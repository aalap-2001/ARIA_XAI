import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, Bot, BrainCircuit, CheckCircle2, Code2, Download, Eye, FileWarning, History, Loader2, Minus, Pencil, Plus, Rocket, Sparkles, Upload, Wand2 } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Badge, Button, Card, Empty, ErrorBox, Field, Input, Loading, Modal, PageHead, Select, Tabs, Textarea, Toggle, useAsync, useToast } from "../components/ui";

type BP = { id: string; version: number; status: string; content: any; validation: { errors: string[]; warnings: string[]; ok: boolean }; progress: any[];
  sources: any; error: string; note: string; created_at: string; published_at: string | null; industry?: string };
type Tab = "overview" | "agents" | "rules" | "actions" | "watch" | "ontology" | "kpis";

export function describe(c: any): string {
  if (!c || typeof c !== "object") return String(c ?? "");
  if (c.all) return "(" + c.all.map(describe).join(" AND ") + ")";
  if (c.any) return "(" + c.any.map(describe).join(" OR ") + ")";
  if (c.not) return "NOT " + describe(c.not);
  if ("exists" in c) return `${c.path} ${c.exists ? "is known" : "is unknown"}`;
  if ("is" in c) return `${c.path} is ${c.is}`;
  return `${c.path} ${c.op ?? "=="} ${typeof c.value === "string" && c.value.startsWith("$") ? c.value.slice(1) : JSON.stringify(c.value)}`;
}
const riskTone = (r: string) => (r === "HIGH" ? "bad" : r === "MEDIUM" ? "warn" : "ok") as "bad" | "warn" | "ok";

