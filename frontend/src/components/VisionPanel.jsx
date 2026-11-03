import { useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { analyzeImage } from "../api/vision";

// -----------------------------------------------------------------------
// Cedric AI - Vision (Phase 18-19)
// -----------------------------------------------------------------------
// Single-image analysis only - either an uploaded file or one photo
// captured from the device camera via <input capture>. This is
// deliberately NOT continuous video: see backend/app/api/vision.py's
// docstring for why that distinction matters and isn't just UI
// wording - there's no persistent stream reaching the model, no
// reasoning across frames.
// -----------------------------------------------------------------------

export function VisionPanel() {
  const { token } = useAuth();
  const [previewUrl, setPreviewUrl] = useState(null);
  const [file, setFile] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  function handleFileChosen(e) {
    const chosen = e.target.files?.[0];
    e.target.value = "";
    if (!chosen) return;

    setFile(chosen);
    setResult(null);
    setError(null);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(chosen);
    });
  }

  async function handleAnalyze(e) {
    e.preventDefault();
    if (!file || analyzing) return;

    setAnalyzing(true);
    setError(null);
    try {
      const { description } = await analyzeImage(
        token,
        file,
        prompt.trim() || undefined,
      );
      setResult(description);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="vision-panel">
      <p className="lede small">
        Upload an image or take a photo - a diagram, handwritten notes, a
        screenshot, anything visual. This analyzes one still image, not a live
        camera feed.
      </p>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        onChange={handleFileChosen}
        style={{ display: "none" }}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileChosen}
        style={{ display: "none" }}
      />

      <div className="vision-toolbar">
        <button
          type="button"
          className="submit-btn secondary"
          onClick={() => fileInputRef.current?.click()}
        >
          Upload an image
        </button>
        <button
          type="button"
          className="submit-btn secondary"
          onClick={() => cameraInputRef.current?.click()}
        >
          Take a photo
        </button>
      </div>

      {previewUrl && (
        <div className="vision-preview">
          <img src={previewUrl} alt="Selected for analysis" />
        </div>
      )}

      <form className="chat-input-row" onSubmit={handleAnalyze}>
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Optional: ask something specific about the image…"
          disabled={analyzing}
        />
        <button
          type="submit"
          className="submit-btn"
          disabled={!file || analyzing}
        >
          {analyzing ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {error && <div className="form-error">{error}</div>}

      {result && (
        <div className="rag-answer" style={{ marginTop: "1.25rem" }}>
          {result}
        </div>
      )}
    </div>
  );
}
