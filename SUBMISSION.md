# Submission — Ajaia Docs

**Live app:** `<PASTE DEPLOYED URL HERE>`
**Walkthrough video:** see `VIDEO_URL.txt`

## Test accounts (password for all: `demo1234`)

- `alice@ajaia.test` — owns "Welcome to Ajaia Docs"
- `bob@ajaia.test` — has edit access to Alice's welcome doc
- `carol@ajaia.test` — no access to anything (isolation check)

The login page has one-click buttons for each account. Use two browsers (or one normal + one
private window) to see sharing and cross-user updates side by side.

## What's included

| Item | Path |
|---|---|
| Source code — backend (FastAPI) | `backend/` |
| Source code — frontend (React + TipTap) | `frontend/` |
| Automated tests (36 pytest) | `backend/tests/` |
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
import `.txt`/`.md`/`.docx` as a new doc (2 MB max), sharing with viewer/editor roles,
role change and revoke, owned vs shared lists, version-conflict detection, polling for
collaborators' saves, Markdown export.

**Stretch items done:** role-based sharing (viewer/editor), export to Markdown.

**Partial / intentionally not built:** real-time character-level co-editing (conflicts are
detected and resolved by choice, not merged), version history, comments, images/tables,
sign-up/password reset, Postgres.

**Next 2–4 hours:** Yjs real-time collaboration with presence; version history with
restore; Postgres + migrations; login rate limiting and CSRF token.
