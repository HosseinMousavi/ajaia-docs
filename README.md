# Ajaia Docs — a lightweight collaborative document editor

A focused Google-Docs-style slice: create, edit (rich text), rename, import files, share with
other users as **viewer, commenter or editor**, and reopen everything after a refresh, plus
live presence, anchored comments, version history with a visual diff, and PDF/Markdown export.

- **Live app:** https://ajaia-docs-x092.onrender.com
- **Stack:** Python 3.11+ · FastAPI · SQLAlchemy · Postgres (prod, Neon) / SQLite (local) — React 19 · TypeScript · TipTap (ProseMirror) · Vite
- **One container:** the FastAPI app serves both the JSON API (`/api/*`) and the built SPA.

## Demo accounts

All seeded on first boot. Password for every account: **`demo1234`**
(the login screen also has one-click buttons).

| User | Email | Documents (live site) |
|---|---|---|
| Alice Chen | `alice@ajaia.test` | Owns "Welcome to Ajaia Docs" |
| Bob Rivera | `bob@ajaia.test` | Can **edit** Alice's welcome doc; owns "Bob's doc", shared with Carol as editor |
| Carol Okafor | `carol@ajaia.test` | Can **edit** Bob's doc; has no access to Alice's documents (isolation check) |

**2-minute review path:** sign in as Alice → create a doc, format it → *Share* → add
`bob@ajaia.test` as *Can view* → sign out → sign in as Bob → *Shared with me* tab shows it as
"View only" and the editor is read-only → open the welcome doc (Bob can edit) and type →
Alice's open copy picks up the change within ~5 s. Sign in as Carol: she sees Bob's doc
under *Shared with me* but none of Alice's documents.

**Collaboration features (1 more minute):** open a doc in two windows (Alice + Bob) to see
live presence avatars → select text as Carol on a doc shared with her as *Can comment* and add
a comment → reply/resolve as the owner → open **History**, click an older version to see a
red/green diff, and **Restore** it → **Export ▾ → PDF**.

A fresh local database is seeded with the three users and the welcome doc only.

## Features

| Area | What works |
|---|---|
| Editing | Bold, italic, underline, strikethrough, H1–H3, bulleted & numbered lists, quote, undo/redo, clear formatting, keyboard shortcuts |
| Documents | Create, rename (inline title), autosave (800 ms debounce) with saved/saving status, reopen, delete (owner) |
| File import | `.txt`, `.md`/`.markdown`, `.docx` → new editable document, **max 2 MB**. Limits shown in the UI. Samples in `samples/` |
| Sharing (roles) | Owner shares by email as **viewer**, **commenter** or **editor**, changes role, revokes. "My documents" vs "Shared with me" tabs, role badges. Matrix: viewer reads · commenter reads + comments · editor + edits · owner + shares/deletes |
| Live presence | Avatars of everyone else in the document right now, with "viewing" / "editing" status (5 s heartbeat, 15 s expiry) |
| Comments | Select text → comment on it (the quote is stored with the comment; clicking it jumps to the text). Replies, resolve/reopen, open/resolved tabs. Authors delete their own comments; the owner can moderate any |
| Version history | Automatic snapshots (saves by the same person within 10 min are grouped). Click a version to see a **word-level diff** against the current text (green = would come back, red = would be removed) and **restore** it; the restore is itself a new version, so nothing is ever lost |
| Export | **PDF** (rendered server-side) and **Markdown** |
| Concurrency | Optimistic versioning: a stale save (or restore) returns **409** and the UI offers *Load their version* / *Keep mine*. Idle editors poll every 5 s for collaborators' saves |
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
| `DATABASE_URL` | `sqlite:///./data/ajaia.db` | SQLite or Postgres. `postgres://…` / `postgresql://…` URLs (Neon, Supabase) are accepted as-is |
| `SECRET_KEY` | random per boot | **Set in production**, otherwise sessions reset on restart |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS |
| `SEED_DEMO_USERS` / `SEED_SAMPLE_CONTENT` | `true` | Demo accounts and the shared welcome doc |
| `MAX_UPLOAD_BYTES` / `MAX_CONTENT_BYTES` | 2 MB / 1 MB | Upload and document size limits |
| `STATIC_DIR` | unset | Path to built SPA; when set, FastAPI serves it |

## Tests

```bash
cd backend && pytest                 # 77 API/unit tests, ~12 s (SQLite)
TEST_DATABASE_URL=postgresql://user@localhost/ajaia_test pytest   # same suite on Postgres
cd frontend && npm run typecheck     # strict TypeScript
# Browser E2E (server running on :8000 with a fresh DB):
pip install playwright && playwright install chromium
python e2e/smoke_test.py http://localhost:8000
```

The most important file is `backend/tests/test_sharing_isolation.py`: it proves that a user
without a grant cannot read, list, edit, export, delete, or manage shares on another user's
document, and that viewer/editor/owner permissions are enforced server-side.

The E2E script drives three real browser sessions (Alice, Bob, Carol) through create →
format → reload → share → import → read-only view → cross-user edit propagation → presence →
history diff + restore → anchored comment, reply, resolve → PDF export, and saves the
screenshots in `docs/screenshots/`.

## Deploy (free: Render + Neon)

Production runs on **Render's free web service** (Docker) with a **Neon free Postgres**
database (no credit card). Render's free disk is wiped whenever the instance sleeps, so
the database must live outside the container.

1. **Neon:** sign up at neon.com → create a project → copy the connection string
   (`postgresql://…?sslmode=require`).
2. **GitHub:** push this repo.
3. **Render:** *New → Blueprint* → select the repo → paste the Neon string into
   `DATABASE_URL` when prompted → *Apply*. `render.yaml` generates `SECRET_KEY`, sets
   `COOKIE_SECURE=true` and the `/api/health` check.

Tables and demo users are created automatically on first boot (idempotent). Free-tier
caveat: the Render service sleeps after ~15 min idle, so the first request takes 30–60 s.

Any other Docker host works too (`railway.json` is included for Railway).

## Project layout

```
backend/app/
  access.py       # the ONE place document permissions are decided
  sanitize.py     # HTML allowlist used for every write
  importers.py    # .txt/.md/.docx → HTML
  exporters.py    # Markdown + PDF
  versions.py     # snapshot coalescing / baseline / restore
  diff.py         # word-level diff for the history preview
  presence.py     # in-memory "who's here" tracker with TTL
  routers/        # auth, documents/sharing, collab (comments, versions, presence)
  models.py, schemas.py, security.py, seed.py, main.py
backend/tests/    # pytest suite (TDD)
frontend/src/     # React app: Login, DocList, EditorPage, Toolbar, ShareDialog,
                  #   Presence, CommentsPanel, HistoryPanel
e2e/              # Playwright smoke test
samples/          # files to try the importer with
```

See `ARCHITECTURE.md` for decisions and trade-offs and `AI_WORKFLOW.md` for how AI was used.
