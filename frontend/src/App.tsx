import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type User } from "./api";
import Login from "./components/Login";
import DocList from "./components/DocList";
import EditorPage from "./components/EditorPage";

function useHashRoute(): [string | null, (id: string | null) => void] {
  const parse = () => {
    const m = window.location.hash.match(/^#\/doc\/([A-Za-z0-9]+)$/);
    return m ? m[1] : null;
  };
  const [docId, setDocId] = useState<string | null>(parse);
  useEffect(() => {
    const onHash = () => setDocId(parse());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const navigate = useCallback((id: string | null) => {
    window.location.hash = id ? `#/doc/${id}` : "#/";
  }, []);
  return [docId, navigate];
}

export default function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [docId, navigate] = useHashRoute();

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch((e) => setUser(e instanceof ApiError && e.status === 401 ? null : null));
  }, []);

  const logout = async () => {
    await api.logout().catch(() => undefined);
    setUser(null);
    navigate(null);
  };

  if (user === undefined) return <div className="center muted">Loading…</div>;
  if (user === null) return <Login onLogin={setUser} />;

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => navigate(null)} title="All documents">
          <span className="logo" aria-hidden>
            ▤
          </span>
          Ajaia Docs
        </button>
        <div className="spacer" />
        <span className="whoami" title={user.email}>
          <span className="avatar" aria-hidden>
            {user.name[0]}
          </span>
          {user.name}
        </span>
        <button className="btn ghost" onClick={logout}>
          Sign out
        </button>
      </header>
      {docId ? (
        <EditorPage key={docId} docId={docId} me={user} onBack={() => navigate(null)} />
      ) : (
        <DocList onOpen={navigate} />
      )}
    </div>
  );
}
