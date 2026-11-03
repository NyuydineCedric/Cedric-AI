"""
Cedric AI - AI Orchestrator (Phase 14)
==========================================

  USER MESSAGE
     |
  GEMINI (given the Phase 15 tool declarations) decides: answer
     directly, or call one or more tools first
     |
  [if tool call(s) requested]
     EXECUTE server-side, permission-scoped to the logged-in user
     (see services/tools.py - the model picks the tool and its
     arguments, never whose data it touches)
     |
     FEED the tool result(s) back to Gemini as a new turn
     |
  GEMINI produces the final natural-language answer, now informed by
     real tool output instead of guessing
     |
  (repeat, up to MAX_TOOL_ROUNDS, in case one tool call's result leads
  the model to want to call another)

This is genuine orchestration: which capability a request needs is
decided by Gemini's own function-calling, not by this codebase hand-
writing if/else intent detection - matching the project spec's
worked example almost exactly ("find my notes and explain PID control"
-> the model itself calls search_documents/ask_documents).

SKETCH HANDLING, A DELIBERATE EXCEPTION TO THE GENERIC LOOP:
Every other tool's result is fed back into Gemini's own context
verbatim, since the model may need to read and reason about it (e.g.
RAG's answer text, search results). create_sketch is different: its
result is raw SVG markup - hundreds of characters the model doesn't
need to re-read to know the sketch succeeded, and feeding it back
verbatim would burn context/cost for nothing. So the raw SVG is
captured directly into `sketch_svg` for the frontend to render, while
Gemini's own context only ever sees a short success/failure note.
"""

from google.genai import types
from sqlalchemy.orm import Session

from app.services.context_engine import build_student_context
from app.services.gemini_client import get_gemini_client
from app.services.tools import TOOL_DECLARATIONS, TOOL_IMPLEMENTATIONS

# Caps how many times the model can call a tool before we give up and
# return an honest failure - protects against a runaway tool-call loop
# from a model misfire rather than hanging or looping forever.
MAX_TOOL_ROUNDS = 4


def _build_tools() -> list:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"], description=t["description"], parameters=t["parameters"]
                )
                for t in TOOL_DECLARATIONS
            ]
        )
    ]


def run_orchestrated_chat(db: Session, owner_id: int, messages: list[dict]) -> dict:
    client = get_gemini_client()
    system_instruction = build_student_context(db, owner_id)
    tools = _build_tools()

    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    tools_used: list[dict] = []
    sketch_svg: str | None = None

    for _round in range(MAX_TOOL_ROUNDS):
        response = client.generate_with_tools(contents, tools, system_instruction)
        candidate_content = response.candidates[0].content
        function_calls = [p.function_call for p in candidate_content.parts if p.function_call]

        if not function_calls:
            return {"answer": response.text or "", "tools_used": tools_used, "sketch": sketch_svg}

        # The model's own function-call turn has to go into the
        # conversation before we send back results - Gemini needs to
        # see what it asked for, not just the answer to it.
        contents.append(candidate_content)

        response_parts = []
        for call in function_calls:
            arguments = dict(call.args or {})
            implementation = TOOL_IMPLEMENTATIONS.get(call.name)
            if implementation is None:
                result = {"error": f"Unknown tool '{call.name}'"}
            else:
                try:
                    result = implementation(db, owner_id, **arguments)
                except Exception as exc:  # noqa: BLE001 - a tool failing shouldn't crash the chat
                    result = {"error": str(exc)[:300]}

            tools_used.append({"name": call.name, "arguments": arguments})

            # See module docstring: create_sketch's raw SVG is
            # captured for the frontend, not echoed back to Gemini.
            if call.name == "create_sketch" and "svg" in result:
                sketch_svg = result["svg"]
                gemini_result = {"success": True, "note": "Sketch created and shown to the student."}
            else:
                gemini_result = result

            response_parts.append(
                types.Part(function_response=types.FunctionResponse(name=call.name, response=gemini_result))
            )

        contents.append(types.Content(role="user", parts=response_parts))

    return {
        "answer": (
            "I wasn't able to finish that after several tool calls - "
            "try rephrasing your request or breaking it into smaller steps."
        ),
        "tools_used": tools_used,
        "sketch": sketch_svg,
    }