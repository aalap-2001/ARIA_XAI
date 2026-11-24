let csrf = "";
export const setCsrf = (t: string) => { csrf = t; };

export class ApiError extends Error {
  status: number;
  details?: string[];
  constructor(message: string, status: number, details?: string[]) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function parse(r: Response) {
  const text = await r.text();
  let body: any = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!r.ok) {
    const d = body?.detail ?? body;
    if (d && typeof d === "object" && !Array.isArray(d)) throw new ApiError(d.message || r.statusText, r.status, d.errors);
    throw new ApiError(typeof d === "string" && d ? d : r.statusText || "Request failed", r.status);
  }
  return body;
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const method = opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = {};
  if (method !== "GET" && csrf) headers["x-csrf-token"] = csrf;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  const r = await fetch(path, { method, headers, body, credentials: "same-origin" });
  return parse(r);
}

/** POST that streams Server-Sent Events. Calls onEvent(type, data) for each event. */
export async function stream(path: string, body: unknown, onEvent: (type: string, data: any) => void) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify(body) });
  if (!r.ok || !r.body) return parse(r);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let type = "message", data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event: ")) type = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) onEvent(type, JSON.parse(data));
    }
  }
}

export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "-");
export const fmtNum = (n?: number | null) => (n == null ? "-" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }));
