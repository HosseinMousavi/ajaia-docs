import { useState, type FormEvent } from "react";
import { api, ApiError, avatarColor, timeAgo, type Comment, type User } from "../api";

interface Props {
  docId: string;
  me: User;
  isOwner: boolean;
  canComment: boolean;
  comments: Comment[];
  reload: () => Promise<void>;
  pendingQuote: string | null;
  clearQuote: () => void;
  onJump: (quote: string) => boolean;
  onClose: () => void;
}

function Avatar({ user }: { user: User }) {
  return (
    <span className="cav" style={{ background: avatarColor(user.id) }} aria-hidden>
      {user.name[0]}
    </span>
  );
}

export default function CommentsPanel(props: Props) {
  const { docId, me, isOwner, canComment, comments, reload, pendingQuote, clearQuote, onJump, onClose } = props;
  const [filter, setFilter] = useState<"open" | "resolved">("open");
  const [body, setBody] = useState("");
  const [replies, setReplies] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState<number | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    if (!body.trim()) return;
    void run(async () => {
      await api.addComment(docId, body.trim(), { quote: pendingQuote });
      setBody("");
      clearQuote();
      setFilter("open");
    });
  };

  const reply = (thread: Comment) => {
    const text = (replies[thread.id] ?? "").trim();
    if (!text) return;
    void run(async () => {
      await api.addComment(docId, text, { parent_id: thread.id });
      setReplies((r) => ({ ...r, [thread.id]: "" }));
    });
  };

  const remove = (c: Comment) => {
    if (window.confirm(c.parent_id ? "Delete this reply?" : "Delete this comment and its replies?")) {
      void run(() => api.deleteComment(docId, c.id));
    }
  };

  const open = comments.filter((c) => !c.resolved);
  const resolved = comments.filter((c) => c.resolved);
  const shown = filter === "open" ? open : resolved;

  const renderComment = (c: Comment) => (
    <div className="c-item" key={c.id}>
      <div className="c-head">
        <Avatar user={c.author} />
        <span className="c-author">{c.author.id === me.id ? "You" : c.author.name}</span>
        <span className="muted small">{timeAgo(c.created_at)}</span>
        {(c.author.id === me.id || isOwner) && (
          <button className="link danger small c-del" onClick={() => remove(c)} disabled={busy} aria-label="Delete comment">
            Delete
          </button>
        )}
      </div>
      {/* Rendered as text, never HTML. */}
      <p className="c-body">{c.body}</p>
    </div>
  );

  return (
    <aside className="side-panel" aria-label="Comments">
      <div className="panel-head">
        <h2>Comments</h2>
        <button className="btn ghost" onClick={onClose} aria-label="Close comments">
          ✕
        </button>
      </div>

      {canComment ? (
        <form className="c-new" onSubmit={submit}>
          {pendingQuote ? (
            <div className="c-quote pending">
              <span>“{pendingQuote}”</span>
              <button type="button" className="link small" onClick={clearQuote} aria-label="Remove quoted text">
                ✕
              </button>
            </div>
          ) : (
            <div className="muted small">Tip: select text in the document to comment on it.</div>
          )}
          <textarea
            placeholder={pendingQuote ? "Comment on the selected text…" : "Add a comment…"}
            value={body}
            maxLength={2000}
            rows={3}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
            }}
          />
          <button className="btn primary" disabled={busy || !body.trim()}>
            Comment
          </button>
        </form>
      ) : (
        <p className="muted small">You have view-only access, so you can read comments but not add them.</p>
      )}

      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}

      <div className="seg" role="tablist">
        <button role="tab" aria-selected={filter === "open"} className={filter === "open" ? "on" : ""} onClick={() => setFilter("open")}>
          Open <span className="count">{open.length}</span>
        </button>
        <button role="tab" aria-selected={filter === "resolved"} className={filter === "resolved" ? "on" : ""} onClick={() => setFilter("resolved")}>
          Resolved <span className="count">{resolved.length}</span>
        </button>
      </div>

      {shown.length === 0 && (
        <p className="muted small empty-panel">{filter === "open" ? "No open comments." : "Nothing resolved yet."}</p>
      )}

      <ul className="threads">
        {shown.map((t) => (
          <li key={t.id} className={`thread ${t.resolved ? "resolved" : ""}`}>
            {t.quote && (
              <button
                className="c-quote"
                title="Show in document"
                onClick={() => setMissing(onJump(t.quote!) ? null : t.id)}
              >
                “{t.quote}”
              </button>
            )}
            {missing === t.id && <div className="muted small">That text is no longer in the document.</div>}
            {renderComment(t)}
            {t.replies.map(renderComment)}
            {canComment && (
              <div className="c-actions">
                {!t.resolved && (
                  <input
                    className="c-reply"
                    placeholder="Reply…"
                    value={replies[t.id] ?? ""}
                    maxLength={2000}
                    onChange={(e) => setReplies((r) => ({ ...r, [t.id]: e.target.value }))}
                    onKeyDown={(e) => e.key === "Enter" && reply(t)}
                  />
                )}
                <button
                  className="btn small-btn"
                  disabled={busy}
                  onClick={() => run(() => api.resolveComment(docId, t.id, !t.resolved))}
                >
                  {t.resolved ? "Reopen" : "✓ Resolve"}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
