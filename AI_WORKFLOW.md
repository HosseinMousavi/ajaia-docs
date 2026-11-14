# AI-native workflow note

> Draft written from the build log. **Edit this to reflect your own experience before
> submitting** — reviewers will ask about it in the walkthrough.

## Tools used

- **Claude (Anthropic) as an agentic coding assistant** — scaffolding, implementation,
  running tests, driving a headless browser for E2E checks, and drafting docs.
- **pytest, TypeScript strict mode, Playwright** — the verification layer. AI output was
  only accepted once these passed.

## Where AI materially sped things up

- **Boilerplate at full speed:** FastAPI routers, Pydantic schemas, SQLAlchemy models,
  the React components and CSS — hours of typing reduced to review.
- **Test-first loop:** the test files were written before the implementation (the first
  run failed with `ModuleNotFoundError`, as intended), then the implementation was iterated
  until all tests passed.
- **Library lookups:** TipTap v3 API changes (StarterKit now bundles Underline/Link,
  `setContent(html, { emitUpdate })`), nh3 options, mammoth for .docx.
- **E2E automation:** a two-user Playwright script that also produced the screenshots.

## What I changed or rejected

Concrete examples from this build:

| AI output | Problem | What I did |
|---|---|---|
| Added `@tiptap/extension-underline` alongside StarterKit | TipTap v3 StarterKit already includes Underline → duplicate-extension warning | Removed the package |
| Seeded a shared "Welcome" doc for every environment | Leaked into test fixtures and broke 3 listing assertions | Split `SEED_SAMPLE_CONTENT` from `SEED_DEMO_USERS`; tests run without sample content, plus a dedicated test that the sample *is* seeded |
| SPA catch-all route | Answered unknown `/api/*` paths with `index.html` and **HTTP 200** — hides client bugs | Wrote a failing test, then returned JSON 404 for `/api/*` |
| A stray "lazy app" line at the end of `main.py` | Dead/confusing code | Deleted; uvicorn uses `--factory` |
| `node:22-alpine` build image | Native binaries in Vite 8 / TS 7 are riskier on musl | Switched to `node:22-slim`; separated `typecheck` from `build` |
| Deployment on Render free with SQLite | Render's free disk is wiped when the instance sleeps — reviewers' documents would vanish | Added Postgres (Neon) support test-first, ran the full suite + E2E against Postgres, verified data survives a server restart |
| Deprecated `HTTP_413_REQUEST_ENTITY_TOO_LARGE` | Warnings in test output | Switched to `HTTP_413_CONTENT_TOO_LARGE` |

Judgment calls I kept for myself: the scope cuts (no CRDT real-time, no version history),
returning **404 instead of 403** for inaccessible docs, storing sanitized HTML rather than
JSON, and optimistic versioning instead of last-write-wins.

## How I verified correctness, UX and reliability

1. **42 backend tests**, run against both SQLite and a real Postgres 16 — especially `test_sharing_isolation.py` (a third user, Carol,
   must never see Alice's document through any endpoint) and XSS sanitization tests.
2. **Playwright E2E** with two browser contexts: create → format → reload persistence →
   share as viewer → import → read-only enforcement → cross-user edit propagation.
3. **Looked at the screenshots** rather than trusting green tests — this caught an
   unstyled blue "Export .md" link.
4. **Clean-room build:** `npm ci` + build and a fresh virtualenv from `requirements.txt`,
   then ran the exact production command to confirm health, SPA routing and assets.
5. Manual pass over each flow in the deployed app.
