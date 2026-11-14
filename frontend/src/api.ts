export type Role = "owner" | "editor" | "commenter" | "viewer";
export type ShareRole = Exclude<Role, "owner">;

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  editor: "Can edit",
  commenter: "Can comment",
  viewer: "View only",
};

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface DocSummary {
  id: string;
  title: string;
  role: Role;
  owner: User;
  updated_at: string;
}

export interface Share {
  user: User;
  role: ShareRole;
}

export interface Comment {
  id: number;
  parent_id: number | null;
  author: User;
  body: string;
  quote: string | null;
  resolved: boolean;
  created_at: string;
  replies: Comment[];
}

export type VersionKind = "created" | "imported" | "baseline" | "edit" | "restored";

export interface Version {
  id: number;
  version: number;
  kind: VersionKind;
  title: string;
  author: User | null;
  restored_from: number | null;
  created_at: string;
  updated_at: string;
}

export interface VersionDetail extends Version {
  content_html: string;
  diff: ["equal" | "insert" | "delete", string][];
  stats: { added: number; removed: number };
}

export interface PresenceUser extends User {
  editing: boolean;
}

export interface Doc extends DocSummary {
  content_html: string;
  version: number;
  created_at: string;
  shares: Share[] | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: unknown = null,
  ) {
    super(message);
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg).replace(/^Value error, /, "");
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (res.status === 204) return undefined as T;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(res.status, detailMessage(body, `Request failed (${res.status})`), body);
  return body as T;
}

const json = (data: unknown) => JSON.stringify(data);

export const api = {
  me: () => request<User>("/api/auth/me"),
  demoUsers: () => request<{ email: string; name: string }[]>("/api/auth/demo-users"),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", body: json({ email, password }) }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  listDocs: () => request<{ owned: DocSummary[]; shared: DocSummary[] }>("/api/documents"),
  createDoc: (title?: string) =>
    request<Doc>("/api/documents", { method: "POST", body: json(title ? { title } : {}) }),
  getDoc: (id: string) => request<Doc>(`/api/documents/${encodeURIComponent(id)}`),
  updateDoc: (id: string, patch: { title?: string; content_html?: string; base_version: number }) =>
    request<Doc>(`/api/documents/${encodeURIComponent(id)}`, { method: "PATCH", body: json(patch) }),
  deleteDoc: (id: string) => request<void>(`/api/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  importFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Doc>("/api/documents/import", { method: "POST", body: form });
  },
  exportUrl: (id: string, format: "md" | "pdf") =>
    `/api/documents/${encodeURIComponent(id)}/export?format=${format}`,

  share: (id: string, email: string, role: ShareRole) =>
    request<Share>(`/api/documents/${encodeURIComponent(id)}/shares`, {
      method: "PUT",
      body: json({ email, role }),
    }),
  listShares: (id: string) => request<Share[]>(`/api/documents/${encodeURIComponent(id)}/shares`),
  revoke: (id: string, userId: number) =>
    request<void>(`/api/documents/${encodeURIComponent(id)}/shares/${userId}`, { method: "DELETE" }),

  listComments: (id: string) => request<Comment[]>(`${docUrl(id)}/comments`),
  addComment: (id: string, body: string, opts: { quote?: string | null; parent_id?: number } = {}) =>
    request<Comment>(`${docUrl(id)}/comments`, { method: "POST", body: json({ body, ...opts }) }),
  resolveComment: (id: string, commentId: number, resolved: boolean) =>
    request<Comment>(`${docUrl(id)}/comments/${commentId}`, { method: "PATCH", body: json({ resolved }) }),
  deleteComment: (id: string, commentId: number) =>
    request<void>(`${docUrl(id)}/comments/${commentId}`, { method: "DELETE" }),

  listVersions: (id: string) => request<Version[]>(`${docUrl(id)}/versions`),
  getVersion: (id: string, versionId: number) => request<VersionDetail>(`${docUrl(id)}/versions/${versionId}`),
  restoreVersion: (id: string, versionId: number, base_version: number) =>
    request<Doc>(`${docUrl(id)}/versions/${versionId}/restore`, { method: "POST", body: json({ base_version }) }),

  heartbeat: (id: string, editing: boolean) =>
    request<{ others: PresenceUser[] }>(`${docUrl(id)}/presence`, { method: "POST", body: json({ editing }) }),
  leave: (id: string) => {
    // keepalive lets the request finish even while the page is unloading
    void fetch(`${docUrl(id)}/presence`, { method: "DELETE", credentials: "same-origin", keepalive: true }).catch(
      () => undefined,
    );
  },
};

function docUrl(id: string): string {
  return `/api/documents/${encodeURIComponent(id)}`;
}

export function timeAgo(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 45) return "just now";
  if (secs < 3600) return `${Math.max(1, Math.round(secs / 60))} min ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)} h ago`;
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

const AVATAR_COLORS = ["#2f5bea", "#0f9d58", "#d93025", "#a142f4", "#e37400", "#00838f", "#c2185b"];
export function avatarColor(userId: number): string {
  return AVATAR_COLORS[userId % AVATAR_COLORS.length];
}

export const SUPPORTED_UPLOADS = ".txt,.md,.markdown,.docx";
export const MAX_UPLOAD_MB = 2;
