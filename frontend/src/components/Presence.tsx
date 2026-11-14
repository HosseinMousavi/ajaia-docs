import { avatarColor, type PresenceUser } from "../api";

const MAX_AVATARS = 4;

export default function Presence({ others }: { others: PresenceUser[] }) {
  if (others.length === 0) return null;
  const editing = others.filter((o) => o.editing);
  const first = (name: string) => name.split(" ")[0];
  const label = editing.length
    ? `${first(editing[0].name)}${editing.length > 1 ? ` +${editing.length - 1}` : ""} editing`
    : `${others.length === 1 ? first(others[0].name) : `${others.length} people`} viewing`;

  return (
    <div className="presence" role="status" aria-label={`Also here: ${others.map((o) => o.name).join(", ")}`}>
      <div className="presence-stack">
        {others.slice(0, MAX_AVATARS).map((o) => (
          <span
            key={o.id}
            className={`pav ${o.editing ? "editing" : ""}`}
            style={{ background: avatarColor(o.id) }}
            title={`${o.name} · ${o.editing ? "editing" : "viewing"}`}
          >
            {o.name[0]}
          </span>
        ))}
        {others.length > MAX_AVATARS && <span className="pav more">+{others.length - MAX_AVATARS}</span>}
      </div>
      <span className="presence-text small">
        <span className="live-dot" aria-hidden /> {label}
      </span>
    </div>
  );
}
