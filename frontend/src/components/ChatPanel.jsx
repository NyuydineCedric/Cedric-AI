import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import DOMPurify from "dompurify";
import { useAuth } from "../context/AuthContext";
import { sendOrchestratedMessage } from "../api/orchestrator";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import logo from "../assets/logo.jpg";

// -----------------------------------------------------------------------
// Cedric AI - Chat (single conversational surface, orchestrator-powered)
// -----------------------------------------------------------------------
// EMPTY-STATE GREETING: a static "Hello, {name}" screen, not an AI-
// generated chat message - no API call, so nothing to repeat or waste
// a Gemini request on. It disappears once a real conversation starts.
//
// HANDS-FREE VOICE: off by default - opt in via the checkbox.
//
// TURN-TAKING, ENFORCED IN BOTH DIRECTIONS:
// - The mic doesn't listen while Cedric AI is speaking.
// - The text input/Send are disabled while tts.isSpeaking too, so a
//   student can't send a new message that overlaps the reply still
//   being read aloud.
// - A "Stop" button lets the student interrupt Cedric AI mid-reply;
//   stopping TTS flips isSpeaking back to false, which the existing
//   turn-taking effect picks up and resumes listening automatically.
//
// SKETCHES: if the orchestrator's response includes raw SVG (the
// create_sketch tool), it's sanitized with DOMPurify's SVG profile
// before being injected into the DOM - LLM-generated markup is never
// trusted raw, since a malicious <script>/onload could otherwise run
// in the page.
// -----------------------------------------------------------------------

export function ChatPanel() {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);
  const [speakReplies, setSpeakReplies] = useState(true);
  const bottomRef = useRef(null);
  const wasListeningRef = useRef(false);

  const speech = useSpeechRecognition();
  const tts = useSpeechSynthesis();

  const [handsFree, setHandsFree] = useState(false);
  const [micReady, setMicReady] = useState(false);
  const [checkingMic, setCheckingMic] = useState(true);

  useEffect(() => {
    if (!speech.isSupported || !navigator.permissions?.query) {
      setCheckingMic(false);
      return;
    }
    navigator.permissions
      .query({ name: "microphone" })
      .then((status) => {
        setMicReady(status.state === "granted");
        setCheckingMic(false);
      })
      .catch(() => setCheckingMic(false));
  }, [speech.isSupported]);

  useEffect(() => {
    if (speech.transcript) setInput(speech.transcript);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speech.transcript]);

  useEffect(() => {
    if (
      !handsFree ||
      !micReady ||
      sending ||
      tts.isSpeaking ||
      speech.isListening
    )
      return;
    const timer = setTimeout(() => speech.start(), 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handsFree, micReady, sending, tts.isSpeaking, speech.isListening]);

  useEffect(() => {
    if (!handsFree && speech.isListening) speech.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handsFree]);

  useEffect(() => {
    if (handsFree && wasListeningRef.current && !speech.isListening) {
      const text = speech.transcript.trim();
      if (text) submitMessage(text);
    }
    wasListeningRef.current = speech.isListening;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speech.isListening]);

  async function submitMessage(text) {
    if (!text || sending || tts.isSpeaking) return;

    const nextMessages = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    speech.resetTranscript();
    setError(null);
    setSending(true);

    try {
      const {
        answer,
        tools_used: toolsUsed,
        sketch,
      } = await sendOrchestratedMessage(token, nextMessages);
      setMessages([
        ...nextMessages,
        { role: "assistant", content: answer, toolsUsed, sketch },
      ]);
      if (speakReplies) tts.speak(answer);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
      setTimeout(
        () => bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
        50,
      );
    }
  }

  function handleSend(e) {
    e.preventDefault();
    submitMessage(input.trim());
  }

  function enableMic() {
    setMicReady(true);
    speech.start();
  }

  const firstName = user?.full_name?.split(" ")[0] || "there";
  const inputLocked = sending || tts.isSpeaking;

  return (
    <div className="chat-panel">
      {(speech.isSupported || tts.isSupported) && (
        <div className="voice-controls">
          {speech.isSupported && (
            <label className="voice-toggle">
              <input
                type="checkbox"
                checked={handsFree}
                onChange={(e) => setHandsFree(e.target.checked)}
              />
              Hands-free voice mode
            </label>
          )}
          {tts.isSupported && (
            <label className="voice-toggle">
              <input
                type="checkbox"
                checked={speakReplies}
                onChange={(e) => {
                  setSpeakReplies(e.target.checked);
                  if (!e.target.checked) tts.stop();
                }}
              />
              Read replies aloud
            </label>
          )}
          {!speech.isSupported && (
            <span className="voice-note">
              Voice input isn't supported in this browser.
            </span>
          )}
        </div>
      )}

      <div className="chat-history">
        {messages.length === 0 && !sending && (
          <div className="chat-greeting">
            <img
              src={logo}
              alt="logo"
              style={{ width: "30px", borderRadius: "50%" }}
            />
            Hello, {firstName}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble chat-${m.role}`}>
            <span className="chat-role">
              {m.role === "user" ? "You" : "Cedric AI"}
            </span>
            {m.role === "assistant" ? (
              <div className="markdown-content">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            ) : (
              <p>{m.content}</p>
            )}
            {m.sketch && (
              <div
                className="chat-sketch"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(m.sketch, {
                    USE_PROFILES: { svg: true, svgFilters: true },
                  }),
                }}
              />
            )}
            {m.toolsUsed && m.toolsUsed.length > 0 && (
              <div className="tools-used">
                {m.toolsUsed.map((t, idx) => (
                  <span key={idx} className="status-pill status-pill-completed">
                    used: {t.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="chat-bubble chat-assistant chat-pending">
            <span className="chat-role">Cedric AI</span>
            <p>Thinking…</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <div className="form-error">{error}</div>}
      {speech.error && (
        <div className="form-error">Voice input error: {speech.error}</div>
      )}

      {handsFree && speech.isSupported && !checkingMic && !micReady && (
        <button
          type="button"
          className="submit-btn mic-enable-btn"
          onClick={enableMic}
        >
          🎤 Tap once to start talking (your browser requires this the first
          time)
        </button>
      )}

      {(handsFree && micReady) || tts.isSpeaking ? (
        <div className="voice-status-row">
          {tts.isSpeaking ? (
            <>
              <span className="voice-indicator voice-indicator-speaking">
                <span></span>
                <span></span>
                <span></span>
                <span></span>
              </span>
              <span className="voice-note">Cedric AI is speaking…</span>
              <button
                type="button"
                className="stop-speaking-btn"
                onClick={() => tts.stop()}
              >
                ⏹ Stop
              </button>
            </>
          ) : speech.isListening ? (
            <>
              <span className="voice-indicator voice-indicator-listening">
                <span></span>
                <span></span>
                <span></span>
                <span></span>
              </span>
              <span className="voice-note">Listening…</span>
            </>
          ) : (
            <span className="voice-note">Ready</span>
          )}
        </div>
      ) : null}

      <form className="chat-input-row" onSubmit={handleSend}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            tts.isSpeaking
              ? "Cedric AI is speaking…"
              : handsFree && micReady
                ? "Listening… or type here"
                : "Ask anything…"
          }
          disabled={inputLocked}
        />
        <button
          type="submit"
          className="submit-btn"
          disabled={inputLocked || !input.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}
