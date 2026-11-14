import { useEffect, useState } from "react";
import { api, ApiError, avatarColor, timeAgo, type Doc, type Version, type VersionDetail } from "../api";

interface Props {
  docId: string;
  docVersion: number;
  canEdit: boolean;
  /** Flush pending edits and return the version to restore on top of. */
  prepareRestore: () => Promise<number>;
  onRestored: (doc: Doc) => void;
  onClose: () => void;
}

const KIND_LABEL: Record<Version["kind"], string> = {
  created: "Created",
  imported: "Imported from file",
  baseline: "Earlier version",
  edit: "Edited",
  restored: "Restored",
};

export default function HistoryPanel({ docId, docVersion, canEdit, prepareRestore, onRestored, onClose }: Props) {
  const [versions, setVersions] = useState<Version[] | null>(null);
  const [preview, setPreview] = useState<VersionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .listVersions(docId)
      .then(setVersions)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load history"));
  }, [docId, docVersion]);

  const open = async (v: Version) => {
    setError(null);
    try {
      setPreview(await api.getVersion(docId, v.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load version");
    }
  };

  const restore = async () => {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const base = await prepareRestore();
      const doc = await api.restoreVersion(docId, preview.id, base);
      setPreview(null);
      onRestored(doc);
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 409
          ? "Someone just changed the document. Try again in a moment."
          : e instanceof ApiError
            ? e.message
            : "Restore failed",
      );
    } finally {
      setBusy(false);
    }
  };

  const isCurrent = (v: Version) => v.version === docVersion;

  return (
    <aside className="side-panel" aria-label="Version history">
      <div className="panel-head">
        <h2>Version history</h2>
        <button className="btn ghost" onClick={onClose} aria-label="Close history">
          ✕
        </button>
      </div>
      <p className="muted small">
        Saves by the same person within 10 minutes are grouped into one version. Click a version to see what changed.
      </p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {!versions && !error && <p className="muted small">Loading…</p>}
      {versions && versions.length === 0 && <p className="muted small">No history yet — it starts with the next edit.</p>}
      <ol className="versions">
        {versions?.map((v) => (
          <li key={v.id}>
            <button className={`v-row ${preview?.id === v.id ? "on" : ""}`} onClick={() => open(v)}>
              <span className="v-dot" style={{ background: v.author ? avatarColor(v.author.id) : "#999" }} />
              <span className="v-main">
                <span className="v-title">
                  {KIND_LABEL[v.kind]}
                  {v.kind === "restored" && v.restored_from ? ` v${v.restored_from}` : ""}
                  {isCurrent(v) && <span className="badge owner">Current</span>}
                </span>
                <span className="muted small">
                  {v.author?.name ?? "Unknown"} · {timeAgo(v.updated_at)} · v{v.version}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ol>

      {preview && (
        <div className="modal-backdrop" onMouseDown={() => setPreview(null)}>
          <div
            className="modal wide"
            role="dialog"
            aria-modal="true"
            aria-label="Version preview"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <h2>
              {KIND_LABEL[preview.kind]} · v{preview.version}
            </h2>
            <div className="muted small">
              {preview.author?.name ?? "Unknown"} · {new Date(preview.updated_at).toLocaleString()} · title “
              {preview.title}”
            </div>
            {isCurrent(preview) ? (
              <p className="muted">This is the current version.</p>
            ) : (
              <>
                <div className="diff-legend small">
                  If you restore this version:{" "}
                  <ins>+{preview.stats.added} words come back</ins> <del>−{preview.stats.removed} words removed</del>
                </div>
                <div className="diff" data-testid="version-diff">
                  {preview.diff.length === 0 && <span className="muted">Both versions are empty.</span>}
                  {preview.diff.map(([op, text], i) =>
                    op === "insert" ? <ins key={i}>{text}</ins> : op === "delete" ? <del key={i}>{text}</del> : <span key={i}>{text}</span>,
                  )}
                </div>
              </>
            )}
            <div className="modal-actions">
              <button className="btn" onClick={() => setPreview(null)}>
                Close
              </button>
              {canEdit && !isCurrent(preview) && (
                <button className="btn primary" disabled={busy} onClick={restore}>
                  {busy ? "Restoring…" : "Restore this version"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
