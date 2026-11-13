import { useCallback, useEffect, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { api, ApiError, type Doc, type Share, type User } from "../api";
import Toolbar from "./Toolbar";
import ShareDialog from "./ShareDialog";

type SaveStatus = "saved" | "unsaved" | "saving" | "error" | "conflict";

const AUTOSAVE_MS = 800;
const POLL_MS = 5000;

const STATUS_TEXT: Record<SaveStatus, string> = {
  saved: "All changes saved",
  unsaved: "Unsaved changes…",
  saving: "Saving…",
  error: "Couldn't save — retrying",
  conflict: "Edit conflict",
};

interface Props {
  docId: string;
  me: User;
  onBack: () => void;
}

export default function EditorPage({ docId, onBack }: Props) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [notice, setNotice] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);

  const versionRef = useRef(0);
  const titleRef = useRef("");
  const dirty = useRef({ title: false, content: false });
  const saving = useRef(false);
  const timer = useRef<number | undefined>(undefined);
  const statusRef = useRef<SaveStatus>("saved");
  statusRef.current = status;

  const readOnly = doc?.role === "viewer";

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        link: { openOnClick: false, autolink: true },
      }),
      Placeholder.configure({ placeholder: "Start writing…" }),
    ],
    editable: false,
    content: "",
    onUpdate: () => markDirty("content"),
  });

  const isDirty = () => dirty.current.title || dirty.current.content;

  const flush = useCallback(async (): Promise<void> => {
    if (!editor || saving.current || !isDirty() || statusRef.current === "conflict") return;
    window.clearTimeout(timer.current);
    saving.current = true;
    const sent = { ...dirty.current };
    dirty.current = { title: false, content: false };
    const patch: { title?: string; content_html?: string; base_version: number } = {
      base_version: versionRef.current,
    };
    if (sent.title && titleRef.current.trim()) patch.title = titleRef.current.trim();
    if (sent.content) patch.content_html = editor.getHTML();
    setStatus("saving");
    try {
      const updated = await api.updateDoc(docId, patch);
      versionRef.current = updated.version;
      setDoc((d) => (d ? { ...d, title: updated.title, updated_at: updated.updated_at } : d));
      setStatus(isDirty() ? "unsaved" : "saved");
    } catch (e) {
      // Put back whatever we failed to send so nothing is silently lost.
      dirty.current = { title: dirty.current.title || sent.title, content: dirty.current.content || sent.content };
      if (e instanceof ApiError && e.status === 409) {
        setStatus("conflict");
      } else if (e instanceof ApiError && (e.status === 403 || e.status === 404)) {
        setStatus("error");
        setNotice("Your access to this document has changed. Reload to see the latest.");
        editor.setEditable(false);
      } else {
        setStatus("error");
        setNotice(e instanceof ApiError ? e.message : "Network error — will retry");
        timer.current = window.setTimeout(() => void flush(), 3000);
      }
    } finally {
      saving.current = false;
      if (isDirty() && (statusRef.current as SaveStatus) !== "conflict") schedule();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, docId]);

  const schedule = () => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), AUTOSAVE_MS);
  };

  function markDirty(field: "title" | "content") {
    dirty.current[field] = true;
    if (statusRef.current !== "conflict") setStatus("unsaved");
    schedule();
  }

  const applyServerDoc = useCallback(
    (d: Doc) => {
      setDoc(d);
      setTitle(d.title);
      titleRef.current = d.title;
      versionRef.current = d.version;
      dirty.current = { title: false, content: false };
      if (editor) {
        editor.commands.setContent(d.content_html, { emitUpdate: false });
        editor.setEditable(d.role !== "viewer");
      }
    },
    [editor],
  );

  // Initial load.
  useEffect(() => {
    if (!editor) return;
    api
      .getDoc(docId)
      .then((d) => {
        applyServerDoc(d);
        setStatus("saved");
      })
      .catch((e) => setLoadError(e instanceof ApiError && e.status === 404 ? "This document doesn't exist or you don't have access to it." : "Failed to load document"));
  }, [docId, editor, applyServerDoc]);

  // Pull collaborators' saved changes while we have nothing pending.
  useEffect(() => {
    if (!doc) return;
    const id = window.setInterval(async () => {
      if (saving.current || isDirty() || document.hidden || statusRef.current === "conflict") return;
      try {
        const latest = await api.getDoc(docId);
        if (latest.version > versionRef.current && !isDirty()) {
          applyServerDoc(latest);
          setNotice("Updated with the latest changes from a collaborator.");
          window.setTimeout(() => setNotice(null), 3000);
        } else if (latest.role !== doc.role) {
          setDoc(latest);
          editor?.setEditable(latest.role !== "viewer");
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setLoadError("This document was deleted or your access was removed.");
        }
      }
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [doc, docId, editor, applyServerDoc]);

  // Warn before closing the tab with unsaved changes; flush on unmount.
  useEffect(() => {
    const onUnload = (e: BeforeUnloadEvent) => {
      if (isDirty()) e.preventDefault();
    };
    window.addEventListener("beforeunload", onUnload);
    return () => {
      window.removeEventListener("beforeunload", onUnload);
      void flush();
    };
  }, [flush]);

  const resolveConflict = async (keepMine: boolean) => {
    const latest = await api.getDoc(docId);
    if (keepMine) {
      versionRef.current = latest.version;
      setStatus("unsaved");
      statusRef.current = "unsaved";
      await flush();
    } else {
      applyServerDoc(latest);
      setStatus("saved");
    }
  };

  const back = async () => {
    await flush();
    onBack();
  };

  const remove = async () => {
    if (!doc || !window.confirm(`Delete "${doc.title}"? This can't be undone.`)) return;
    try {
      dirty.current = { title: false, content: false };
      await api.deleteDoc(docId);
      onBack();
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : "Delete failed");
    }
  };

  if (loadError) {
    return (
      <main className="center">
        <p>{loadError}</p>
        <button className="btn" onClick={onBack}>
          Back to documents
        </button>
      </main>
    );
  }

  return (
    <main className="editor-page">
      <div className="doc-header">
        <button className="btn ghost" onClick={back} title="Back to documents" aria-label="Back to documents">
          ←
        </button>
        <div className="title-block">
          <input
            className="title-input"
            value={title}
            readOnly={readOnly || !doc}
            maxLength={200}
            aria-label="Document title"
            placeholder="Untitled document"
            onChange={(e) => {
              setTitle(e.target.value);
              titleRef.current = e.target.value;
              if (e.target.value.trim()) markDirty("title");
            }}
            onBlur={() => {
              if (!titleRef.current.trim() && doc) {
                setTitle(doc.title);
                titleRef.current = doc.title;
              }
            }}
            onKeyDown={(e) => e.key === "Enter" && editor?.commands.focus()}
          />
          <div className="meta muted small">
            {doc && doc.role !== "owner" && (
              <>
                Shared by {doc.owner.name} ·{" "}
                <span className={`badge ${doc.role}`}>{doc.role === "editor" ? "Can edit" : "View only"}</span> ·{" "}
              </>
            )}
            {doc && (readOnly ? "Read-only" : <span className={`status ${status}`}>{STATUS_TEXT[status]}</span>)}
          </div>
        </div>
        <div className="doc-actions">
          {doc && (
            <a className="btn ghost" href={api.exportUrl(docId)} download>
              Export .md
            </a>
          )}
          {doc?.role === "owner" && (
            <>
              <button className="btn ghost danger" onClick={remove}>
                Delete
              </button>
              <button className="btn primary" onClick={() => setShareOpen(true)}>
                Share{doc.shares && doc.shares.length > 0 ? ` · ${doc.shares.length}` : ""}
              </button>
            </>
          )}
        </div>
      </div>

      {status === "conflict" && (
        <div className="banner warn" role="alert">
          Someone else saved this document while you were editing.
          <button className="btn" onClick={() => resolveConflict(false)}>
            Load their version
          </button>
          <button className="btn" onClick={() => resolveConflict(true)}>
            Keep mine (overwrite)
          </button>
        </div>
      )}
      {notice && (
        <div className="banner info" role="status">
          {notice}
          <button className="link" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}

      {editor && !readOnly && doc && <Toolbar editor={editor} />}
      <div className="paper-scroll">
        <div className={`paper ${readOnly ? "readonly" : ""}`}>
          {!doc && <p className="muted">Loading…</p>}
          <EditorContent editor={editor} />
        </div>
      </div>

      {shareOpen && doc && (
        <ShareDialog
          docId={docId}
          owner={doc.owner}
          initial={doc.shares ?? []}
          onClose={(shares: Share[]) => {
            setShareOpen(false);
            setDoc((d) => (d ? { ...d, shares } : d));
          }}
        />
      )}
    </main>
  );
}
