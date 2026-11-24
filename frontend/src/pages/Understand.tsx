import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Database, Download, ExternalLink, Eye, FileText, Globe, Loader2, RefreshCw, Sparkles, Table2, Trash2, Upload, XCircle } from "lucide-react";
import { api, fmtNum } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Badge, Button, Card, CardHead, Empty, Field, Input, Loading, Modal, PageHead, Textarea, Toggle, cx, useAsync, useToast } from "../components/ui";

type Doc = { id: string; filename: string; size: number; pages: number; chunks: number; status: string; error: string; has_file: boolean };
type Conn = { id: string; name: string; kind: string; status: string; error: string; allow_writes: boolean; tables: { name: string; rows: number | null; columns: { name: string; type: string }[] }[]; endpoints: { path: string; summary: string }[]; config: any };
type Kind = { id: string; name: string; upload?: boolean; accept?: string; fields: { name: string; label: string; secret?: boolean; required?: boolean; default?: string; placeholder?: string }[] };

export default function Understand() {
  const { can } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const product = useAsync<{ description: string }>(() => api("/api/product"));
  const docs = useAsync<Doc[]>(() => api("/api/knowledge/documents"));
  const conns = useAsync<Conn[]>(() => can("data:view") ? api("/api/data/connections") : Promise.resolve([]));
  const setup = useAsync<any>(() => api("/api/setup"));
  const [desc, setDesc] = useState("");
  const [saved, setSaved] = useState(true);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (product.data) setDesc(product.data.description || ""); }, [product.data]);

  const latest = setup.data?.blueprint?.latest;
  const generating = latest?.status === "generating";
  useEffect(() => {
    if (!generating) return;
    const t = setInterval(() => setup.reload(), 2000);
    return () => clearInterval(t);
  }, [generating]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveDesc = async () => {
    try { await api("/api/product", { method: "PUT", body: { description: desc } }); setSaved(true); toast("Description saved"); } catch (e: any) { toast(e.message, "bad"); }
  };
  const understand = async () => {
    setBusy(true);
    try {
      if (!saved) await api("/api/product", { method: "PUT", body: { description: desc } });
      setSaved(true);
      await api("/api/blueprints/generate", { method: "POST", body: {} });
      setup.reload();
    } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); }
  };

  if (product.loading) return <Loading />;
  const hasInput = !!desc.trim() || (docs.data?.length || 0) > 0 || (conns.data?.length || 0) > 0;
  return (
    <>
      <PageHead title="Understand my product"
        sub="Tell Aria XAI about your product in any of three ways. It works out what your business is and designs an agent team, rules and guardrails for you to review." />

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-1">
          <CardHead title={<Step n={1} done={!!desc.trim()}>Describe it</Step>} sub="In your own words: what you sell, who uses it, the workflows, what good looks like." />
          <div className="p-5">
            <Textarea rows={12} value={desc} onChange={(e) => { setDesc(e.target.value); setSaved(false); }} disabled={!can("blueprint:edit")}
              />
            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-muted">{desc.length.toLocaleString()} characters</span>
              {can("blueprint:edit") && <Button size="sm" onClick={saveDesc} disabled={saved}>{saved ? "Saved" : "Save"}</Button>}
            </div>
          </div>
        </Card>

        <Documents docs={docs} />
        <DataConnections conns={conns} />
      </div>

      <Card className="mt-5 overflow-hidden">
        <div className="flex flex-wrap items-center gap-4 bg-gradient-to-r from-accentsoft to-transparent px-6 py-5">
          <div className="grid size-11 place-items-center rounded-xl bg-accent text-white"><Sparkles className="size-5" /></div>
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{latest ? "Re-understand after changes" : "Let Aria XAI understand your product"}</div>
            <div className="text-[13px] text-muted">Reads everything above with the platform's AI model, proposes a blueprint, checks it symbolically, repairs any errors, then waits for your review.</div>
          </div>
          {can("blueprint:create") && <Button variant="primary" icon={<Sparkles className="size-4" />} loading={busy} disabled={!hasInput || generating} onClick={understand}>
            {generating ? "Working…" : "Understand my product"}
          </Button>}
        </div>
        {latest && (
          <div className="border-t border-line px-6 py-4">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">Blueprint v{latest.version}</span>
              <Badge tone={latest.status === "failed" ? "bad" : latest.status === "generating" ? "info" : latest.status === "published" ? "ok" : "accent"}>{latest.status}</Badge>
              {latest.industry && <span className="text-muted">· inferred: <b className="text-fg">{latest.industry}</b></span>}
              {latest.status !== "generating" && latest.status !== "failed" && <Button size="sm" variant="primary" className="ml-auto" onClick={() => nav(`/blueprint/${latest.id}`)}>Review blueprint</Button>}
            </div>
            <ol className="space-y-1.5">
              {(latest.progress || []).map((p: any, i: number) => (
                <li key={i} className="flex items-start gap-2 text-[13px]">
                  {p.state === "failed" ? <XCircle className="mt-0.5 size-4 text-bad" /> : <CheckCircle2 className="mt-0.5 size-4 text-ok" />}
                  <span className={p.state === "failed" ? "text-bad" : ""}>{p.step}</span>
                </li>
              ))}
              {generating && <li className="flex items-center gap-2 text-[13px] text-muted"><Loader2 className="size-4 animate-spin" /> Thinking… this can take a minute for large products.</li>}
            </ol>
            {latest.status === "failed" && latest.error?.includes("AI model") && <div className="mt-3"><Alert tone="warn">The AI model is not available right now. It is set on the server; contact your administrator.</Alert></div>}
          </div>
        )}
      </Card>
    </>
  );
}

