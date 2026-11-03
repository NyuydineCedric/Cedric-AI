import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  deleteDocument,
  downloadDocument,
  listDocuments,
  searchDocuments,
  uploadDocument,
} from "../api/documents";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const STATUS_LABEL = {
  completed: "Processed",
  unsupported: "No text extraction",
  failed: "Processing failed",
  pending: "Processing…",
};

export function DocumentsPanel() {
  const { token } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  const fileInputRef = useRef(null);

  // Phase 11: semantic file search ("find the PDF about X")
  const [findQuery, setFindQuery] = useState("");
  const [findResults, setFindResults] = useState(null);
  const [finding, setFinding] = useState(false);
  const [findError, setFindError] = useState(null);

  async function refresh() {
    try {
      setDocuments(await listDocuments(token));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleFileChosen(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setError(null);
    setUploading(true);
    try {
      await uploadDocument(token, file);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id) {
    setError(null);
    try {
      await deleteDocument(token, id);
      setDocuments((docs) => docs.filter((d) => d.id !== id));
      if (expandedId === id) setExpandedId(null); // <- remove this line
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDownload(id, filename) {
    setError(null);
    try {
      await downloadDocument(token, id, filename);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleFind(e) {
    e.preventDefault();
    const q = findQuery.trim();
    if (!q || finding) return;

    setFinding(true);
    setFindError(null);
    setFindResults(null);
    try {
      setFindResults(await searchDocuments(token, q));
    } catch (err) {
      setFindError(err.message);
    } finally {
      setFinding(false);
    }
  }

  return (
    <div className="documents-panel">
      <form className="chat-input-row find-row" onSubmit={handleFind}>
        <input
          type="text"
          value={findQuery}
          onChange={(e) => setFindQuery(e.target.value)}
          placeholder="Find a file by meaning, e.g. 'notes about PID controllers'…"
          disabled={finding}
        />
        <button
          type="submit"
          className="submit-btn"
          disabled={finding || !findQuery.trim()}
        >
          {finding ? "Searching…" : "Find"}
        </button>
      </form>
      {findError && <div className="form-error">{findError}</div>}
      {findResults && (
        <div className="rag-sources find-results">
          <span className="chunk-label">
            {findResults.length === 0
              ? "No matching files found"
              : "Matching files"}
          </span>
          {findResults.map((r) => (
            <div key={r.document_id} className="rag-source">
              <span className="document-name">
                {r.filename}
                {r.page_number != null && ` · page/slide ${r.page_number}`}
                {r.section_title && ` · ${r.section_title}`}
                {` · similarity ${(r.similarity * 100).toFixed(0)}%`}
              </span>
              <p>{r.matched_snippet}</p>
              <button
                type="button"
                className="link-btn"
                onClick={() => handleDownload(r.document_id, r.filename)}
              >
                Download
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="documents-toolbar">
        <p className="lede small">
          PDF, DOCX, PPTX, TXT, or image files, up to 20MB. Text is extracted
          and chunked automatically after upload. Stored per account — nobody
          else can see or list these.
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
          onChange={handleFileChosen}
          style={{ display: "none" }}
        />
        <button
          type="button"
          className="submit-btn"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? "Uploading…" : "Upload a file"}
        </button>
      </div>
      {error && <div className="form-error">{error}</div>}

      {loading ? (
        <p className="lede small">Loading your documents…</p>
      ) : documents.length === 0 ? (
        <p className="chat-empty">No documents uploaded yet.</p>
      ) : (
        <ul className="document-list">
          {documents.map((doc) => (
            <li key={doc.id} className="document-row-wrap">
              <div className="document-row">
                <div className="document-info">
                  <span className="document-name">{doc.filename}</span>
                  <span className="document-meta">
                    {formatSize(doc.size_bytes)} ·{" "}
                    {new Date(doc.uploaded_at).toLocaleString()}
                    {doc.page_count != null && ` · ${doc.page_count} pages`}
                  </span>
                  <span
                    className={`status-pill status-pill-${doc.processing_status}`}
                  >
                    {STATUS_LABEL[doc.processing_status] ||
                      doc.processing_status}
                  </span>

                  {doc.processing_error && (
                    <span className="document-meta">
                      {doc.processing_error}
                    </span>
                  )}
                </div>
                <div className="document-actions">
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => handleDownload(doc.id, doc.filename)}
                  >
                    Download
                  </button>
                  <button
                    type="button"
                    className="link-btn danger"
                    onClick={() => handleDelete(doc.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
