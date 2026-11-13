# Walkthrough video script (~4 min)

Setup: two browser windows side by side — normal (Alice) and private/incognito (Bob).

**0:00 – Intro (20 s)**
"This is Ajaia Docs, a lightweight collaborative editor. FastAPI + SQLite backend, React +
TipTap frontend, one container. I prioritized three things: an editor that feels finished,
sharing that's correct by construction, and a build you can actually test."

**0:20 – Editing (60 s)** — Alice
- One-click login as Alice. Point out *My documents* / *Shared with me* tabs.
- *Blank document* → rename title to "Launch plan".
- H1, bold, italic, underline, bullet list, numbered list. Point at "All changes saved".
- Refresh the page → everything is still there.

**1:20 – Import (30 s)**
- Back → *Import a file* → `samples/sample.docx` → becomes an editable doc with headings
  and lists. Mention .txt/.md/.docx, 2 MB, limits shown in UI, sanitized server-side.

**1:50 – Sharing (60 s)**
- Open "Launch plan" → *Share* → `bob@ajaia.test` as *Can view*. Show the unknown-email error.
- Bob window: login as Bob → *Shared with me* shows "View only" → open: no toolbar,
  not editable, "Shared by Alice".
- Bob opens "Welcome to Ajaia Docs" (he's an editor) and types a line. Alice's window shows
  it within ~5 s.
- (Optional) Carol sees nothing.

**2:50 – Decisions & cuts (45 s)**
- Authorization lives in one function (`access.py`); no access ⇒ 404 so existence doesn't leak.
- HTML is stored but always passes an allowlist sanitizer.
- No real-time CRDT: optimistic versioning instead — stale saves get a 409 and a
  "load theirs / keep mine" choice. Next step would be Yjs.
- Deprioritized: version history, comments, images, sign-up.

**3:35 – AI workflow (30 s)**
- Used Claude as a coding agent with a test-first loop; 36 tests + a two-user Playwright E2E.
- Give one or two examples from `AI_WORKFLOW.md` of output you changed (e.g. the SPA
  route returning 200 for unknown API paths, seed data leaking into tests).

**4:05 – Wrap**
- Point to README / SUBMISSION.md and the test accounts.