export default function BlueprintPage() {
  const { bid } = useParams();
  const nav = useNavigate();
  const { can } = useAuth();
  const toast = useToast();
  const list = useAsync<BP[]>(() => api("/api/blueprints"));
  const id = bid || list.data?.find((b) => b.status === "published")?.id || list.data?.[0]?.id;
  const bp = useAsync<BP | null>(() => (id ? api(`/api/blueprints/${id}`) : Promise.resolve(null)), [id]);
  const [tab, setTab] = useState<Tab>("overview");
  const [json, setJson] = useState<{ key: string; text: string } | null>(null);
  const [refine, setRefine] = useState("");
  const [busy, setBusy] = useState("");
  const [showVersions, setShowVersions] = useState(false);
  const [showUpload, setShowUpload] = useState(false);

  useEffect(() => {
    if (bp.data?.status !== "generating") return;
    const t = setInterval(() => bp.reload(), 2000);
    return () => clearInterval(t);
  }, [bp.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (list.loading || (id && bp.loading && !bp.data)) return <Loading />;
  if (list.error) return <ErrorBox error={list.error} />;
  if (!id || !bp.data) return (
    <>
      <PageHead title="Blueprint" />
      <Empty icon={<BrainCircuit className="size-8" />} title="No blueprint yet" action={<Link to="/understand"><Button variant="primary" icon={<Sparkles className="size-4" />}>Understand my product</Button></Link>}>
        A blueprint is what Aria XAI understood about your product: the agent team, the rules, the actions and who must approve them.
      </Empty>
    </>
  );
  const b = bp.data;
  const c = b.content || {};
  const editable = can("blueprint:edit") && b.status !== "generating";

  const save = async (content: any, msg = "Saved") => {
    setBusy("save");
    try {
      const r = await api<BP>(`/api/blueprints/${b.id}`, { method: "PUT", body: { content } });
      toast(r.id !== b.id ? `${msg} as new draft v${r.version}` : msg);
      list.reload();
      r.id !== b.id ? nav(`/blueprint/${r.id}`) : bp.setData(r);
    } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };
  const publish = async () => {
    setBusy("publish");
    try { await api(`/api/blueprints/${b.id}/publish`, { method: "POST" }); toast(`v${b.version} is live, the agent team now runs on it`); bp.reload(); list.reload(); }
    catch (e: any) { toast(e.details ? `${e.message}: ${e.details[0]}` : e.message, "bad"); bp.reload(); } finally { setBusy(""); }
  };
  const askAI = async () => {
    setBusy("refine");
    try { const r = await api<BP>(`/api/blueprints/${b.id}/refine`, { body: { instruction: refine, section: tab } }); setRefine(""); list.reload(); nav(`/blueprint/${r.id}`); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };
  const sectionKey: Record<Tab, string[]> = { overview: ["summary", "industry", "business_model", "primary_users", "starter_questions"], agents: ["agents"],
    rules: ["facts", "signals", "rules"], actions: ["actions"], watch: ["watch_rules"], ontology: ["ontology"], kpis: ["kpis"] };
  const openJson = () => setJson({ key: tab, text: JSON.stringify(Object.fromEntries(sectionKey[tab].map((k) => [k, c[k]])), null, 2) });
  const applyJson = async () => {
    try { const part = JSON.parse(json!.text); setJson(null); await save({ ...c, ...part }); } catch (e: any) { toast("Invalid JSON: " + e.message, "bad"); }
  };

  return (
    <>
      <PageHead
        title={<span className="inline-flex flex-wrap items-center gap-2">Blueprint v{b.version}
          <Badge tone={b.status === "published" ? "ok" : b.status === "failed" ? "bad" : b.status === "generating" ? "info" : b.status === "archived" ? "neutral" : "accent"}>{b.status}</Badge></span>}
        sub={b.status === "generating" ? "Aria XAI is working…" : <>{c.industry && <>Inferred industry: <b className="text-fg">{c.industry}</b> · </>}{b.note}{b.published_at && <> · published {fmtDate(b.published_at)}</>}</>}
        right={<>
          <Button icon={<History className="size-4" />} onClick={() => setShowVersions(true)}>Versions ({list.data!.length})</Button>
          {b.status !== "generating" && <a href={`/api/blueprints/${b.id}/rules.yaml`} download><Button icon={<Download className="size-4" />}>Download rules (YAML)</Button></a>}
          {can("blueprint:edit") && <Button icon={<Upload className="size-4" />} onClick={() => setShowUpload(true)}>Upload rules (YAML)</Button>}
          {can("blueprint:publish") && (b.status === "draft" || b.status === "archived") &&
            <Button variant="primary" icon={<Rocket className="size-4" />} loading={busy === "publish"} disabled={!b.validation?.ok} onClick={publish}>{b.status === "archived" ? "Switch to this version" : "Publish"}</Button>}
        </>} />
      {showVersions && <Versions list={list.data!} current={b} canSwitch={can("blueprint:publish")} onClose={() => setShowVersions(false)}
        onSwitched={() => { list.reload(); bp.reload(); }} />}
      {showUpload && <UploadRules onClose={() => setShowUpload(false)} canPublish={can("blueprint:publish")}
        onApplied={(id) => { setShowUpload(false); list.reload(); nav(`/blueprint/${id}`); }} />}

      {b.status === "generating" && (
        <Card className="mb-5 p-5"><ol className="space-y-1.5">{b.progress.map((p, i) => <li key={i} className="flex items-center gap-2 text-sm"><CheckCircle2 className="size-4 text-ok" />{p.step}</li>)}
          <li className="flex items-center gap-2 text-sm text-muted"><Loader2 className="size-4 animate-spin" /> Working…</li></ol></Card>
      )}
      {b.status === "failed" && <div className="mb-5"><Alert tone="bad" title="Generation failed">{b.error}</Alert></div>}

      {b.status !== "generating" && b.status !== "failed" && (
        <>
          {(b.validation?.errors?.length > 0 || b.validation?.warnings?.length > 0) ? (
            <Card className="mb-5 p-4">
              <div className="mb-2 text-sm font-semibold">Symbolic check</div>
              {b.validation.errors.map((e, i) => <div key={i} className="flex gap-2 text-[13px] text-bad"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{e}</div>)}
              {b.validation.warnings.map((e, i) => <div key={i} className="flex gap-2 text-[13px] text-warn"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{e}</div>)}
              {b.validation.errors.length > 0 && <p className="mt-2 text-xs text-muted">Errors must be fixed before publishing, edit the section, or ask AI to fix them.</p>}
            </Card>
          ) : <div className="mb-5"><Alert tone="ok">Symbolic check passed: every rule, signal, action and agent references things that exist.</Alert></div>}

          {editable && (
            <Card className="mb-5 flex flex-wrap items-center gap-2 p-3">
              <Wand2 className="ml-1 size-4 text-accent" />
              <Input className="min-w-[240px] flex-1" value={refine} onChange={(e) => setRefine(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && refine.trim() && askAI()} />
              <Button loading={busy === "refine"} disabled={!refine.trim()} onClick={askAI}>Ask AI</Button>
            </Card>
          )}

          <Card>
            <div className="flex items-center justify-between gap-2 px-4 pt-2">
              <Tabs<Tab> value={tab} onChange={setTab} tabs={[{ id: "overview", label: "Overview" }, { id: "agents", label: `Agent team (${(c.agents || []).length})` },
                { id: "rules", label: `Rules & facts (${(c.rules || []).length})` }, { id: "actions", label: `Actions & approvals (${(c.actions || []).length})` },
                { id: "watch", label: `Watch rules (${(c.watch_rules || []).length})` },
                { id: "ontology", label: "Ontology" }, { id: "kpis", label: "KPIs" }]} />
              {editable && <Button size="sm" variant="ghost" icon={<Code2 className="size-4" />} onClick={openJson}>Edit JSON</Button>}
            </div>
            <div className="p-5">
              {tab === "overview" && <Overview c={c} b={b} />}
              {tab === "agents" && <Agents c={c} />}
              {tab === "rules" && <Rules c={c} />}
              {tab === "actions" && <Actions c={c} editable={editable} onSave={(content) => save(content, "Actions saved")} saving={busy === "save"} />}
              {tab === "watch" && <WatchRules c={c} />}
              {tab === "ontology" && <Ontology c={c} />}
              {tab === "kpis" && <Kpis c={c} />}
            </div>
          </Card>
        </>
      )}

      <Modal open={!!json} onClose={() => setJson(null)} wide title={`Edit ${json?.key} as JSON`}>
        <Textarea rows={22} className="font-mono text-xs" value={json?.text || ""} onChange={(e) => setJson({ ...json!, text: e.target.value })} spellCheck={false} />
        <p className="mt-2 text-xs text-muted">Saving re-runs the symbolic check. Editing a published version creates a new draft; the live version is untouched until you publish.</p>
        <div className="mt-3 flex justify-end gap-2"><Button variant="ghost" onClick={() => setJson(null)}>Cancel</Button><Button variant="primary" onClick={applyJson}>Apply</Button></div>
      </Modal>
    </>
  );
}

function Overview({ c, b }: { c: any; b: BP }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <div><div className="text-xs font-semibold uppercase tracking-wide text-faint">What Aria XAI understood</div><p className="mt-1 text-[15px] leading-relaxed">{c.summary}</p></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div><div className="text-xs font-semibold uppercase tracking-wide text-faint">Industry (inferred)</div><div className="mt-1">{c.industry || "-"}</div></div>
          <div><div className="text-xs font-semibold uppercase tracking-wide text-faint">Business model</div><div className="mt-1">{c.business_model || "-"}</div></div>
        </div>
        <div><div className="text-xs font-semibold uppercase tracking-wide text-faint">Primary users</div><div className="mt-1 flex flex-wrap gap-1.5">{(c.primary_users || []).map((u: string) => <Badge key={u}>{u}</Badge>)}</div></div>
        <div><div className="text-xs font-semibold uppercase tracking-wide text-faint">Starter questions</div>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{(c.starter_questions || []).map((q: string) => <li key={q}>{q}</li>)}</ul></div>
      </div>
      <div className="rounded-lg bg-panel2 p-4 text-sm">
        <div className="text-xs font-semibold uppercase tracking-wide text-faint">Learned from</div>
        <ul className="mt-2 space-y-1.5">
          <li>{b.sources?.described ? "✓ Your product description" : "– No description"}</li>
          <li>✓ {b.sources?.documents?.length || 0} document(s){b.sources?.documents?.length ? <span className="text-muted">: {b.sources.documents.join(", ")}</span> : null}</li>
          <li>✓ {b.sources?.connections?.length || 0} data connection(s){b.sources?.connections?.length ? <span className="text-muted">: {b.sources.connections.join(", ")}</span> : null}</li>
          {b.sources?.model && <li className="text-muted">Model: {b.sources.model}</li>}
        </ul>
      </div>
    </div>
  );
}

function Agents({ c }: { c: any }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {[["Aria, Orchestrator", "Plans each request, delegates to Aria Analyst or Aria Executor, and writes the final answer. Never acts directly."],
        ["Aria Analyst", "Reads: documents, data and APIs. Delegates investigations to the specialists below. Never changes anything."],
        ["Aria Executor", "Writes: proposes a plan of actions; nothing runs until the responsible person approves and becomes accountable."],
        ["Aria Watch", "Background: investigates product events that match the watch rules and suggests changes to the owner role."]].map(([n, d]) => (
        <div key={n} className="rounded-lg border border-accent/40 bg-accentsoft/50 p-4">
          <div className="flex items-center gap-2"><Bot className="size-4 text-accent" /><b>{n}</b><Badge tone="accent">built in</Badge></div>
          <p className="mt-1 text-[13px] text-muted">{d}</p>
        </div>))}
      {(c.agents || []).map((a: any) => (
        <div key={a.id} className="rounded-lg border border-line p-4">
          <div className="flex items-center gap-2"><Bot className="size-4 text-muted" /><b>{a.name}</b><span className="font-mono text-xs text-faint">{a.id}</span></div>
          <p className="mt-1 text-[13px]">{a.purpose}</p>
          <p className="mt-2 text-[13px] text-muted">{a.instructions}</p>
          <div className="mt-3 flex flex-wrap gap-1">{(a.tools || []).map((t: string) => <Badge key={t} tone="info">{t}</Badge>)}</div>
          {(a.data_scope || []).length > 0 && <div className="mt-2 text-xs text-muted">Data: {a.data_scope.map((d: any) => `${(d.tables || ["*"]).join(", ")}`).join("; ")}</div>}
          {(a.actions || []).length > 0 && <div className="mt-1 text-xs text-muted">May request: {a.actions.join(", ")}</div>}
        </div>
      ))}
    </div>
  );
}

function Rules({ c }: { c: any }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 font-semibold">Hard rules <span className="text-xs font-normal text-muted">- deterministic; a failing rule blocks the action</span></h3>
        <div className="space-y-2">
          {(c.rules || []).map((r: any) => (
            <div key={r.id} className="rounded-lg border border-line p-3">
              <div className="flex flex-wrap items-center gap-2"><b className="text-sm">{r.description}</b><span className="font-mono text-xs text-faint">{r.id}</span>
                <Badge tone={r.on_fail === "INVALID" ? "bad" : "warn"}>{r.on_fail === "INVALID" ? "blocks" : "needs evidence"}</Badge>
                <span className="text-xs text-muted">applies to {r.applies_to?.join(", ")}</span></div>
              <div className="mt-1.5 rounded bg-panel2 px-2 py-1 font-mono text-xs">{describe(r.condition)}</div>
              {r.citation && <div className="mt-1 text-xs text-muted">Source: {r.citation}</div>}
            </div>
          ))}
          {!(c.rules || []).length && <p className="text-sm text-muted">No hard rules.</p>}
        </div>
      </div>
      {(c.signals || []).length > 0 && (
        <div>
          <h3 className="mb-2 font-semibold">Soft signals <span className="text-xs font-normal text-muted">- weighted evidence, discretised by the gate before any rule sees it</span></h3>
          <div className="grid gap-2 md:grid-cols-2">
            {c.signals.map((s: any) => (
              <div key={s.id} className="rounded-lg border border-line p-3 text-sm">
                <b>{s.description}</b> <span className="font-mono text-xs text-faint">signals.{s.id}</span>
                <div className="mt-1 text-xs text-muted"><Badge className="mr-1">{s.combine === "noisy_or" ? "noisy-OR" : "weighted sum"}</Badge>{s.inputs.map((i: any) => `${i.fact}×${i.weight}${i.invert ? " (inverted)" : ""}`).join(s.combine === "noisy_or" ? " or " : " + ")}</div>
                <div className="mt-1 text-xs">TRUE ≥ {s.assert_above} · FALSE ≤ {s.deny_below} · in between = insufficient evidence</div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div>
        <h3 className="mb-2 font-semibold">Fact vocabulary <span className="text-xs font-normal text-muted">- what agents must establish before requesting an action</span></h3>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="py-1.5 pr-3">Fact</th><th className="pr-3">Type</th><th>Meaning</th></tr></thead>
          <tbody>{(c.facts || []).map((f: any) => <tr key={f.name} className="border-t border-line"><td className="py-1.5 pr-3 font-mono text-xs">{f.name}</td><td className="pr-3"><Badge>{f.type}</Badge></td><td className="text-[13px]">{f.description}{f.unit && <span className="text-muted"> ({f.unit})</span>}</td></tr>)}</tbody></table></div>
      </div>
    </div>
  );
}

function DbExecutor({ ex, conns, editable, onChange }: { ex: any; conns: any[]; editable: boolean; onChange: (ex: any) => void }) {
  const conn = conns.find((x) => x.id === ex.connection_id);
  const cols: string[] = conn?.tables.find((t: any) => t.name === ex.table)?.columns.map((c: any) => c.name) || [];
  const set = (p: any) => onChange({ ...ex, ...p });
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-4">
        <Field label="Connection"><Select disabled={!editable} value={ex.connection_id || ""} onChange={(e) => set({ connection_id: e.target.value, table: "", columns: [] })}>
          {conns.filter((x) => x.kind !== "rest").map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select></Field>
        <Field label="Table"><Select disabled={!editable} value={ex.table || ""} onChange={(e) => set({ table: e.target.value, columns: [], key_column: "" })}>
          <option value="">Choose…</option>{(conn?.tables || []).map((t: any) => <option key={t.name}>{t.name}</option>)}</Select></Field>
        <Field label="Operation"><Select disabled={!editable} value={ex.operation} onChange={(e) => set({ operation: e.target.value })}><option value="update">update one row</option><option value="insert">insert a row</option></Select></Field>
        {ex.operation === "update" && <Field label="Key column"><Select disabled={!editable} value={ex.key_column || ""} onChange={(e) => set({ key_column: e.target.value })}>
          <option value="">Choose…</option>{cols.map((c) => <option key={c}>{c}</option>)}</Select></Field>}
      </div>
      <div><div className="mb-1 text-[13px] font-medium">Columns it may write</div>
        <div className="flex flex-wrap gap-1.5">{cols.filter((c) => c !== ex.key_column).map((c) => {
          const on = (ex.columns || []).includes(c);
          return <button key={c} type="button" disabled={!editable} onClick={() => set({ columns: on ? ex.columns.filter((x: string) => x !== c) : [...(ex.columns || []), c] })}
            className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-accent bg-accentsoft text-accent" : "border-line text-muted"}`}>{c}</button>;
        })}{!cols.length && <span className="text-xs text-muted">Choose a table</span>}</div></div>
      {conn && !conn.allow_writes && <Alert tone="warn">Writes are disabled on “{conn.name}”. An admin can enable them in Understand my product → Connect data.</Alert>}
    </div>
  );
}

function Actions({ c, editable, onSave, saving }: { c: any; editable: boolean; onSave: (content: any) => void; saving: boolean }) {
  const [rows, setRows] = useState<any[]>(c.actions || []);
  const [conns, setConns] = useState<any[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  useEffect(() => {
    api<any[]>("/api/data/connections").then(setConns).catch(() => {});
    api<any[]>("/api/roles").then((r) => setRoles(r.map((x) => x.name))).catch(() => {});
  }, []);
  useEffect(() => setRows(c.actions || []), [c.actions]);
  const dirty = JSON.stringify(rows) !== JSON.stringify(c.actions || []);
  const upd = (i: number, patch: any) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  if (!rows.length) return <p className="text-sm text-muted">No actions, this team answers questions but does not change anything.</p>;
  return (
    <div className="space-y-3">
      <datalist id="role-names">{roles.map((r) => <option key={r} value={r} />)}</datalist>
      <Alert tone="info">Aria Executor proposes a plan → the person approves it and becomes accountable → hard rules must pass → Sentinel checks the step against <b>that person's</b> authority (allowed actions, approval limit, HIGH-risk clearance). Anything beyond it goes to the action's <b>owner role</b>. Requests with no person in the loop (API / widget) only run when LOW risk or below the auto-approval limit.</Alert>
      {rows.map((a, i) => (
        <div key={a.name} className="rounded-lg border border-line p-4">
          <div className="flex flex-wrap items-center gap-2"><b className="font-mono text-sm">{a.name}</b><Badge tone={riskTone(a.risk)}>{a.risk} risk</Badge><span className="text-[13px] text-muted">{a.description}</span></div>
          <div className="mt-3 grid gap-3 md:grid-cols-4">
            <Field label="Risk"><Select value={a.risk} disabled={!editable} onChange={(e) => upd(i, { risk: e.target.value })}>{["LOW", "MEDIUM", "HIGH"].map((r) => <option key={r}>{r}</option>)}</Select></Field>
            <Field label="Auto-run below (API / widget)" hint={a.amount_fact ? `amount = ${a.amount_fact}` : "no amount fact"}>
              <Input type="number" disabled={!editable || !a.amount_fact} value={a.auto_approve_below ?? ""} onChange={(e) => upd(i, { auto_approve_below: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
            <Field label="Owner role" hint="Approves escalations & Aria Watch suggestions">
              <Input disabled={!editable} list="role-names" value={a.owner_role || ""} onChange={(e) => upd(i, { owner_role: e.target.value })} /></Field>
            <div className="pt-6"><Toggle checked={!!a.always_review} onChange={(v) => editable && upd(i, { always_review: v })} label="Always needs the owner" /></div>
          </div>
          <div className="mt-3 rounded-lg bg-panel2/60 p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-[13px]"><b>When approved, carry it out by</b>
              <Select className="w-auto" disabled={!editable} value={a.executor?.type || "webhook"}
                onChange={(e) => upd(i, { executor: e.target.value === "database" ? { type: "database", connection_id: conns[0]?.id, table: "", operation: "update", key_column: "", columns: [] } : { type: "webhook", url: "" } })}>
                <option value="webhook">calling your webhook</option><option value="database">writing to a connected database</option></Select></div>
            {(a.executor?.type || "webhook") === "webhook" ? (
              <Field label="Webhook URL" hint="Signed POST with the decision_id and the accountable person"><Input disabled={!editable} value={a.executor?.url || ""} onChange={(e) => upd(i, { executor: { ...a.executor, type: "webhook", url: e.target.value } })} /></Field>
            ) : <DbExecutor ex={a.executor} conns={conns} editable={editable} onChange={(ex) => upd(i, { executor: ex })} />}
          </div>
          {(a.required_facts || []).length > 0 && <div className="mt-2 text-xs text-muted">Required facts: {a.required_facts.join(", ")}</div>}
        </div>
      ))}
      {editable && dirty && <div className="flex justify-end"><Button variant="primary" loading={saving} onClick={() => onSave({ ...c, actions: rows })}>Save actions</Button></div>}
    </div>
  );
}

function WatchRules({ c }: { c: any }) {
  const rules = c.watch_rules || [];
  return (
    <div className="space-y-3">
      <Alert tone="info">Aria Watch checks every event your product sends against these rules. Events that match no rule are recorded and ignored without calling the model. Matching events are investigated, and a suggestion is made to the owner only when a change would clearly help.</Alert>
      {!rules.length && <p className="text-sm text-muted">No watch rules, Aria Watch will ignore every event. Use “Ask AI to refine” to add some.</p>}
      {rules.map((w: any) => (
        <div key={w.id} className="rounded-lg border border-line p-3">
          <div className="flex flex-wrap items-center gap-2"><Eye className="size-4 text-muted" /><b className="text-sm">{w.why}</b><span className="font-mono text-xs text-faint">{w.id}</span>
            {w.owner_role && <Badge>owner: {w.owner_role}</Badge>}</div>
          <div className="mt-1.5 rounded bg-panel2 px-2 py-1 font-mono text-xs">on <b>{w.event_type}</b>{w.when && <> when {describe(w.when)}</>}</div>
        </div>
      ))}
    </div>
  );
}

function Ontology({ c }: { c: any }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {(c.ontology || []).map((o: any) => (
        <div key={o.name} className="rounded-lg border border-line p-3">
          <b>{o.name}</b>{o.source?.table && <span className="ml-2 font-mono text-xs text-muted">↳ {o.source.table}</span>}
          <p className="mt-1 text-[13px] text-muted">{o.description}</p>
          {(o.fields || []).length > 0 && <div className="mt-2 flex flex-wrap gap-1">{o.fields.map((f: any) => <Badge key={f.name}>{f.name}</Badge>)}</div>}
        </div>
      ))}
    </div>
  );
}

function Kpis({ c }: { c: any }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {(c.kpis || []).map((k: any) => (
        <div key={k.name} className="rounded-lg border border-line p-3"><b>{k.name}</b><p className="mt-1 text-[13px] text-muted">{k.description}</p>{k.how_to_measure && <p className="mt-1 text-xs text-faint">{k.how_to_measure}</p>}</div>
      ))}
      {!(c.kpis || []).length && <p className="text-sm text-muted">No KPIs.</p>}
    </div>
  );
}

// ------------------------------------------------------------------ business rules via YAML
type Change = { section: string; label: string; id: string; change: "added" | "removed" | "changed"; fields: { field: string; before: string; after: string }[] };

function ChangeList({ changes }: { changes: Change[] }) {
  if (!changes.length) return <p className="text-sm text-muted">No differences.</p>;
  const icon = { added: <Plus className="size-3.5 text-ok" />, removed: <Minus className="size-3.5 text-bad" />, changed: <Pencil className="size-3.5 text-warn" /> };
  return (
    <ul className="space-y-2">
      {changes.map((c, i) => (
        <li key={i} className="rounded-lg border border-line p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">{icon[c.change]}<b>{c.label}</b><span className="font-mono">{c.id}</span>
            <Badge tone={c.change === "added" ? "ok" : c.change === "removed" ? "bad" : "warn"}>{c.change}</Badge></div>
          {c.fields.length > 0 && (
            <table className="mt-2 w-full text-xs"><tbody>
              {c.fields.map((f) => (
                <tr key={f.field} className="border-t border-line align-top">
                  <td className="w-28 py-1 pr-2 font-mono text-muted">{f.field}</td>
                  <td className="py-1 pr-2"><span className="rounded bg-badsoft px-1 font-mono text-bad line-through decoration-1">{f.before}</span></td>
                  <td className="py-1"><span className="rounded bg-oksoft px-1 font-mono text-ok">{f.after}</span></td>
                </tr>))}
            </tbody></table>)}
        </li>))}
    </ul>
  );
}

function UploadRules({ onClose, onApplied, canPublish }: { onClose: () => void; onApplied: (id: string) => void; canPublish: boolean }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [file, setFile] = useState("");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [live, setLive] = useState(canPublish);
  const check = async (t: string) => {
    setBusy("check"); setRes(null);
    try { setRes(await api("/api/blueprints/rules/preview", { body: { yaml: t } })); } catch (e: any) { setRes({ ok: false, errors: [e.message] }); } finally { setBusy(""); }
  };
  const pick = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > 2_000_000) { setRes({ ok: false, errors: ["The file is too large (over 2 MB) to be a business-rules file."] }); return; }
    const t = await f.text();
    setFile(f.name); setText(t); check(t);
  };
  const apply = async () => {
    setBusy("apply");
    try {
      const r = await api<any>("/api/blueprints/rules/apply", { body: { yaml: text, publish: live } });
      toast(`Version ${r.version} ${r.status === "published" ? "is now live" : "saved as a draft"}`);
      onApplied(r.id);
    } catch (e: any) { toast(e.details ? `${e.message}: ${e.details[0]}` : e.message, "bad"); } finally { setBusy(""); }
  };
  return (
    <Modal open onClose={onClose} wide title="Upload business rules (YAML)">
      <div className="space-y-4">
        <p className="text-[13px] text-muted">Download the current rules, edit them, and upload the file here. Aria XAI checks that the file is valid and makes sense, then shows exactly what would change before anything is saved.</p>
        <Field label="Rules file (.yaml or .yml)"><Input type="file" accept=".yaml,.yml,text/yaml,application/x-yaml" onChange={(e) => pick(e.target.files?.[0])} className="pt-1.5" /></Field>
        {busy === "check" && <div className="flex items-center gap-2 text-sm text-muted"><Loader2 className="size-4 animate-spin" /> Checking {file}…</div>}
        {res && !res.ok && (
          <Alert tone="bad" title={<span className="inline-flex items-center gap-1.5"><FileWarning className="size-4" /> {res.stage === "rules" ? "The rules in this file do not hold together" : "This file was rejected"}</span>}>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">{(res.errors || []).slice(0, 12).map((e: string, i: number) => <li key={i}>{e}</li>)}</ul>
            {res.errors?.length > 12 && <div className="mt-1">and {res.errors.length - 12} more</div>}
          </Alert>
        )}
        {res?.ok && (
          <>
            {res.changes.length === 0 ? <Alert tone="info">This file is identical to version {res.base.version}. There is nothing to change.</Alert> : (
              <>
                <div className="text-sm font-semibold">From version {res.base.version} to version {res.base.version + 1}, these are the changes:</div>
                <ChangeList changes={res.changes} />
                {res.warnings?.length > 0 && <Alert tone="warn" title="Warnings">{res.warnings.slice(0, 6).map((w: string, i: number) => <div key={i}>{w}</div>)}</Alert>}
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                  {canPublish ? <Toggle checked={live} onChange={setLive} label="Make it live now" /> : <span className="text-xs text-muted">It will be saved as a draft for someone with publish permission.</span>}
                  <div className="flex gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
                    <Button variant="primary" loading={busy === "apply"} onClick={apply}>Yes, go with these changes</Button></div>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

function Versions({ list, current, canSwitch, onClose, onSwitched }: { list: BP[]; current: BP; canSwitch: boolean; onClose: () => void; onSwitched: () => void }) {
  const nav = useNavigate();
  const toast = useToast();
  const live = list.find((v) => v.status === "published");
  const [cmp, setCmp] = useState<{ title: string; changes: Change[] } | null>(null);
  const [busy, setBusy] = useState("");
  const compare = async (v: BP) => {
    if (!live) return;
    const r = await api<any>(`/api/blueprints/compare/${live.id}/${v.id}`);
    setCmp({ title: `From live version ${live.version} to version ${v.version}`, changes: r.changes });
  };
  const switchTo = async (v: BP) => {
    setBusy(v.id);
    try { await api(`/api/blueprints/${v.id}/publish`, { method: "POST" }); toast(`Version ${v.version} is now live`); onSwitched(); }
    catch (e: any) { toast(e.details ? `${e.message}: ${e.details[0]}` : e.message, "bad"); } finally { setBusy(""); }
  };
  return (
    <Modal open onClose={onClose} wide title="Versions">
      {cmp ? (
        <div className="space-y-3"><button onClick={() => setCmp(null)} className="text-sm text-accent">Back to versions</button>
          <div className="text-sm font-semibold">{cmp.title}</div><ChangeList changes={cmp.changes} /></div>
      ) : (
        <ul className="divide-y divide-line">
          {list.map((v) => (
            <li key={v.id} className="flex flex-wrap items-center gap-3 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2"><b>Version {v.version}</b>
                  <Badge tone={v.status === "published" ? "ok" : v.status === "failed" ? "bad" : v.status === "archived" ? "neutral" : "accent"}>{v.status === "published" ? "live" : v.status}</Badge>
                  {v.id === current.id && <span className="text-xs text-muted">viewing</span>}</div>
                <div className="truncate text-xs text-muted">{fmtDate(v.created_at)}{v.note && `, ${v.note}`}</div>
              </div>
              <Button size="sm" onClick={() => { nav(`/blueprint/${v.id}`); onClose(); }}>View</Button>
              {live && v.id !== live.id && v.status !== "generating" && v.status !== "failed" && <Button size="sm" onClick={() => compare(v)}>Compare with live</Button>}
              {canSwitch && (v.status === "draft" || v.status === "archived") &&
                <Button size="sm" variant="primary" loading={busy === v.id} onClick={() => switchTo(v)}>Switch to this version</Button>}
            </li>))}
        </ul>
      )}
    </Modal>
  );
}
