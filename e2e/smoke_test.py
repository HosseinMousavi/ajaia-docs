"""Browser end-to-end smoke test (Playwright).

Usage:
    pip install playwright && playwright install chromium
    python e2e/smoke_test.py http://localhost:8000   # against a freshly seeded server

Covers: login, create, rename, rich-text formatting, autosave + reload persistence,
sharing (viewer/commenter/editor), file import, owned-vs-shared listing, read-only
enforcement in the UI, live presence, anchored comments with reply/resolve, version
history with diff + restore, and PDF export.
Writes screenshots to e2e/screenshots/.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SHOTS = Path(__file__).parent / "screenshots"
SHOTS.mkdir(exist_ok=True)
CHROME = os.environ.get("CHROME_PATH")


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def login(page: Page, name: str) -> None:
    page.goto(BASE)
    page.get_by_role("button", name=name).click()
    expect(page.get_by_text("My documents")).to_be_visible()


def wait_saved(page: Page) -> None:
    expect(page.get_by_text("All changes saved")).to_be_visible(timeout=10_000)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch()
        alice = browser.new_context(viewport={"width": 1280, "height": 860}).new_page()

        # --- Login + home
        alice.goto(BASE)
        expect(alice.get_by_text("Demo accounts")).to_be_visible()
        shot(alice, "01-login")
        login(alice, "Alice Chen")
        shot(alice, "02-home-owned")

        # --- Create, rename, format
        alice.get_by_role("button", name="Blank document").click()
        title = alice.get_by_label("Document title")
        expect(title).to_have_value("Untitled document")
        title.fill("Launch plan")
        editor = alice.locator(".tiptap")
        editor.click()
        alice.get_by_role("button", name="H1").click()
        alice.keyboard.type("Launch plan")
        alice.keyboard.press("Enter")
        alice.get_by_role("button", name="B", exact=True).click()
        alice.keyboard.type("Ship by Friday.")
        alice.get_by_role("button", name="B", exact=True).click()
        alice.keyboard.press("Enter")
        alice.get_by_role("button", name="• List").click()
        alice.keyboard.type("Write README")
        alice.keyboard.press("Enter")
        alice.keyboard.type("Record walkthrough")
        wait_saved(alice)
        shot(alice, "03-editor-formatting")

        # --- Persistence across reload
        alice.reload()
        expect(alice.get_by_label("Document title")).to_have_value("Launch plan")
        html = editor.inner_html()
        assert "<h1>Launch plan</h1>" in html, html
        assert "<strong>Ship by Friday.</strong>" in html, html
        assert "<li><p>Record walkthrough</p></li>" in html, html

        # --- Share with Bob as viewer
        alice.get_by_role("button", name="Share").click()
        alice.get_by_placeholder("Add people by email").fill("bob@ajaia.test")
        alice.get_by_label("Access level").select_option("viewer")
        alice.get_by_role("dialog").get_by_role("button", name="Share").click()
        expect(alice.get_by_role("dialog").get_by_text("Bob Rivera")).to_be_visible()
        alice.get_by_placeholder("Add people by email").fill("carol@ajaia.test")
        alice.get_by_label("Access level").select_option("commenter")
        alice.get_by_role("dialog").get_by_role("button", name="Share").click()
        expect(alice.get_by_role("dialog").get_by_text("Carol Okafor")).to_be_visible()
        shot(alice, "04-share-dialog")
        # Validation: unknown user
        alice.get_by_placeholder("Add people by email").fill("nobody@ajaia.test")
        alice.get_by_role("dialog").get_by_role("button", name="Share").click()
        expect(alice.get_by_text("No user found with that email")).to_be_visible()
        alice.get_by_role("button", name="Done").click()

        # --- Import a markdown file
        alice.get_by_role("button", name="Back to documents").click()
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "Imported notes.md"
            md.write_text("# Imported heading\n\nSome *italic* text.\n\n1. first\n2. second\n")
            alice.get_by_test_id("file-input").set_input_files(str(md))
            expect(alice.get_by_label("Document title")).to_have_value("Imported notes")
            assert "<h1>Imported heading</h1>" in editor.inner_html()
            assert "<ol>" in editor.inner_html()
        shot(alice, "05-imported-markdown")
        alice.get_by_role("button", name="Back to documents").click()
        expect(alice.get_by_role("button", name="Launch plan")).to_be_visible()

        # --- Bob sees it under "Shared with me", read-only
        bob = browser.new_context(viewport={"width": 1280, "height": 860}).new_page()
        login(bob, "Bob Rivera")
        expect(bob.get_by_role("button", name="Launch plan")).to_have_count(0)  # not in "My documents"
        bob.get_by_role("tab", name="Shared with me").click()
        shot(bob, "06-bob-shared-with-me")
        bob.get_by_role("button", name="Launch plan").click()
        expect(bob.get_by_text("Shared by Alice Chen")).to_be_visible()
        expect(bob.get_by_role("toolbar")).to_have_count(0)
        expect(bob.locator(".tiptap")).to_have_attribute("contenteditable", "false")
        expect(bob.get_by_role("button", name="Share")).to_have_count(0)
        shot(bob, "07-bob-view-only")

        # --- Bob edits the seeded welcome doc (editor), Alice receives the change via polling
        bob.get_by_role("button", name="Back to documents").click()
        bob.get_by_role("tab", name="Shared with me").click()
        bob.get_by_role("button", name="Welcome to Ajaia Docs").click()
        bob.locator(".tiptap").click()
        bob.keyboard.press("Control+End")
        bob.keyboard.press("Enter")
        bob.keyboard.type("Bob was here.")
        wait_saved(bob)
        alice.get_by_role("button", name="Welcome to Ajaia Docs").click()
        expect(alice.locator(".tiptap")).to_contain_text("Bob was here.", timeout=10_000)
        shot(alice, "08-alice-sees-bob-edit")

        # --- Presence: Bob is still in the welcome doc, so Alice sees his avatar
        expect(alice.locator(".presence")).to_contain_text("Bob", timeout=12_000)
        shot(alice, "09-presence")

        # --- Version history: diff against an older version, then restore it
        alice.get_by_role("button", name=re.compile("History")).click()
        panel = alice.get_by_role("complementary", name="Version history")
        expect(panel.get_by_role("button", name=re.compile(r"^Edited"))).to_be_visible()
        panel.get_by_role("button", name=re.compile(r"^(Created|Earlier version)")).click()
        expect(alice.get_by_test_id("version-diff").locator("del")).to_contain_text("Bob was here.")
        shot(alice, "10-history-diff")
        alice.get_by_role("button", name="Restore this version").click()
        expect(alice.locator(".tiptap")).not_to_contain_text("Bob was here.")
        expect(panel.get_by_role("button", name=re.compile(r"^Restored v1"))).to_be_visible()
        expect(bob.locator(".tiptap")).not_to_contain_text("Bob was here.", timeout=12_000)

        # --- Comments: Carol (commenter) comments on selected text
        carol = browser.new_context(viewport={"width": 1280, "height": 860}).new_page()
        login(carol, "Carol Okafor")
        carol.get_by_role("tab", name="Shared with me").click()
        carol.get_by_role("button", name="Launch plan").click()
        expect(carol.locator(".meta")).to_contain_text("Can comment")
        expect(carol.get_by_role("toolbar")).to_have_count(0)
        carol.locator(".tiptap strong", has_text="Ship by Friday.").click(click_count=3)
        carol.get_by_role("button", name=re.compile("Comments")).click()
        expect(carol.locator(".c-quote.pending")).to_contain_text("Ship by Friday")
        carol.get_by_placeholder("Comment on the selected text…").fill("Is Friday a hard deadline?")
        carol.get_by_role("button", name="Comment", exact=True).click()
        expect(carol.locator(".thread")).to_contain_text("Is Friday a hard deadline?")
        shot(carol, "11-carol-comments")

        # Alice opens the doc: the comments panel opens itself, she sees Carol, replies and resolves
        alice.get_by_role("button", name="Back to documents").click()
        alice.get_by_role("button", name="Launch plan").click()
        thread = alice.locator(".thread").first
        expect(thread).to_contain_text("Is Friday a hard deadline?", timeout=12_000)
        expect(alice.locator(".presence")).to_contain_text("Carol", timeout=12_000)
        thread.get_by_placeholder("Reply…").fill("Yes, launch is locked.")
        thread.get_by_placeholder("Reply…").press("Enter")
        expect(thread).to_contain_text("Yes, launch is locked.")
        shot(alice, "12-alice-replies")
        thread.get_by_role("button", name="✓ Resolve").click()
        expect(alice.get_by_role("tab", name=re.compile("Resolved"))).to_contain_text("1")
        expect(carol.locator(".thread")).to_have_count(0, timeout=12_000)  # moved to Resolved for Carol too

        # --- PDF export
        doc_id = alice.url.split("/doc/")[1]
        pdf = alice.request.get(f"{BASE}/api/documents/{doc_id}/export?format=pdf")
        assert pdf.ok and pdf.headers["content-type"] == "application/pdf"
        assert pdf.body().startswith(b"%PDF")

        browser.close()
    print("E2E smoke test passed. Screenshots in", SHOTS)


if __name__ == "__main__":
    main()
