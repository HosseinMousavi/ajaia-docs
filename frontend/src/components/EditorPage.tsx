import { useCallback, useEffect, useRef, useState } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { api, ApiError, ROLE_LABEL, type Comment, type Doc, type PresenceUser, type Share, type User } from "../api";
import Toolbar from "./Toolbar";
import ShareDialog from "./ShareDialog";
import Presence from "./Presence";
import CommentsPanel from "./CommentsPanel";
import HistoryPanel from "./HistoryPanel";

type SaveStatus = "saved" | "unsaved" | "saving" | "error" | "conflict";
type Panel = "comments" | "history" | null;

const AUTOSAVE_MS = 800;
const POLL_MS = 5000;
const EDITING_WINDOW_MS = 8000;

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

/** Locate `quote` inside one text block and return its document positions. */
function findQuote(editor: Editor, quote: string): { from: number; to: number } | null {
  const needles = [quote, quote.split(/\s+/).slice(0, 6).join(" ")].filter((n) => n.length >= 2);
  for (const needle of needles) {
    let found: { from: number; to: number } | null = null;
    editor.state.doc.descendants((node, pos) => {
      if (found) return false;
      if (!node.isTextblock) return true;
      let text = "";
      const map: number[] = [];
      node.descendants((child, childPos) => {
        if (child.isText && child.text) {
          for (let i = 0; i < child.text.length; i++) map.push(pos + 1 + childPos + i);
          text += child.text;
        }
        return true;
      });
      const idx = text.indexOf(needle);
      if (idx >= 0) found = { from: map[idx], to: map[idx + needle.length - 1] + 1 };
      return false;
    });
    if (found) return found;
  }
  return null;
}

