// -----------------------------------------------------------------------
// Cedric AI - Text-to-speech (Phase 17)
// -----------------------------------------------------------------------
// Uses the browser's built-in SpeechSynthesis API - same tradeoff as
// speech-to-text (useSpeechRecognition.js): zero backend dependency
// or API key, but voice quality/availability depends entirely on
// whatever voices the browser/OS has installed, and support is
// inconsistent across browsers.
//
// isSpeaking is exposed so hands-free chat (ChatPanel.jsx) can avoid
// listening while the AI is talking - without it, the mic would pick
// up Cedric AI's own voice as if the student had said it.
// -----------------------------------------------------------------------

import { useCallback, useState } from 'react'

export function useSpeechSynthesis() {
  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const [isSpeaking, setIsSpeaking] = useState(false)

  const speak = useCallback(
    (text) => {
      if (!isSupported || !text) return
      window.speechSynthesis.cancel() // stop whatever was already being read

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.onstart = () => setIsSpeaking(true)
      utterance.onend = () => setIsSpeaking(false)
      utterance.onerror = () => setIsSpeaking(false)

      window.speechSynthesis.speak(utterance)
    },
    [isSupported]
  )

  const stop = useCallback(() => {
    if (isSupported) window.speechSynthesis.cancel()
    setIsSpeaking(false)
  }, [isSupported])

  return { isSupported, isSpeaking, speak, stop }
}