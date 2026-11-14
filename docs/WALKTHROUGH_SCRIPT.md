# Walkthrough video script (~5 min)

**Before recording:** open https://ajaia-docs-x092.onrender.com a minute early to wake it.
Three windows: **Alice** (normal), **Bob** (private/incognito), **Carol** (a second browser,
or another private window profile). Have `samples/sample.docx` ready.

## 0:00 – Intro (20 s)
> "Hi, I'm Hossein. This is Ajaia Docs, a lightweight collaborative document editor:
> a FastAPI backend with Postgres, a React frontend using TipTap for rich text, deployed as
> one Docker container on Render with a Neon database. I focused on an editor that feels
> finished, sharing that's secure by design, and collaboration features on top."

## 0:20 – Editing + import (60 s) · Alice
- Click **Alice Chen** → **Blank document** → rename "Q4 launch plan".
- H1 "Q4 launch plan", bold "Ship by Friday.", a bullet list, a numbered list.
> "Headings, bold, italic, underline, bulleted and numbered lists, keyboard shortcuts.
> It autosaves when I pause; you can see 'All changes saved'."
- Refresh.
> "After a refresh it's all still there, because it's stored in Postgres."
- Back → **Import a file** → `sample.docx`.
> "Uploads: text, Markdown or Word, up to 2 MB, become a new editable doc. Everything is
> sanitized on the server, so no scripts or unsafe HTML get stored."

## 1:20 – Sharing with roles (45 s)
- Open "Q4 launch plan" → **Share** → `bob@ajaia.test` **Can edit**, `carol@ajaia.test`
  **Can comment**.
> "Four roles: viewer, commenter, editor and owner. Every permission is enforced on the
> server through one function, and if you have no access you get 'not found', so we don't
> even reveal the document exists."
- Carol window → **Shared with me** → open it.
> "Carol can comment: there's no toolbar, so she can read and comment but not edit."

## 2:05 – Presence + comments (60 s)
- Bob opens the doc too. Point at Alice's header.
> "Live presence: Alice sees who else is here, and whether they're viewing or editing."
- Carol: select "Ship by Friday." → **Comments** → "Is Friday a hard deadline?" → Comment.
> "Carol selects text and comments on it. The comment keeps the quote."
- Alice: the comment appears → click the yellow quote (jumps to the text) → reply "Yes,
  launch is locked." → **Resolve**.
> "Alice sees it within a few seconds, clicks the quote to jump to the text, replies, and
> resolves the thread."

## 3:05 – Version history + diff + PDF (50 s)
- Bob types a line in the doc. Alice → **History** → click the earlier version.
> "Version history is automatic. Saves by the same person within ten minutes are grouped,
> so it isn't noise. And my extra feature: a word-level diff of what restoring would do.
> Green comes back, red goes away."
- **Restore this version**.
> "Restoring is itself a new version, so even a restore can be undone."
- **Export ▾ → PDF**, open the file.
> "Export as a server-rendered PDF or as Markdown."

## 3:55 – Decisions & cuts (35 s)
> "Deliberate cuts: no real-time character-level co-editing. Doing that properly with
> something like Yjs is days of work. Instead every save carries a version number, and a
> conflicting save gets a prompt instead of silently overwriting. I also skipped suggestion
> mode, images and sign-up. Next would be Yjs co-editing with live cursors."

## 4:30 – AI workflow (30 s)
> "I built this with Claude as a coding agent. I set the constraints (strict TDD, isolation
> between users) and made the product and infrastructure calls. I didn't accept output
> blindly: SQLite on Render's free tier would wipe data, so I moved to Neon Postgres. Before
> shipping these features I tested the upgrade against a database from the previous
> release. In total: 77 tests on SQLite and Postgres, a three-user browser test, and checks
> on the live site. Thanks for watching."
