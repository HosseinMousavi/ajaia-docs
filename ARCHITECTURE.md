# Architecture note

## What I optimized for

The brief rewards depth over breadth, so I picked three things to make solid and kept
everything else deliberately small:

1. **An editor that feels finished**, not a textarea with buttons: real rich-text model
   (TipTap/ProseMirror), active-state toolbar, keyboard shortcuts, autosave with visible
   status, and no silent data loss.
2. **Access control that is correct by construction**, because sharing is where a document
   product leaks data. One function decides every permission, and it is the most-tested
   code in the repo.
3. **A build reviewers can actually run**: one container, zero paid services, seeded users,
   one-click demo login.

## Shape of the system

```
Browser (React + TipTap)  ──JSON over /api, HttpOnly cookie──▶  FastAPI
                                                                 ├─ routers/   (HTTP only)
                                                                 ├─ access.py  (authorization)
                                                                 ├─ sanitize.py / importers.py
                                                                 └─ SQLAlchemy ─▶ SQLite
```

One process serves the API and the static SPA, so there's no CORS and only one thing to
deploy. The database URL is configurable; nothing is SQLite-specific apart from two PRAGMAs,
so moving to Postgres is a config change plus migrations.

**Data model:** `users`, `documents` (owner_id, title, content_html, version, timestamps),
`document_shares` (document_id, user_id, role ∈ {viewer, editor}, unique per pair, cascades on
delete). Document IDs are random UUIDs so they can't be enumerated.

## Key decisions and trade-offs

| Decision | Why | Cost / what I gave up |
|---|---|---|
| **Store sanitized HTML**, not ProseMirror JSON | Imports (Markdown, .docx) produce HTML naturally; HTML is portable for export; one format end to end | Schema is less strict than JSON. Mitigated by a server-side **allowlist** (nh3) on *every* write and import, so stored content can only contain the tags the editor supports |
| **Authorization in one choke point** (`access.load_document`) | Routes can't forget a check: they can't get a document *except* through it. Users with no access get **404**, not 403, so document existence doesn't leak | Slightly more ceremony than inline checks |
| **Roles: owner / editor / viewer** | Small step past the minimum that makes sharing realistic (the stretch item) and exercises the permission matrix | No re-sharing by editors, no link sharing, no groups |
| **Optimistic concurrency** (`version` + `base_version`, 409 on mismatch) instead of real-time CRDT | Real-time co-editing (Yjs + websockets) is the right long-term answer but is a multi-day feature to do well. Versioning guarantees no silent overwrites today | Two people typing at the same moment get a conflict banner rather than a merge. Idle viewers poll every 5 s to pick up saves |
| **Seeded users + signed-cookie sessions** | Brief allows mocked auth; real password hashing (scrypt) and HttpOnly/SameSite=Lax cookies cost little and avoid demo-only shortcuts like user-id headers | No sign-up, password reset, or SSO |
| **Import creates a new document** | Clearest product behavior; supports the most common formats (.txt, .md, .docx via mammoth) | No PDF/Google Docs import; no attachments; images in .docx are dropped by the sanitizer |
| **SQLite** | Zero-ops, file-based, fine for a single instance | One writer at a time; on Render free the disk is ephemeral (documented) |

## Security / privacy posture (sized to the scope)

- HTML sanitized server-side with an allowlist (no scripts, event handlers, `javascript:` URLs,
  images, iframes); plain-text import is HTML-escaped.
- Uploads: extension allowlist, size limit enforced while reading (no unbounded reads),
  .docx must be a real zip, text must be valid UTF-8.
- Tenant isolation: every document query is scoped to the caller; unauthorized ⇒ 404.
- Login returns the same error for unknown email and wrong password.
- No document content is logged; API responses are `Cache-Control: no-store`; standard
  hardening headers (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`).
- Known gaps (acceptable for a demo, listed honestly): no rate limiting on login, no CSRF
  token (relies on SameSite=Lax + JSON bodies), share-by-email reveals whether an email
  exists to document owners, no audit log.

## Testing strategy

Built test-first. **36 pytest tests** cover auth, CRUD, validation, size limits, XSS
sanitization, version conflicts, import of each format and each rejection path, the
full permission matrix, revocation, and cascade deletes. A **Playwright E2E** runs two real
browser sessions through the main flows. TypeScript runs in strict mode.

## Deliberately not built (and what I'd do next with 2–4 more hours)

1. **Real-time co-editing** with Yjs over a websocket (TipTap has first-class support);
   presence avatars and cursors would replace polling + conflict banner.
2. **Version history** — store a snapshot per N saves; restore UI.
3. **Postgres + Alembic migrations** for multi-instance deploys.
4. Login rate limiting, CSRF token, audit log of share changes.
5. Comments / suggestion mode.

Also out of scope on purpose: tables, images, page layout, PDF import, mobile-specific UI.
