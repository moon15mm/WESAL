/* Typed fetch wrapper for the WESAL API (same origin: /api/v1).
   - Sends cookies, the CSRF double-submit header, the UI locale and the active business context.
   - Normalizes errors into ApiError(code, message, fields). */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string> = {},
    public params: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export type Page<T> = { items: T[]; total: number; page: number; page_size: number } & Record<string, unknown>;

let currentLocale = "ar";
let currentBusinessId: string | null = null;

export function setApiLocale(locale: string) {
  currentLocale = locale;
}
export function setApiBusiness(id: string | null) {
  currentBusinessId = id;
}
export function getApiBusiness() {
  return currentBusinessId;
}

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|; )wesal_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

type Opts = { method?: string; body?: unknown; form?: FormData; query?: Record<string, unknown>; business?: string | null; raw?: boolean };

export function buildQuery(query?: Record<string, unknown>) {
  if (!query) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const method = opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { "x-locale": currentLocale, accept: "application/json" };
  const business = opts.business !== undefined ? opts.business : currentBusinessId;
  if (business) headers["x-business-id"] = business;
  if (method !== "GET") {
    let token = csrfToken();
    if (!token) {
      await fetch("/api/v1/auth/csrf", { credentials: "include" });
      token = csrfToken();
    }
    if (token) headers["x-csrf-token"] = token;
  }
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(`/api/v1${path}${buildQuery(opts.query)}`, { method, headers, body, credentials: "include" });
  if (opts.raw) {
    if (!res.ok) throw await toError(res);
    return res as unknown as T;
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const data = await res.json();
    const e = data.error || {};
    return new ApiError(res.status, e.code || "error", e.message || res.statusText, e.fields || {}, e.params || {});
  } catch {
    return new ApiError(res.status, "network_error", res.statusText);
  }
}

export async function download(path: string, query?: Record<string, unknown>, filename?: string) {
  const res = await api<Response>(path, { query, raw: true });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const cd = res.headers.get("content-disposition") || "";
  a.download = filename || /filename="([^"]+)"/.exec(cd)?.[1] || "wesal-export";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
