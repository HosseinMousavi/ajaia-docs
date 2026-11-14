# Submission — Ajaia Docs

**Live app:** https://ajaia-docs-x092.onrender.com
**Walkthrough video:** see `VIDEO_URL.txt`

## Test accounts (password for all: `demo1234`)

- `alice@ajaia.test` — owns "Welcome to Ajaia Docs"
- `bob@ajaia.test` — can edit Alice's welcome doc; owns "Bob's doc", shared with Carol as editor
- `carol@ajaia.test` — can edit Bob's doc; no access to Alice's documents (isolation check)

Hosted on Render's free tier: if the app has been idle, the first load takes 30–60 s
while it wakes up. Data is stored in Postgres (Neon) and persists across restarts.

The login page has one-click buttons for each account. Use two browsers (or one normal + one
private window) to see sharing and cross-user updates side by side.

## What's included

| Item | Path |
|---|---|
| Source code — backend (FastAPI) | `backend/` |
| Source code — frontend (React + TipTap) | `frontend/` |
| Automated tests (77 pytest, SQLite + Postgres) | `backend/tests/` |
| Browser E2E test (Playwright) | `e2e/smoke_test.py` |
| Setup & run instructions | `README.md` |
| Architecture note | `ARCHITECTURE.md` |
| AI workflow note | `AI_WORKFLOW.md` |
| Walkthrough video link | `VIDEO_URL.txt` |
| Screenshots of every main flow | `docs/screenshots/` |
| Sample files for upload | `samples/` (.txt, .md, .docx) |
| Deployment config | `Dockerfile`, `railway.json`, `render.yaml` |
| This file | `SUBMISSION.md` |

## Status

**Working end to end:** login (seeded users), create, rename, rich-text editing (bold, italic,
underline, strike, H1–H3, bulleted/numbered lists, quote), autosave + reopen, delete,
import `.txt`/`.md`/`.docx` as a new doc (2 MB max), sharing with roles, role change and
revoke, owned vs shared lists, version-conflict detection, polling for collaborators' saves.

**Stretch items — all five done:**

| Stretch item | What's built |
|---|---|
| Real-time collaboration indicators | Live presence avatars with "viewing" / "editing" status |
| Commenting | Comments anchored to selected text, replies, resolve/reopen, moderation |
| Document version history | Automatic coalesced snapshots, preview, one-click restore |
| Export to PDF or Markdown | Both: server-rendered PDF and Markdown |
| Role-based sharing beyond basic access | Four roles: owner, editor, **commenter**, viewer |

**Plus one extra:** a **visual word-level diff** in version history, so you can see exactly
what restoring a version would bring back (green) or remove (red) before you click Restore.

**Partial / intentionally not built:** real-time character-level co-editing (conflicts are
detected and resolved by choice, not merged), suggestion mode (tracked changes),
images/tables, sign-up/password reset, database migrations.

**Next 2–4 hours:** Yjs real-time co-editing with live cursors; suggestion mode on top of the
snapshot/diff machinery; Alembic migrations; login rate limiting and CSRF token.