export default function EditorPage({ docId, me, onBack }: Props) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [notice, setNotice] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [panel, setPanel] = useState<Panel>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [others, setOthers] = useState<PresenceUser[]>([]);
  const [pendingQuote, setPendingQuote] = useState<string | null>(null);
  const [docVersion, setDocVersion] = useState(0);

  const versionRef = useRef(0);
  const titleRef = useRef("");
  const dirty = useRef({ title: false, content: false });
  const saving = useRef(false);
  const timer = useRef<number | undefined>(undefined);
  const statusRef = useRef<SaveStatus>("saved");
  const lastLocalEdit = useRef(0);
  const suppressQuoteUntil = useRef(0);
  const autoOpenedComments = useRef(false);
  statusRef.current = status;

  const role = doc?.role;
  const canEdit = role === "owner" || role === "editor";
  const canComment = canEdit || role === "commenter";

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

  const setVersion = (v: number) => {
    versionRef.current = v;
    setDocVersion(v);
  };

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
      setVersion(updated.version);
      setDoc((d) => (d ? { ...d, title: updated.title, updated_at: updated.updated_at, version: updated.version } : d));
      setStatus(isDirty() ? "unsaved" : "saved");
    } catch (e) {
      // Put back whatever we failed to send so nothing is silently lost.
      dirty.current = { title: dirty.current.title || sent.title, content: dirty.current.content || sent.content };
      if (e instanceof ApiError && e.status === 409) {
        setStatus("conflict");
      } else if (e instanceof ApiError && (e.status === 403 || e.status === 404)) {
        setStatus("error");
        setNotice("Your access to this document has changed. Reload to see the latest.");
        editor.setEditable(false, false);
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
    lastLocalEdit.current = Date.now();
    if (statusRef.current !== "conflict") setStatus("unsaved");
    schedule();
  }

  const applyServerDoc = useCallback(
    (d: Doc) => {
      setDoc(d);
      setTitle(d.title);
      titleRef.current = d.title;
      setVersion(d.version);
      dirty.current = { title: false, content: false };
      if (editor) {
        editor.commands.setContent(d.content_html, { emitUpdate: false });
        // emitUpdate=false: toggling editability must not look like a user edit (it would trigger autosave).
        editor.setEditable(d.role === "owner" || d.role === "editor", false);
      }
    },
    [editor],
  );

  const loadComments = useCallback(async () => {
    try {
      setComments(await api.listComments(docId));
    } catch {
      /* transient; next poll retries */
    }
  }, [docId]);

  // Initial load.
  useEffect(() => {
    if (!editor) return;
    api
      .getDoc(docId)
      .then((d) => {
        applyServerDoc(d);
        setStatus("saved");
      })
      .catch((e) =>
        setLoadError(
          e instanceof ApiError && e.status === 404
            ? "This document doesn't exist or you don't have access to it."
            : "Failed to load document",
        ),
      );
  }, [docId, editor, applyServerDoc]);

  // Comments: load once, open the panel automatically if there are open threads.
  useEffect(() => {
    if (!doc) return;
    void loadComments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc?.id, loadComments]);
  useEffect(() => {
    if (autoOpenedComments.current || comments.length === 0) return;
    autoOpenedComments.current = true;
    if (comments.some((c) => !c.resolved) && window.innerWidth > 1100) setPanel((p) => p ?? "comments");
  }, [comments]);

  // Poll: collaborators' saves, comments, and presence heartbeat.
  useEffect(() => {
    if (!doc) return;
    let cancelled = false;
    const tick = async () => {
      if (document.hidden) return;
      try {
        const editing = canEdit && Date.now() - lastLocalEdit.current < EDITING_WINDOW_MS;
        const { others: here } = await api.heartbeat(docId, editing);
        if (!cancelled) setOthers(here);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setLoadError("This document was deleted or your access was removed.");
          return;
        }
      }
      void loadComments();
      if (saving.current || isDirty() || statusRef.current === "conflict") return;
      try {
        const latest = await api.getDoc(docId);
        if (cancelled) return;
        if (latest.version > versionRef.current && !isDirty()) {
          applyServerDoc(latest);
          setNotice("Updated with the latest changes from a collaborator.");
          window.setTimeout(() => setNotice(null), 3000);
        } else if (latest.role !== doc.role) {
          setDoc(latest);
          editor?.setEditable(latest.role === "owner" || latest.role === "editor", false);
        }
      } catch {
        /* next tick retries */
      }
    };
    void tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc?.id, doc?.role, docId, editor, applyServerDoc, loadComments, canEdit]);

  // Leave presence when the page goes away.
  useEffect(() => {
    const onHide = () => api.leave(docId);
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      api.leave(docId);
    };
  }, [docId]);

  // Capture the selected text so it can be quoted in a new comment.
  useEffect(() => {
    if (!editor || !canComment) return;
    const onSelection = () => {
      if (Date.now() < suppressQuoteUntil.current) return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.anchorNode || !editor.view.dom.contains(sel.anchorNode)) return;
      const text = sel.toString().replace(/\s+/g, " ").trim().slice(0, 500);
      if (text) setPendingQuote(text);
    };
    document.addEventListener("selectionchange", onSelection);
    return () => document.removeEventListener("selectionchange", onSelection);
  }, [editor, canComment]);

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

  const jumpTo = (quote: string): boolean => {
    if (!editor) return false;
    const range = findQuote(editor, quote);
    if (!range) return false;
    suppressQuoteUntil.current = Date.now() + 400;
    const { view } = editor;
    const start = view.domAtPos(range.from);
    const end = view.domAtPos(range.to);
    const dom = document.createRange();
    dom.setStart(start.node, start.offset);
    dom.setEnd(end.node, end.offset);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(dom);
    const el = start.node.nodeType === Node.TEXT_NODE ? start.node.parentElement : (start.node as Element);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    return true;
  };

  const resolveConflict = async (keepMine: boolean) => {
    const latest = await api.getDoc(docId);
    if (keepMine) {
      setVersion(latest.version);
      setStatus("unsaved");
      statusRef.current = "unsaved";
      await flush();
    } else {
      applyServerDoc(latest);
      setStatus("saved");
    }
  };

  const prepareRestore = async () => {
    await flush();
    return versionRef.current;
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

  const togglePanel = (p: Exclude<Panel, null>) => setPanel((cur) => (cur === p ? null : p));
  const openCount = comments.filter((c) => !c.resolved).length;

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
            readOnly={!canEdit}
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
                Shared by {doc.owner.name} · <span className={`badge ${doc.role}`}>{ROLE_LABEL[doc.role]}</span> ·{" "}
              </>
            )}
            {doc &&
              (canEdit ? (
                <span className={`status ${status}`}>{STATUS_TEXT[status]}</span>
              ) : (
                "Read-only"
              ))}
          </div>
        </div>
        <Presence others={others} />
        <div className="doc-actions">
          {doc && (
            <>
              <button
                className={`btn ghost ${panel === "comments" ? "active" : ""}`}
                onClick={() => togglePanel("comments")}
                aria-pressed={panel === "comments"}
              >
                💬 Comments{openCount > 0 && <span className="count">{openCount}</span>}
              </button>
              <button
                className={`btn ghost ${panel === "history" ? "active" : ""}`}
                onClick={() => togglePanel("history")}
                aria-pressed={panel === "history"}
              >
                ⟲ History
              </button>
              <details className="menu">
                <summary className="btn ghost">Export ▾</summary>
                <div className="menu-list">
                  <a href={api.exportUrl(docId, "pdf")} download>
                    PDF document (.pdf)
                  </a>
                  <a href={api.exportUrl(docId, "md")} download>
                    Markdown (.md)
                  </a>
                </div>
              </details>
            </>
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

      {editor && canEdit && doc && <Toolbar editor={editor} />}
      <div className="editor-body">
        <div className="paper-scroll">
          <div className={`paper ${canEdit ? "" : "readonly"}`}>
            {!doc && <p className="muted">Loading…</p>}
            <EditorContent editor={editor} />
          </div>
        </div>
        {doc && panel === "comments" && (
          <CommentsPanel
            docId={docId}
            me={me}
            isOwner={doc.role === "owner"}
            canComment={canComment}
            comments={comments}
            reload={loadComments}
            pendingQuote={pendingQuote}
            clearQuote={() => setPendingQuote(null)}
            onJump={jumpTo}
            onClose={() => setPanel(null)}
          />
        )}
        {doc && panel === "history" && (
          <HistoryPanel
            docId={docId}
            docVersion={docVersion}
            canEdit={canEdit}
            prepareRestore={prepareRestore}
            onRestored={(d) => {
              applyServerDoc(d);
              setStatus("saved");
              setNotice(`Restored. The previous state is still in history.`);
              window.setTimeout(() => setNotice(null), 4000);
            }}
            onClose={() => setPanel(null)}
          />
        )}
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