function Step({ n, done, children }: { n: number; done: boolean; children: ReactNode }) {
  return <span className="inline-flex items-center gap-2"><span className={cx("grid size-6 place-items-center rounded-full text-xs font-semibold", done ? "bg-ok text-white" : "bg-panel2 text-muted")}>{done ? "✓" : n}</span>{children}</span>;
}

function Documents({ docs }: { docs: ReturnType<typeof useAsync<Doc[]>> }) {
  const { can } = useAuth();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [view, setView] = useState<Doc | null>(null);
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    setBusy(true);
    try {
      const r = await api<any[]>("/api/knowledge/upload", { form });
      const bad = r.filter((d) => d.status === "error");
      bad.length ? toast(`${bad[0].filename}: ${bad[0].error}`, "bad") : toast(`${r.length} document(s) added`);
      docs.reload();
    } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); if (input.current) input.current.value = ""; }
  };
  const del = async (d: Doc) => { if (!confirm(`Remove ${d.filename} from the knowledge base?`)) return; await api(`/api/knowledge/documents/${d.id}`, { method: "DELETE" }); docs.reload(); };
  const list = docs.data || [];
  return (
    <Card>
      <CardHead title={<Step n={2} done={list.length > 0}>Upload documents</Step>} sub="Policies, SOPs, manuals, contracts, price lists, FAQs. PDF, Word, Excel, CSV, Markdown, text." />
      <div className="p-5">
        {can("knowledge:create") && (
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
            onClick={() => input.current?.click()}
            className={cx("flex cursor-pointer flex-col items-center rounded-lg border-2 border-dashed px-4 py-6 text-center transition", drag ? "border-accent bg-accentsoft" : "border-line2 hover:bg-panel2")}>
            {busy ? <Loader2 className="size-6 animate-spin text-accent" /> : <Upload className="size-6 text-faint" />}
            <div className="mt-2 text-sm font-medium">{busy ? "Reading documents…" : "Drop files or click to upload"}</div>
            <div className="text-xs text-muted">Text is extracted and cited by page</div>
            <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.json,.html" onChange={(e) => upload(e.target.files)} />
          </div>
        )}
        <ul className="mt-3 divide-y divide-line">
          {list.map((d) => (
            <li key={d.id} className="flex items-center gap-2.5 py-2">
              <FileText className="size-4 shrink-0 text-muted" />
              <div className="min-w-0 flex-1"><div className="truncate text-sm">{d.filename}</div>
                <div className="text-xs text-muted">{d.status === "error" ? <span className="text-bad">{d.error}</span> : `${d.pages} page(s) · ${d.chunks} passages · ${fmtSize(d.size)}`}</div></div>
              {d.status !== "error" && <button onClick={() => setView(d)} className="rounded p-1 text-faint hover:text-fg" title="View" aria-label={`View ${d.filename}`}><Eye className="size-4" /></button>}
              {d.has_file
                ? <a href={`/api/knowledge/documents/${d.id}/file?download=true`} download className="rounded p-1 text-faint hover:text-fg" title="Download" aria-label={`Download ${d.filename}`}><Download className="size-4" /></a>
                : <span className="cursor-help rounded p-1 text-line2" title="Uploaded before downloads were available. Upload the file again to download it."><Download className="size-4" /></span>}
              {can("knowledge:delete") && <button onClick={() => del(d)} className="rounded p-1 text-faint hover:text-bad" title="Remove" aria-label={`Remove ${d.filename}`}><Trash2 className="size-4" /></button>}
            </li>
          ))}
        </ul>
        {!list.length && !can("knowledge:create") && <p className="text-sm text-muted">No documents yet.</p>}
      </div>
      {view && <DocViewer doc={view} onClose={() => setView(null)} />}
    </Card>
  );
}

