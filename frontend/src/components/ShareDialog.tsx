import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type Share, type ShareRole, type User } from "../api";

interface Props {
  docId: string;
  owner: User;
  initial: Share[];
  onClose: (shares: Share[]) => void;
}

export default function ShareDialog({ docId, owner, initial, onClose }: Props) {
  const [shares, setShares] = useState<Share[]>(initial);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ShareRole>("editor");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose(shares);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, shares]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const add = (ev: FormEvent) => {
    ev.preventDefault();
    if (!email.trim()) return setError("Enter an email address");
    void run(async () => {
      await api.share(docId, email.trim(), role);
      setShares(await api.listShares(docId));
      setEmail("");
    });
  };

  const changeRole = (s: Share, r: ShareRole) =>
    run(async () => {
      await api.share(docId, s.user.email, r);
      setShares(await api.listShares(docId));
    });

  const revoke = (s: Share) =>
    run(async () => {
      await api.revoke(docId, s.user.id);
      setShares((prev) => prev.filter((x) => x.user.id !== s.user.id));
    });

  return (
    <div className="modal-backdrop" onMouseDown={() => onClose(shares)}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Share document" onMouseDown={(e) => e.stopPropagation()}>
        <h2>Share document</h2>
        <form className="share-form" onSubmit={add}>
          <input
            autoFocus
            type="email"
            placeholder="Add people by email, e.g. bob@ajaia.test"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <select value={role} onChange={(e) => setRole(e.target.value as ShareRole)} aria-label="Access level">
            <option value="editor">Can edit</option>
            <option value="commenter">Can comment</option>
            <option value="viewer">Can view</option>
          </select>
          <button className="btn primary" disabled={busy}>
            Share
          </button>
        </form>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <h3 className="muted small">People with access</h3>
        <ul className="people">
          <li>
            <span className="avatar">{owner.name[0]}</span>
            <span className="person">
              {owner.name}
              <span className="muted small">{owner.email}</span>
            </span>
            <span className="muted">Owner</span>
          </li>
          {shares.map((s) => (
            <li key={s.user.id}>
              <span className="avatar">{s.user.name[0]}</span>
              <span className="person">
                {s.user.name}
                <span className="muted small">{s.user.email}</span>
              </span>
              <select
                value={s.role}
                disabled={busy}
                onChange={(e) => changeRole(s, e.target.value as ShareRole)}
                aria-label={`Access for ${s.user.name}`}
              >
                <option value="editor">Can edit</option>
                <option value="commenter">Can comment</option>
                <option value="viewer">Can view</option>
              </select>
              <button className="link danger" disabled={busy} onClick={() => revoke(s)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
        <div className="modal-actions">
          <button className="btn primary" onClick={() => onClose(shares)}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
