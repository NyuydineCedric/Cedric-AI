import { useCallback, useEffect, useRef, useState } from 'react'

// -----------------------------------------------------------------------
// Cedric AI - Speech-to-text (Phase 16)
// -----------------------------------------------------------------------
// Uses the browser's built-in Web Speech API (SpeechRecognition)
// instead of a cloud STT service - zero extra backend dependency or
// API key. Works client-side, though most browsers' implementations
// (Chrome's included) stream audio to the vendor's own servers under
// the hood - this is not genuinely offline/on-device recognition.
//
// CONTINUOUS MODE + OUR OWN SILENCE TIMER:
// An earlier version used continuous=false and relied on the
// browser's own end-of-speech detection to know when the student
// stopped talking. That cut sentences off prematurely mid-thought.
// This version keeps recognition running continuously and instead
// tracks silence ourselves: every time new speech arrives, a timer
// resets; if SILENCE_TIMEOUT_MS passes with nothing new, THEN we
// stop - a deliberately more patient, conversational cutoff.
//
// LIMITATIONS, STATED PLAINLY:
// - Browser support is inconsistent (Chrome/Edge desktop best;
//   Firefox/Safari partial or missing) - isSupported feature-detects
//   and calling code should hide voice UI entirely rather than show
//   a button that silently fails.
// - Requires an active internet connection in most implementations.
// - Recognition quality/accuracy is whatever the browser vendor's
//   model produces - not something this app can tune.
// - The browser will show its own mic-in-use indicator (address bar
//   or tab) once permission is granted - that's OS/browser chrome,
//   not something a web app can hide, regardless of in-app UI.
// -----------------------------------------------------------------------

const SpeechRecognitionAPI =
  typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

const SILENCE_TIMEOUT_MS = 4000

export function useSpeechRecognition() {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState(null)
  const recognitionRef = useRef(null)
  const silenceTimerRef = useRef(null)
  const finalTranscriptRef = useRef('')

  const isSupported = Boolean(SpeechRecognitionAPI)

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
  }, [])

  const start = useCallback(() => {
    if (!isSupported || isListening) return

    const recognition = new SpeechRecognitionAPI()
    recognition.lang = 'en-US'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    finalTranscriptRef.current = ''

    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalText += chunk
        } else {
          interimText += chunk
        }
      }
      if (finalText) {
        finalTranscriptRef.current = (finalTranscriptRef.current + ' ' + finalText).trim()
      }
      setTranscript((finalTranscriptRef.current + ' ' + interimText).trim())

      // OUR silence detection, not the browser's - reset on every
      // new result (interim or final), so a natural mid-sentence
      // pause doesn't cut the student off.
      clearSilenceTimer()
      silenceTimerRef.current = setTimeout(() => recognition.stop(), SILENCE_TIMEOUT_MS)
    }

    recognition.onerror = (event) => {
      // 'no-speech' fires routinely while idle in continuous mode -
      // not a real error worth surfacing.
      if (event.error !== 'no-speech') setError(event.error)
    }

    recognition.onend = () => {
      clearSilenceTimer()
      setIsListening(false)
    }

    recognitionRef.current = recognition
    setError(null)
    setTranscript('')
    setIsListening(true)
    recognition.start()
  }, [isSupported, isListening, clearSilenceTimer])

  const stop = useCallback(() => {
    clearSilenceTimer()
    recognitionRef.current?.stop()
  }, [clearSilenceTimer])

  const resetTranscript = useCallback(() => {
    finalTranscriptRef.current = ''
    setTranscript('')
  }, [])

  useEffect(
    () => () => {
      clearSilenceTimer()
      recognitionRef.current?.stop()
    },
    [clearSilenceTimer]
  )

  return { isSupported, isListening, transcript, error, start, stop, resetTranscript }
}