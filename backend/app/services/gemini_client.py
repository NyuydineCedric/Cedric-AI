"""
Cedric AI - Gemini Client
===========================

The one place in the codebase that talks to Google's Gemini API. Every
future AI feature (RAG generation, quiz generation, vision, etc.)
will call through here rather than each importing the SDK directly -
that keeps model config, error handling, and (later) logging/cost
tracking in one place instead of scattered across feature modules.

AI ENGINEERING DATA FLOW FOR THIS FEATURE:

  INPUT              -> conversation history from the frontend
  PREPROCESSING       -> convert our {role, content} shape into the
                          SDK's expected `contents` format
  AI/MODEL            -> client.models.generate_content(...)
  POSTPROCESSING      -> extract plain text, handle empty/blocked
                          responses instead of crashing
  OUTPUT              -> plain string reply
"""

from google import genai
from google.genai import types

from app.core.config import settings


class GeminiClient:
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            # Fail with a clear message instead of a cryptic SDK error
            # the first time someone tries to send a chat message.
            raise RuntimeError(
                "GEMINI_API_KEY is not set in backend/.env - the client "
                "cannot be created without it."
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def generate_reply(self, messages: list[dict], system_instruction: str | None = None) -> str:
        """
        `messages` is a list of {"role": "user" | "assistant", "content": str},
        oldest first - the shape our API/frontend use. Gemini's SDK
        expects role "model" instead of "assistant" and a `parts` list
        instead of a plain string, so we translate here rather than
        leaking Gemini's wire format into the rest of the app.

        `system_instruction` (Phase 13, context engine) is background
        guidance - who the model is, what it knows about the student -
        that shapes the reply without being a visible turn in the
        conversation itself.
        """
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]

        config = (
            types.GenerateContentConfig(system_instruction=system_instruction)
            if system_instruction
            else None
        )

        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=config,
        )

        # `response.text` is None if the model returned no candidates
        # at all (e.g. the prompt was blocked by a safety filter).
        # Surfacing a clear message beats letting `None` propagate up
        # and show as a blank chat bubble in the UI.
        if not response.text:
            return (
                "I wasn't able to generate a response to that "
                "(it may have been blocked by a safety filter). "
                "Try rephrasing."
            )

        return response.text

    def generate_with_tools(
        self,
        contents: list,
        tools: list,
        system_instruction: str | None = None,
    ):
        """
        Phase 14/15: like generate_reply, but with function-calling
        tools available and returning the RAW SDK response (not just
        `.text`) - the orchestrator needs to inspect it for
        `function_call` parts before deciding whether there's a final
        text answer yet. See services/orchestrator.py.
        """
        config = types.GenerateContentConfig(system_instruction=system_instruction, tools=tools)
        return self._client.models.generate_content(
            model=settings.gemini_model, contents=contents, config=config
        )

    def describe_image(self, image_bytes: bytes, mime_type: str, prompt: str) -> str:
        """
        Phase 18: true multimodal understanding - the image is sent
        directly to Gemini as part of the request, not run through a
        separate OCR step first. This is what lets it handle diagrams,
        handwritten notes, and photos, not just printed text.
        """
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Content(role="user", parts=[image_part, types.Part(text=prompt)])],
        )
        if not response.text:
            return "I couldn't analyze this image (it may have been blocked by a safety filter)."
        return response.text

    def generate_structured(self, prompt: str, schema: dict) -> dict:
        """
        Phase 20: ask Gemini to return JSON matching `schema` directly
        (the API's native structured-output mode), rather than asking
        for prose and trying to parse structure out of it afterward.
        Raises json.JSONDecodeError if the model still doesn't comply -
        callers should treat that as a hard failure, not patch around it.
        """
        import json

        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return json.loads(response.text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Phase 6: turn a batch of strings into embedding vectors (used
        both to embed document chunks at upload time, and to embed a
        user's question at retrieval time - same model for both, which
        matters: comparing vectors from two different embedding models
        would be meaningless).
        """
        if not texts:
            return []

        response = self._client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=texts,
        )
        return [embedding.values for embedding in response.embeddings]
    
        def search_web(self, query: str) -> dict:
            """
        A separate, isolated call using the Gemini API's BUILT-IN
        Google Search grounding tool - not a custom function
        declaration. Kept as its own dedicated call rather than added
        to generate_with_tools's tools list, because the API doesn't
        reliably support mixing its built-in search-grounding tool
        with custom function-declaration tools in the same request.
        The orchestrator's own tool_search_web (services/tools.py)
        calls this internally and returns only the resulting text +
        sources as a function response - to the orchestrator's main
        call, this looks like any other tool result.
        """
        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Content(role="user", parts=[types.Part(text=query)])],
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
        )

        text = response.text or "No results found."
        sources = []
        try:
            grounding = response.candidates[0].grounding_metadata
            if grounding and grounding.grounding_chunks:
                for chunk in grounding.grounding_chunks:
                    if chunk.web:
                        sources.append({"title": chunk.web.title, "url": chunk.web.uri})
        except (AttributeError, IndexError):
            pass  # No grounding metadata on this response - return the text alone.

        return {"answer": text, "sources": sources}
    
        def generate_sketch(self, description: str) -> str:
            """
        Asks Gemini to emit raw SVG markup for a simple line-art
        sketch/diagram - NOT a photorealistic image (that would need
        Imagen, a separate, billed model). This reuses the same
        text-generation model, just constrained to output SVG source
        instead of prose.
        """
        prompt = (
            "Draw a simple, clean SVG sketch/diagram of the following, "
            "for display inside a chat message. Rules:\n"
            "- Output ONLY raw <svg>...</svg> markup, nothing else - no "
            "markdown code fences, no explanation before or after.\n"
            '- Use viewBox="0 0 400 300", simple shapes/lines/paths, a '
            "restrained color palette.\n"
            "- Style it like a hand-drawn whiteboard sketch or diagram, "
            "not a photorealistic image.\n"
            "- Include short text labels directly in the SVG where "
            "useful (e.g. labeling parts of a diagram).\n\n"
            f"Sketch this: {description}"
        )
        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        )
        svg = (response.text or "").strip()

        # Defensive: strip a markdown code fence if the model added
        # one anyway, despite the instruction not to.
        if svg.startswith("```"):
            svg = svg.split("\n", 1)[1] if "\n" in svg else svg
            if svg.endswith("```"):
                svg = svg.rsplit("```", 1)[0]
            svg = svg.strip()

        return svg


# A single shared instance. Cheap to construct, but this avoids
# re-creating the SDK client on every request.
_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
