import { useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { sendOrchestratedMessage } from '../api/orchestrator'

// -----------------------------------------------------------------------
// Cedric AI - Smart Assistant (Phase 14-15: orchestrator + tools)
// -----------------------------------------------------------------------
// Looks like a normal chat, but every message goes through Gemini's
// function-calling: the model itself decides whether to just answer,
// or call search_documents / ask_documents / get_memory / save_memory
// first. Each assistant turn shows which tools (if any) were used, so
// the orchestration is visible rather than a black box.
// -----------------------------------------------------------------------

export function AssistantPanel() {
  const { token } = useAuth()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(false)
  const bottomRef = useRef(null)

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return

    const nextMessages = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    setInput('')
    setError(null)
    setSending(true)

    try {
      const { answer, tools_used: toolsUsed } = await sendOrchestratedMessage(token, nextMessages)
      setMessages([...nextMessages, { role: 'assistant', content: answer, toolsUsed }])
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <div className="chat-panel">
      <p className="lede small">
        This assistant can decide on its own to search your files,
        answer from your documents, or remember/recall things about
        you - watch for the "used" tags below its replies.
      </p>

      <div className="chat-history">
        {messages.length === 0 && (
          <p className="chat-empty">
            Try: "Find my notes about X" or "Remember that my exam is
            next Friday."
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble chat-${m.role}`}>
            <span className="chat-role">{m.role === 'user' ? 'You' : 'Cedric AI'}</span>
            <p>{m.content}</p>
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

      <form className="chat-input-row" onSubmit={handleSend}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the assistant anything…"
          disabled={sending}
        />
        <button type="submit" className="submit-btn" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
