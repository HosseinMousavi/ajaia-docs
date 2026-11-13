import { useEditorState, type Editor } from "@tiptap/react";

type Btn = {
  label: string;
  title: string;
  run: (e: Editor) => void;
  active: (e: Editor) => boolean;
  className?: string;
};

const GROUPS: Btn[][] = [
  [
    { label: "B", title: "Bold (Ctrl/Cmd+B)", className: "b", run: (e) => e.chain().focus().toggleBold().run(), active: (e) => e.isActive("bold") },
    { label: "I", title: "Italic (Ctrl/Cmd+I)", className: "i", run: (e) => e.chain().focus().toggleItalic().run(), active: (e) => e.isActive("italic") },
    { label: "U", title: "Underline (Ctrl/Cmd+U)", className: "u", run: (e) => e.chain().focus().toggleUnderline().run(), active: (e) => e.isActive("underline") },
    { label: "S", title: "Strikethrough", className: "s", run: (e) => e.chain().focus().toggleStrike().run(), active: (e) => e.isActive("strike") },
  ],
  [
    { label: "H1", title: "Heading 1", run: (e) => e.chain().focus().toggleHeading({ level: 1 }).run(), active: (e) => e.isActive("heading", { level: 1 }) },
    { label: "H2", title: "Heading 2", run: (e) => e.chain().focus().toggleHeading({ level: 2 }).run(), active: (e) => e.isActive("heading", { level: 2 }) },
    { label: "H3", title: "Heading 3", run: (e) => e.chain().focus().toggleHeading({ level: 3 }).run(), active: (e) => e.isActive("heading", { level: 3 }) },
  ],
  [
    { label: "• List", title: "Bulleted list", run: (e) => e.chain().focus().toggleBulletList().run(), active: (e) => e.isActive("bulletList") },
    { label: "1. List", title: "Numbered list", run: (e) => e.chain().focus().toggleOrderedList().run(), active: (e) => e.isActive("orderedList") },
    { label: "❝", title: "Quote", run: (e) => e.chain().focus().toggleBlockquote().run(), active: (e) => e.isActive("blockquote") },
  ],
];

export default function Toolbar({ editor }: { editor: Editor }) {
  // Re-render on selection/transaction so active states stay accurate.
  const active = useEditorState({
    editor,
    selector: ({ editor: e }) => GROUPS.flat().map((b) => b.active(e)),
  });
  let i = 0;
  return (
    <div className="toolbar" role="toolbar" aria-label="Formatting">
      <button className="tb" title="Undo" onClick={() => editor.chain().focus().undo().run()}>
        ↶
      </button>
      <button className="tb" title="Redo" onClick={() => editor.chain().focus().redo().run()}>
        ↷
      </button>
      {GROUPS.map((group, gi) => (
        <div className="tb-group" key={gi}>
          {group.map((b) => {
            const isActive = active[i++];
            return (
              <button
                key={b.title}
                className={`tb ${b.className ?? ""} ${isActive ? "on" : ""}`}
                title={b.title}
                aria-pressed={isActive}
                onMouseDown={(ev) => ev.preventDefault()}
                onClick={() => b.run(editor)}
              >
                {b.label}
              </button>
            );
          })}
        </div>
      ))}
      <div className="tb-group">
        <button
          className="tb"
          title="Clear formatting"
          onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()}
        >
          T̸
        </button>
      </div>
    </div>
  );
}
