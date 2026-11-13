# Ajaia Docs — a lightweight collaborative document editor

A focused Google-Docs-style slice: create, edit (rich text), rename, import files, share with
other users as **viewer** or **editor**, and reopen everything after a refresh.

- **Live app:** _see `SUBMISSION.md`_
- **Stack:** Python 3.11+ · FastAPI · SQLAlchemy · SQLite — React 19 · TypeScript · TipTap (ProseMirror) · Vite
- **One container:** the FastAPI app serves both the JSON API (`/api/*`) and the built SPA.

## Demo accounts

All seeded on first boot. Password for every account: **`demo1234`**
(the login screen also has one-click buttons).

| User | Email | Starts with |
|---|---|---|
| Alice Chen | `alice@ajaia.test` | Owns "Welcome to Ajaia Docs" |
| Bob Rivera | `bob@ajaia.test` | Has **edit** access to Alice's welcome doc |
| Carol Okafor | `carol@ajaia.test` | Nothing — use her to verify isolation |

**2-minute review path:** sign in as Alice → create a doc, format it → *Share* → add
`bob@ajaia.test` as *Can view* → sign out → sign in as Bob → *Shared with me* tab shows it as
"View only" and the editor is read-only → open the welcome doc (Bob can edit) and type →
Alice's open copy picks up the change within ~5 s. Carol sees neither document.

## Features

| Area | What works |
|---|---|
| Editing | Bold, italic, underline, strikethrough, H1–H3, bulleted & numbered lists, quote, undo/redo, clear formatting, keyboard shortcuts |
| Documents | Create, rename (inline title), autosave (800 ms debounce) with saved/saving status, reopen, delete (owner), export to Markdown |
| File import | `.txt`, `.md`/`.markdown`, `.docx` → new editable document, **max 2 MB**. Limits shown in the UI. Samples in `samples/` |
| Sharing | Owner shares by email as *viewer* or *editor*, changes role, revokes. "My documents" vs "Shared with me" tabs, role badges |
| Concurrency | Optimistic versioning: a stale save returns **409** and the UI offers *Load their version* / *Keep mine*. Idle editors poll every 5 s for collaborators' saves |
| Security | Server-side HTML allowlist sanitization (nh3) on every write and import, 404 (not 403) for documents you can't see, scrypt password hashes, signed HttpOnly SameSite cookies, random doc IDs, upload size/type/magic-byte checks |

## Run locally

Prereqs: Python 3.11+ and Node 20+.

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:create_app --factory --reload --port 8000

# 2. Frontend (second terminal) — Vite proxies /api to :8000
cd frontend
npm ci
npm run dev            # open http://localhost:5173
```

Production-style single process (what the deployment runs):

```bash
cd frontend && npm ci && npm run build && cd ..
cd backend && STATIC_DIR=../frontend/dist uvicorn app.main:create_app --factory --port 8000
# open http://localhost:8000
```

Or with Docker: `docker build -t ajaia-docs . && docker run -p 8000:8000 -v ajaia-data:/data ajaia-docs`

The SQLite file is created at `backend/data/ajaia.db` (or `/data/ajaia.db` in Docker). Delete it to reset to seed data.

### Configuration (env vars)

| Var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/ajaia.db` | Any SQLAlchemy URL |
| `SECRET_KEY` | random per boot | **Set in production**, otherwise sessions reset on restart |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS |
| `SEED_DEMO_USERS` / `SEED_SAMPLE_CONTENT` | `true` | Demo accounts and the shared welcome doc |
| `MAX_UPLOAD_BYTES` / `MAX_CONTENT_BYTES` | 2 MB / 1 MB | Upload and document size limits |
| `STATIC_DIR` | unset | Path to built SPA; when set, FastAPI serves it |

## Tests

```bash
cd backend && pytest                 # 36 API/unit tests, ~5 s
cd frontend && npm run typecheck     # strict TypeScript
# Browser E2E (server running on :8000 with a fresh DB):
pip install playwright && playwright install chromium
python e2e/smoke_test.py http://localhost:8000
```

The most important file is `backend/tests/test_sharing_isolation.py`: it proves that a user
without a grant cannot read, list, edit, export, delete, or manage shares on another user's
document, and that viewer/editor/owner permissions are enforced server-side.

The E2E script drives two real browser sessions (Alice and Bob) through create → format →
reload → share → import → read-only view → cross-user edit propagation, and saves the
screenshots in `docs/screenshots/`.

## Deploy

The repo is a single Dockerfile, so any container host works. Two tested-by-config paths:

- **Railway (CLI, no GitHub needed):** `railway login && railway init && railway up`, then in
  the service settings add a Volume mounted at `/data`, set `SECRET_KEY` (any long random
  string) and `COOKIE_SECURE=true`, and *Generate Domain*. `railway.json` sets the health check.
- **Render (free):** push to GitHub → Render → *New → Blueprint* → select the repo
  (`render.yaml`). Note: the free plan has no persistent disk, so data resets when the
  instance restarts/redeploys (demo users are re-seeded automatically).

## Project layout

```
backend/app/
  access.py       # the ONE place document permissions are decided
  sanitize.py     # HTML allowlist used for every write
  importers.py    # .txt/.md/.docx → HTML
  routers/        # auth + documents/sharing HTTP layer
  models.py, schemas.py, security.py, seed.py, main.py
backend/tests/    # pytest suite (TDD)
frontend/src/     # React app: Login, DocList, EditorPage, Toolbar, ShareDialog
e2e/              # Playwright smoke test
samples/          # files to try the importer with
```

See `ARCHITECTURE.md` for decisions and trade-offs and `AI_WORKFLOW.md` for how AI was used.