const fmtSize = (b: number) => (b < 1024 ? `${b} bytes` : b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1)} MB`);
const OPENS_IN_BROWSER = /\.(pdf|png|jpe?g|gif|webp)$/i;

function DocViewer({ doc, onClose }: { doc: Doc; onClose: () => void }) {
  const [data, setData] = useState<{ pages: { page: number; text: string }[] } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<any>(`/api/knowledge/documents/${doc.id}/text`).then(setData).catch((e) => setErr(e.message)); }, [doc.id]);
  return (
    <Modal open onClose={onClose} wide title={doc.filename}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-muted">{doc.pages} page(s) · {fmtSize(doc.size)} · this is the text Aria XAI read and the agents search, with page numbers for citations.</span>
          <span className="ml-auto flex gap-2">
            {doc.has_file && OPENS_IN_BROWSER.test(doc.filename) && <a href={`/api/knowledge/documents/${doc.id}/file`} target="_blank" rel="noopener noreferrer"><Button size="sm" icon={<ExternalLink className="size-4" />}>Open original</Button></a>}
            {doc.has_file && <a href={`/api/knowledge/documents/${doc.id}/file?download=true`} download><Button size="sm" icon={<Download className="size-4" />}>Download</Button></a>}
          </span>
        </div>
        {err ? <Alert tone="bad">{err}</Alert> : !data ? <Loading /> : (
          <div className="max-h-[60vh] space-y-4 overflow-y-auto rounded-lg border border-line p-4 scroll-thin">
            {data.pages.map((p) => (
              <section key={p.page}>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-faint">Page {p.page}</div>
                <p className="whitespace-pre-wrap text-[13px] leading-relaxed">{p.text}</p>
              </section>
            ))}
            {!data.pages.length && <p className="text-sm text-muted">No text could be read from this file.</p>}
          </div>
        )}
      </div>
    </Modal>
  );
}

function DataConnections({ conns }: { conns: ReturnType<typeof useAsync<Conn[]>> }) {
  const { can } = useAuth();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [view, setView] = useState<Conn | null>(null);
  const list = conns.data || [];
  const refresh = async (c: Conn) => { const r = await api<Conn>(`/api/data/connections/${c.id}/refresh`, { method: "POST" }); toast(r.status === "ready" ? "Schema refreshed" : r.error, r.status === "ready" ? "ok" : "bad"); conns.reload(); };
  const del = async (c: Conn) => { if (!confirm(`Disconnect ${c.name}?`)) return; await api(`/api/data/connections/${c.id}`, { method: "DELETE" }); conns.reload(); };
  const toggleWrites = async (c: Conn, on: boolean) => {
    if (on && !confirm(`Allow approved actions to write to ${c.name}?\n\nOnly actions in the published blueprint that declare a table and columns can write, one row at a time, after a person approves. Use a database user that can write only those tables.`)) return;
    try { await api(`/api/data/connections/${c.id}`, { method: "PATCH", body: { allow_writes: on } }); toast(on ? `Writes enabled on ${c.name}` : `Writes disabled on ${c.name}`); conns.reload(); }
    catch (e: any) { toast(e.message, "bad"); }
  };
  return (
    <Card>
      <CardHead title={<Step n={3} done={list.some((c) => c.status === "ready")}>Connect data</Step>} sub="Read-only. Aria XAI learns your schema and a few sample rows; agents query it under the SQL guard."
        right={can("data:create") && <Button size="sm" onClick={() => setAdding(true)}>Connect</Button>} />
      <div className="p-5">
        {!list.length ? (
          <Empty icon={<Database className="size-7" />} title="No data connected">Postgres, MySQL, SQL Server, a REST API, or upload a CSV / Excel / SQLite file.</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {list.map((c) => (
              <li key={c.id} className="py-2.5">
                <div className="flex items-center gap-2.5">
                  {c.kind === "rest" ? <Globe className="size-4 text-muted" /> : <Database className="size-4 text-muted" />}
                  <button onClick={() => setView(c)} className="min-w-0 flex-1 text-left">
                    <div className="truncate text-sm font-medium hover:text-accent">{c.name}</div>
                    <div className="text-xs text-muted">{c.status === "ready" ? (c.kind === "rest" ? `${c.endpoints.length} GET endpoints` : `${c.tables.length} tables · ${fmtNum(c.tables.reduce((a, t) => a + (t.rows || 0), 0))} rows`) : <span className="text-bad">{c.error || c.status}</span>}</div>
                  </button>
                  {c.kind !== "rest" && c.status === "ready" && (can("data:edit") ? (
                    <Toggle checked={c.allow_writes} onChange={(v) => toggleWrites(c, v)} label={<span className="text-xs text-muted">writes</span>} />
                  ) : c.allow_writes ? <Badge tone="warn">writes on</Badge> : null)}
                  {can("data:edit") && <button onClick={() => refresh(c)} className="rounded p-1 text-faint hover:text-fg" title="Refresh schema" aria-label="Refresh schema"><RefreshCw className="size-4" /></button>}
                  {can("data:delete") && <button onClick={() => del(c)} className="rounded p-1 text-faint hover:text-bad" aria-label="Disconnect"><Trash2 className="size-4" /></button>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      {adding && <AddConnection onClose={() => setAdding(false)} onDone={() => { setAdding(false); conns.reload(); }} />}
      {view && <SchemaView conn={view} onClose={() => setView(null)} />}
    </Card>
  );
}

function AddConnection({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const kinds = useAsync<Kind[]>(() => api("/api/data/kinds"));
  const [kind, setKind] = useState<Kind | null>(null);
  const [name, setName] = useState("");
  const [vals, setVals] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const pick = (k: Kind) => { setKind(k); setName(""); setErr(""); setVals(Object.fromEntries(k.fields.map((f) => [f.name, f.default || ""]))); };
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      let r: Conn;
      if (kind!.upload) {
        const form = new FormData(); form.append("file", file!); form.append("name", name || file!.name);
        r = await api<Conn>("/api/data/upload", { form });
      } else {
        r = await api<Conn>("/api/data/connections", { body: { name: name || kind!.name, kind: kind!.id, values: vals } });
      }
      if (r.status !== "ready") { setErr(r.error); toast("Saved, but the connection failed, fix the details and refresh", "bad"); }
      else toast(`${r.name} connected`);
      onDone();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title="Connect data">
      {kinds.loading ? <Loading /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {kinds.data!.map((k) => (
              <button key={k.id} onClick={() => pick(k)} className={cx("rounded-lg border px-3 py-2.5 text-left text-sm", kind?.id === k.id ? "border-accent bg-accentsoft font-medium" : "border-line hover:bg-panel2")}>{k.name}</button>
            ))}
          </div>
          {kind && (
            <>
              <Field label="Name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
              {kind.upload ? (
                <Field label="File" hint="CSV, Excel (.xlsx, every sheet becomes a table) or a SQLite database."><Input type="file" accept={kind.accept} onChange={(e) => setFile(e.target.files?.[0] || null)} className="pt-1.5" /></Field>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {kind.fields.map((f) => (
                    <Field key={f.name} label={<>{f.label}{f.required && <span className="text-bad"> *</span>}</>}>
                      <Input type={f.secret ? "password" : "text"} autoComplete="off" value={vals[f.name] || ""} onChange={(e) => setVals({ ...vals, [f.name]: e.target.value })} />
                    </Field>
                  ))}
                </div>
              )}
              <Alert tone="info">Use a read-only database user. Aria XAI only ever runs SELECT queries that pass its SQL guard, and credentials are encrypted at rest.</Alert>
              {err && <Alert tone="bad">{err}</Alert>}
              <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
                <Button variant="primary" loading={busy} disabled={kind.upload ? !file : kind.fields.some((f) => f.required && !vals[f.name])} onClick={submit}>Connect & read schema</Button></div>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}

function SchemaView({ conn, onClose }: { conn: Conn; onClose: () => void }) {
  const [table, setTable] = useState<string | null>(conn.tables[0]?.name || null);
  const preview = useAsync<any>(() => table ? api(`/api/data/connections/${conn.id}/tables/${encodeURIComponent(table)}`) : Promise.resolve(null), [table]);
  return (
    <Modal open onClose={onClose} wide title={conn.name}>
      {conn.kind === "rest" ? (
        <ul className="space-y-1 text-sm">{conn.endpoints.map((e) => <li key={e.path}><span className="font-mono">GET {e.path}</span> <span className="text-muted">{e.summary}</span></li>)}</ul>
      ) : (
        <div className="grid gap-4 md:grid-cols-[200px_1fr]">
          <ul className="space-y-0.5">
            {conn.tables.map((t) => (
              <li key={t.name}><button onClick={() => setTable(t.name)} className={cx("flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm", table === t.name ? "bg-accentsoft text-accent" : "hover:bg-panel2")}>
                <Table2 className="size-3.5" /><span className="truncate">{t.name}</span><span className="ml-auto text-xs text-faint">{fmtNum(t.rows)}</span></button></li>
            ))}
          </ul>
          <div className="min-w-0">
            {preview.loading ? <Loading /> : preview.error ? <Alert tone="bad">{preview.error}</Alert> : preview.data && (
              <div className="overflow-auto rounded-lg border border-line scroll-thin">
                <table className="w-full text-xs">
                  <thead className="bg-panel2"><tr>{preview.data.columns.map((c: string) => <th key={c} className="whitespace-nowrap px-2 py-1.5 text-left font-medium">{c}</th>)}</tr></thead>
                  <tbody>{preview.data.rows.map((r: any[], i: number) => <tr key={i} className="border-t border-line">{r.map((v, j) => <td key={j} className="whitespace-nowrap px-2 py-1">{v == null ? <span className="text-faint">null</span> : String(v)}</td>)}</tr>)}</tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
