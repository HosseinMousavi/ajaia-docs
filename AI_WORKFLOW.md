# AI workflow note

## Tools I used

- **Claude (Anthropic) as an agentic coding assistant.** It wrote most of the code, ran the
  tests, drove a headless browser for end-to-end checks, and drafted the docs, working
  under my direction.
- **pytest, TypeScript strict mode, Playwright, and my own manual testing** on the live
  deployment as the verification layer. I accepted AI output only once it passed these.

## How I worked with it

I treated the AI like a very fast pair programmer, not an autopilot. Before any code was
written I set the engineering constraints: Python 3.11+, strict test-driven development,
strict data isolation between users, and no leakage of personal data. I made the product
and infrastructure decisions myself (scope cuts, sharing model, hosting and database), and
used the AI to execute them and to research options quickly.

## Where AI materially sped up my work

- **Scaffolding at full speed.** The FastAPI routes, data models, React components and
  styling were hours of typing; reviewing them took a fraction of that.
- **Tests first.** The test files were written before the implementation. The first run
  failed on purpose, and the code was iterated until everything passed. That included the
  access-control tests I cared most about.
- **Library details.** Version-specific API changes in TipTap v3, the HTML sanitizer's
  options, and .docx conversion.
- **Deployment research.** Comparing free hosting tiers as they stand in late 2026: Fly.io,
  Heroku and Hugging Face Docker Spaces are no longer free, and Koyeb now requires a card.
- **End-to-end automation.** A two-user browser test that also produced the screenshots.

## What I changed, rejected, or decided myself

| Situation | Problem | What I did |
|---|---|---|
| First deployment plan: Render's free tier with SQLite | Render's free disk is wiped whenever the app sleeps, so reviewers' documents would vanish | Asked for alternatives and chose **Render + Neon Postgres** (both free, no card). Postgres support was added test-first and the full suite was run against a real Postgres 16 |
| Hosting on GitHub Pages or Streamlit Cloud | Pages only serves static files; Streamlit would mean a rewrite and a much weaker editor | Rejected both and kept the FastAPI + React architecture |
| Railway (my first choice of host) | My free trial was already used | Ruled it out and didn't create a throwaway account |
| Sample "Welcome" doc seeded in every environment | It leaked into test fixtures and broke 3 tests | Separated "seed users" from "seed sample content", plus a dedicated test that the sample *is* seeded |
| Single-page-app catch-all route | Unknown `/api/*` paths returned the HTML page with status 200, which hides client bugs | Wrote a failing test first, then made them return a JSON 404 |
| Extra TipTap underline package | TipTap v3 already includes it, which caused a duplicate-extension warning | Removed it |
| `node:22-alpine` Docker build image | Native build tools are less reliable on Alpine | Switched to `node:22-slim` and separated type-checking from the build |
| Version history: one snapshot per save | Autosave fires on every pause in typing (Bob's doc reached version 27), so history would be noise | Coalesce saves by the same person within 10 minutes; created/imported/restored snapshots are never overwritten, and a restore is itself undoable |
| Shipping new tables to the live database | Existing documents have no history; production data must survive | Documents get a "baseline" snapshot on their first edit; verified by upgrading a database created by the old release |
| Database password shown in a setup screenshot | A credential exposed in a chat transcript | Rotated it in Neon before using it. The connection string lives only in Render's environment variables, never in the repo |

## How I verified correctness, UX and reliability

1. **77 automated backend tests**, run against both SQLite and a real Postgres database.
   The key file, `test_sharing_isolation.py`, proves a user without access cannot read,
   list, edit, export, delete, or manage sharing on someone else's document.
2. **A Playwright end-to-end test** with three simultaneous users: create, format, reload,
   share, import, read-only enforcement, cross-user edits, presence, version diff + restore,
   anchored comments with reply/resolve, and PDF export.
3. **Upgrade check before shipping the stretch features.** I ran the new code against a
   database created by the previous release (as production is): the new tables were created,
   and existing documents keep their pre-upgrade content as a "baseline" version.
4. **Checks against the live deployment.** Users can't see each other's documents (404s),
   script tags are stripped on save, stale saves get a conflict, the session cookie is
   HttpOnly, security headers are set, and logout works. Test data was cleaned up afterward.
5. **My own manual testing on the live site.** As Bob I created "Bob's doc" and shared it
   with Carol as an editor, edited Alice's welcome doc, and confirmed the changes persisted
   and showed up for the other users.
6. **Looking at the screens, not just the test results.** Reviewing the screenshots caught
   an unstyled "Export .md" link and a struck-through legend label in the diff view that
   every test had passed.
