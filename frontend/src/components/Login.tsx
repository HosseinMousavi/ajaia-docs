import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type User } from "../api";

const DEMO_PASSWORD = "demo1234";

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<{ email: string; name: string }[]>([]);

  useEffect(() => {
    api.demoUsers().then(setDemo).catch(() => setDemo([]));
  }, []);

  const doLogin = async (e: string, p: string) => {
    setBusy(true);
    setError(null);
    try {
      onLogin(await api.login(e, p));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server");
    } finally {
      setBusy(false);
    }
  };

  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    if (!email.trim() || !password) return setError("Enter your email and password");
    void doLogin(email, password);
  };

  return (
    <div className="login-wrap">
      <form className="card login" onSubmit={submit}>
        <h1>
          <span className="logo" aria-hidden>
            ▤
          </span>{" "}
          Ajaia Docs
        </h1>
        <p className="muted">Sign in to create, edit and share documents.</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <button className="btn primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>

        {demo.length > 0 && (
          <div className="demo">
            <div className="muted small">
              Demo accounts (password <code>{DEMO_PASSWORD}</code>) — one click to sign in:
            </div>
            <div className="demo-list">
              {demo.map((u) => (
                <button
                  type="button"
                  key={u.email}
                  className="btn"
                  disabled={busy}
                  onClick={() => doLogin(u.email, DEMO_PASSWORD)}
                >
                  {u.name}
                  <span className="muted small"> {u.email}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
