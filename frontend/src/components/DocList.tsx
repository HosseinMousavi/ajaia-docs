import { useEffect, useRef, useState } from "react";
import { api, ApiError, MAX_UPLOAD_MB, SUPPORTED_UPLOADS, type DocSummary } from "../api";

function timeAgo(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

type Tab = "owned" | "shared";

export default function DocList({ onOpen }: { onOpen: (id: string) => void }) {
  const [docs, setDocs] = useState<{ owned: DocSummary[]; shared: DocSummary[] } | null>(null);
  const [tab, setTab] = useState<Tab>("owned");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .listDocs()
      .then(setDocs)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load documents"));
  }, []);

  const create = async () => {
    setBusy(true);
    try {
      onOpen((await api.createDoc()).id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create document");
      setBusy(false);
    }
  };

  const upload = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`"${file.name}" is larger than ${MAX_UPLOAD_MB} MB`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onOpen((await api.importFile(file)).id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
      setBusy(false);
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const list = docs ? docs[tab] : [];

  return (
    <main className="home">
      <section className="actions">
        <button className="tile" onClick={create} disabled={busy}>
          <span className="tile-icon">＋</span>
          <span>Blank document</span>
        </button>
        <button className="tile" onClick={() => fileRef.current?.click()} disabled={busy}>
          <span className="tile-icon">⇪</span>
          <span>Import a file</span>
          <span className="muted small">.txt, .md, .docx · max {MAX_UPLOAD_MB} MB</span>
        </button>
        <input
          ref={fileRef}
          type="file"
          accept={SUPPORTED_UPLOADS}
          hidden
          data-testid="file-input"
          onChange={(e) => upload(e.target.files?.[0])}
        />
      </section>

      {error && (
        <div className="error" role="alert">
          {error}
          <button className="link" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      <nav className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "owned"} className={tab === "owned" ? "active" : ""} onClick={() => setTab("owned")}>
          My documents {docs && <span className="count">{docs.owned.length}</span>}
        </button>
        <button role="tab" aria-selected={tab === "shared"} className={tab === "shared" ? "active" : ""} onClick={() => setTab("shared")}>
          Shared with me {docs && <span className="count">{docs.shared.length}</span>}
        </button>
      </nav>

      {!docs && !error && <p className="muted">Loading…</p>}
      {docs && list.length === 0 && (
        <p className="empty muted">
          {tab === "owned" ? "No documents yet — create one or import a file." : "Nothing has been shared with you yet."}
        </p>
      )}
      <ul className="doc-list">
        {list.map((d) => (
          <li key={d.id}>
            <button className="doc-row" onClick={() => onOpen(d.id)}>
              <span className="doc-icon" aria-hidden>
                ▤
              </span>
              <span className="doc-title">{d.title}</span>
              {tab === "shared" ? (
                <span className="muted small">
                  {d.owner.name} · <span className={`badge ${d.role}`}>{d.role === "editor" ? "Can edit" : "View only"}</span>
                </span>
              ) : (
                <span className="badge owner">Owner</span>
              )}
              <span className="muted small when">{timeAgo(d.updated_at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
