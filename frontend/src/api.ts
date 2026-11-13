export type Role = "owner" | "editor" | "viewer";

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
  role: Exclude<Role, "owner">;
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
  exportUrl: (id: string) => `/api/documents/${encodeURIComponent(id)}/export?format=md`,

  share: (id: string, email: string, role: Share["role"]) =>
    request<Share>(`/api/documents/${encodeURIComponent(id)}/shares`, {
      method: "PUT",
      body: json({ email, role }),
    }),
  listShares: (id: string) => request<Share[]>(`/api/documents/${encodeURIComponent(id)}/shares`),
  revoke: (id: string, userId: number) =>
    request<void>(`/api/documents/${encodeURIComponent(id)}/shares/${userId}`, { method: "DELETE" }),
};

export const SUPPORTED_UPLOADS = ".txt,.md,.markdown,.docx";
export const MAX_UPLOAD_MB = 2;
