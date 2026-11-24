import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowRight, Bot, CheckCircle2, ChevronRight, Download, FileWarning, FlaskConical, History, Loader2, Lock, Minus, Pencil, Plus, Rocket, RotateCcw, Trash2, Upload, User, Wand2 } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Badge, Button, Card, CardHead, ErrorBox, Field, Input, Loading, Modal, PageHead, Select, Tabs, Textarea, Toggle, cx, useAsync, useToast } from "../components/ui";

type BP = { id: string; version: number; status: string; content: any; provenance: Record<string, Record<string, any>>;
  validation: { errors: string[]; warnings: string[]; ok: boolean }; progress: any[]; sources: any; error: string; note: string;
  created_at: string; published_at: string | null };
type Spec = { type: "bool" | "int" | "choice" | "text"; label: string; default: any; min?: number; max?: number; choices?: string[]; hint?: string };
type Layer = { id: string; number: number; name: string; runs_on: string; purpose: string; sections: string[]; settings_spec: Record<string, Spec>;
  settings: Record<string, any>; defaults: Record<string, any>; can_edit_settings: boolean; can_edit_records: boolean; readonly: boolean };
type Studio = { layers: Layer[]; original: { id: string; version: number } | null };

export function describe(c: any): string {
  if (!c || typeof c !== "object") return String(c ?? "");
  if (c.all) return "(" + c.all.map(describe).join(" AND ") + ")";
  if (c.any) return "(" + c.any.map(describe).join(" OR ") + ")";
  if (c.not) return "NOT " + describe(c.not);
  if ("exists" in c) return `${c.path} ${c.exists ? "is known" : "is unknown"}`;
  if ("is" in c) return `${c.path} is ${c.is}`;
  return `${c.path} ${c.op ?? "=="} ${typeof c.value === "string" && c.value.startsWith("$") ? c.value.slice(1) : JSON.stringify(c.value)}`;
}
// "Describe a change and AI drafts it" only where people write rules: the rule engine and the approval policy
const ASK_AI = ["cognitive", "governance"];
const riskTone =(r: string) => (r === "HIGH" ? "bad" : r === "MEDIUM" ? "warn" : "ok") as "bad" | "warn" | "ok";
const CHOICE: Record<string, string> = { plain: "Plain", friendly: "Friendly", formal: "Formal", short: "Short", standard: "Standard", detailed: "Detailed",
  match: "Same language as the person", English: "Always English", teal: "Teal", indigo: "Indigo", amber: "Amber", rose: "Rose", slate: "Slate" };

// ------------------------------------------------------------------ what each record section is, and how it is edited
type F = { k: string; label: string; kind: "text" | "long" | "number" | "bool" | "enum" | "list" | "json" | "tools" | "role" | "executor"; options?: string[]; hint?: string };
const SECTIONS: Record<string, { title: string; one: string; help: string; key: string; fields: F[]; blank: any }> = {
  facts: { title: "Facts", one: "fact", key: "name", help: "What the model must establish before an action is checked. The rules only ever see these.",
    fields: [{ k: "name", label: "Name", kind: "text", hint: "snake_case, for example order_amount" }, { k: "type", label: "Type", kind: "enum", options: ["number", "boolean", "string"] },
      { k: "unit", label: "Unit", kind: "text" }, { k: "description", label: "Meaning", kind: "long" }],
    blank: { name: "", type: "number", unit: "", description: "" } },
  signals: { title: "Soft signals and gate", one: "signal", key: "id", help: "Evidence scored from 0 to 1. The gate turns each score into true, false or not enough evidence.",
    fields: [{ k: "id", label: "Id", kind: "text" }, { k: "description", label: "What it indicates", kind: "long" },
      { k: "combine", label: "How evidence combines", kind: "enum", options: ["weighted_sum", "noisy_or"], hint: "Noisy-OR: any one strong input is enough. Weights must then be 0 to 1." },
      { k: "inputs", label: "Inputs", kind: "json", hint: "A list like [{\"fact\": \"days_late\", \"weight\": 0.6, \"max\": 30}]" },
      { k: "assert_above", label: "True when the score is at least", kind: "number" }, { k: "deny_below", label: "False when the score is at most", kind: "number" }],
    blank: { id: "", description: "", combine: "weighted_sum", inputs: [], assert_above: 0.7, deny_below: 0.3 } },
  rules: { title: "Hard rules", one: "rule", key: "id", help: "Deterministic checks with a source. A failing rule blocks the action or asks for more evidence.",
    fields: [{ k: "id", label: "Id", kind: "text" }, { k: "description", label: "Rule", kind: "long" },
      { k: "applies_to", label: "Applies to actions", kind: "list", hint: "Comma separated action names, or * for all" },
      { k: "condition", label: "Condition", kind: "json", hint: "For example {\"path\": \"order_amount\", \"op\": \"<=\", \"value\": 500}" },
      { k: "on_fail", label: "When it fails", kind: "enum", options: ["INVALID", "INSUFFICIENT_EVIDENCE"] },
      { k: "message", label: "Message shown when it fails", kind: "text" }, { k: "citation", label: "Source (document and page)", kind: "text" }],
    blank: { id: "", description: "", applies_to: ["*"], condition: { path: "", op: "==", value: "" }, on_fail: "INVALID", message: "", citation: "" } },
  kpis: { title: "Goals (KPIs)", one: "goal", key: "name", help: "What the team should improve. Aria Watch suggests changes that move these.",
    fields: [{ k: "name", label: "Name", kind: "text" }, { k: "description", label: "Why it matters", kind: "long" }, { k: "how_to_measure", label: "How to measure it", kind: "long" }],
    blank: { name: "", description: "", how_to_measure: "" } },
  watch_rules: { title: "Watch rules", one: "watch rule", key: "id", help: "Product events Aria Watch investigates. Every other event is recorded and ignored without calling the model.",
    fields: [{ k: "id", label: "Id", kind: "text" }, { k: "event_type", label: "Event type", kind: "text", hint: "Exact type, or a prefix with *, for example order.*" },
      { k: "when", label: "Only when (optional)", kind: "json", hint: "Condition over data.*, for example {\"path\": \"data.amount\", \"op\": \">\", \"value\": 1000}" },
      { k: "why", label: "What it watches for", kind: "long" }, { k: "owner_role", label: "Owner role", kind: "role", hint: "Receives the suggestions" }],
    blank: { id: "", event_type: "", when: null, why: "", owner_role: "Reviewer" } },
  ontology: { title: "Business entities", one: "entity", key: "name", help: "The things your business works with, mapped to where they live in your data.",
    fields: [{ k: "name", label: "Name", kind: "text" }, { k: "description", label: "Description", kind: "long" },
      { k: "source", label: "Where it lives", kind: "json", hint: "{\"connection_id\": \"...\", \"table\": \"...\"}, or leave empty" },
      { k: "key_fields", label: "Key fields", kind: "list" }, { k: "fields", label: "Fields", kind: "json", hint: "A list like [{\"name\": \"status\", \"type\": \"string\"}]" }],
    blank: { name: "", description: "", source: null, key_fields: [], fields: [] } },
  agents: { title: "Specialist sub-agents", one: "sub-agent", key: "id", help: "Read-only specialists the lead agents delegate to. Only Aria Executor can propose changes.",
    fields: [{ k: "id", label: "Id", kind: "text" }, { k: "name", label: "Name", kind: "text" }, { k: "purpose", label: "Purpose", kind: "long" },
      { k: "instructions", label: "Instructions", kind: "long" }, { k: "tools", label: "Tools", kind: "tools", options: ["query_data", "call_api", "search_knowledge", "check_rules"] },
      { k: "data_scope", label: "Data it may read", kind: "json", hint: "A list like [{\"connection_id\": \"*\", \"tables\": [\"orders\"]}]" },
      { k: "actions", label: "Actions it may suggest", kind: "list" }],
    blank: { id: "", name: "", purpose: "", instructions: "", tools: ["search_knowledge"], data_scope: [], actions: [] } },
  starter_questions: { title: "Starter questions", one: "question", key: "", help: "Shown to people when they open the agent team.", fields: [], blank: "" },
  actions: { title: "Actions and approvals", one: "action", key: "name", help: "The only changes the agents can make. Each one is approved by a person, who is accountable for it.",
    fields: [{ k: "name", label: "Name", kind: "text", hint: "UPPER_SNAKE_CASE" }, { k: "description", label: "What it does", kind: "long" },
      { k: "risk", label: "Risk", kind: "enum", options: ["LOW", "MEDIUM", "HIGH"] }, { k: "owner_role", label: "Owner role", kind: "role", hint: "Approves escalations and Aria Watch suggestions" },
      { k: "required_facts", label: "Facts it needs", kind: "list" }, { k: "amount_fact", label: "Fact that holds the amount", kind: "text" },
      { k: "auto_approve_below", label: "API and widget may run it below", kind: "number", hint: "Leave empty to always need a person" },
      { k: "always_review", label: "Always needs the owner role", kind: "bool" }, { k: "executor", label: "When approved, carry it out by", kind: "executor" }],
    blank: { name: "", description: "", risk: "MEDIUM", owner_role: "Reviewer", required_facts: [], amount_fact: "", auto_approve_below: null, always_review: false, executor: { type: "webhook", url: "" } } },
};

function summary(s: string, r: any): { title: ReactNode; detail: ReactNode } {
  switch (s) {
    case "facts": return { title: <span className="font-mono text-[13px]">{r.name}</span>, detail: <><Badge className="mr-1.5">{r.type}</Badge>{r.description}{r.unit && <span className="text-muted"> ({r.unit})</span>}</> };
    case "signals": return { title: r.description, detail: <><Badge className="mr-1.5">{r.combine === "noisy_or" ? "noisy-OR" : "weighted sum"}</Badge>
      {(r.inputs || []).map((i: any) => `${i.fact}×${i.weight}${i.invert ? " (inverted)" : ""}`).join(r.combine === "noisy_or" ? " or " : " + ")}
      <div className="mt-0.5 text-xs text-muted">Gate: true at {r.assert_above} or more, false at {r.deny_below} or less, otherwise not enough evidence</div></> };
    case "rules": return { title: r.description, detail: <><Badge tone={r.on_fail === "INVALID" ? "bad" : "warn"} className="mr-1.5">{r.on_fail === "INVALID" ? "blocks" : "needs evidence"}</Badge>
      <span className="font-mono text-xs">{describe(r.condition)}</span><div className="mt-0.5 text-xs text-muted">Applies to {(r.applies_to || []).join(", ")}{r.citation && `. Source: ${r.citation}`}</div></> };
    case "kpis": return { title: r.name, detail: <>{r.description}{r.how_to_measure && <div className="mt-0.5 text-xs text-muted">{r.how_to_measure}</div>}</> };
    case "watch_rules": return { title: r.why, detail: <><span className="font-mono text-xs">on {r.event_type}{r.when && ` when ${describe(r.when)}`}</span>{r.owner_role && <Badge className="ml-1.5">owner: {r.owner_role}</Badge>}</> };
    case "ontology": return { title: r.name, detail: <>{r.description}{r.source?.table && <span className="ml-1 font-mono text-xs text-muted">in {r.source.table}</span>}</> };
    case "agents": return { title: r.name, detail: <>{r.purpose}<div className="mt-1 flex flex-wrap gap-1">{(r.tools || []).map((t: string) => <Badge key={t} tone="info">{t}</Badge>)}</div></> };
    case "actions": return { title: <span className="font-mono text-[13px]">{r.name}</span>, detail: <><Badge tone={riskTone(r.risk)} className="mr-1.5">{r.risk} risk</Badge>{r.description}
      <div className="mt-0.5 text-xs text-muted">Owner: {r.owner_role}{r.always_review && ", always needs the owner"}. Carried out by {r.executor?.type === "database" ? `a database ${r.executor.operation} on ${r.executor.table || "?"}` : r.executor?.url ? "your webhook" : "a webhook (not set yet)"}.</div></> };
    default: return { title: String(r), detail: null };
  }
}

// ------------------------------------------------------------------ page
export default function StudioPage() {
  const { bid } = useParams();
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const { can } = useAuth();
  const toast = useToast();
  const studio = useAsync<Studio>(() => api("/api/studio"));
  const list = useAsync<BP[]>(() => api("/api/blueprints"));
  const id = bid || list.data?.find((b) => b.status === "published")?.id || list.data?.[0]?.id;
  const bp = useAsync<BP | null>(() => (id ? api(`/api/blueprints/${id}`) : Promise.resolve(null)), [id]);
  const [refine, setRefine] = useState("");
  const [busy, setBusy] = useState("");
  const [modal, setModal] = useState<"" | "versions" | "upload" | "reset">("");
  const layerId = sp.get("layer");

  useEffect(() => {
    if (bp.data?.status !== "generating") return;
    const t = setInterval(() => bp.reload(), 2000);
    return () => clearInterval(t);
  }, [bp.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (studio.loading || list.loading || (id && bp.loading && !bp.data)) return <Loading />;
  if (studio.error || list.error) return <ErrorBox error={(studio.error || list.error)!} />;
  const layers = studio.data!.layers;
  const hasRecords = !!bp.data && bp.data.status !== "generating" && bp.data.status !== "failed";
  if (!layerId || !hasRecords) return (
    <>
      <PageHead title="Studio" sub="The six layers of the Aria XAI framework. Open a layer to see, add, edit or reset its rules, guardrails and settings." />
      {!hasRecords && <div className="mb-4"><Alert tone="info" title={bp.data?.status === "generating" ? "Aria XAI is working on your product" : "The layers fill in once Aria XAI understands your product"}>
        {bp.data?.status !== "generating" && can("blueprint:create") && <Link to="/understand" className="font-medium underline">Understand my product</Link>}</Alert></div>}
      {hasRecords && <div className="mb-5"><LayerTabs layers={layers} value="overview" onChange={(id) => setSp(id === "overview" ? {} : { layer: id })} /></div>}
      {hasRecords && bp.data!.content?.summary && <Card className="mb-5 p-5"><div className="text-xs font-semibold uppercase tracking-wide text-faint">What Aria XAI understood</div>
        <p className="mt-1 text-[14px] leading-relaxed">{bp.data!.content.summary}</p>
        <p className="mt-2 text-[13px] text-muted">{bp.data!.content.industry && <>Inferred industry: <b className="text-fg">{bp.data!.content.industry}</b> · </>}Version {bp.data!.version}, {bp.data!.status === "published" ? "live" : bp.data!.status}</p></Card>}
      <Card className="overflow-hidden">
        {layers.map((l) => {
          const n = l.sections.reduce((t, s) => t + ((bp.data?.content || {})[s] || []).length, 0);
          const row = (
            <>
              <span className="w-8 shrink-0 font-mono text-xs text-faint">{String(l.number).padStart(2, "0")}</span>
              <span className="min-w-0 flex-1"><span className="block text-[17px] font-medium">{l.name}</span>
                <span className="mt-0.5 block text-[13px] text-muted">{l.purpose}</span></span>
              <span className="hidden shrink-0 text-right sm:block"><span className="block font-mono text-xs text-muted">{l.runs_on}</span>
                {hasRecords && <span className="mt-1 block text-xs text-faint">{l.readonly ? "fills itself, nothing to configure" : <>{n} record(s){Object.keys(l.settings_spec).length > 0 && `, ${Object.keys(l.settings_spec).length} setting(s)`}</>}</span>}</span>
              {hasRecords && <ChevronRight className="size-4 shrink-0 text-faint" />}
            </>
          );
          const cls = "flex w-full items-center gap-4 border-b border-line px-5 py-5 text-left last:border-0";
          return hasRecords
            ? <button key={l.id} className={cx(cls, "hover:bg-panel2")} onClick={() => setSp({ layer: l.id })}>{row}</button>
            : <div key={l.id} className={cls}>{row}</div>;
        })}
      </Card>
    </>
  );
  const b = bp.data!;
  const layer = layers.find((l) => l.id === layerId) || layers[0];
  const ready = b.status !== "generating" && b.status !== "failed";
  const goTo = (r: BP) => { list.reload(); r.id !== b.id ? nav(`/studio/${r.id}?layer=${layer.id}`) : bp.setData(r); };

  const publish = async () => {
    setBusy("publish");
    try { await api(`/api/blueprints/${b.id}/publish`, { method: "POST" }); toast(`Version ${b.version} is live, the agent team now runs on it`); bp.reload(); list.reload(); }
    catch (e: any) { toast(e.details ? `${e.message}: ${e.details[0]}` : e.message, "bad"); bp.reload(); } finally { setBusy(""); }
  };
  const askAI = async () => {
    setBusy("refine");
    try { const r = await api<BP>(`/api/blueprints/${b.id}/refine`, { body: { instruction: refine, section: layer.name } }); setRefine(""); list.reload(); nav(`/studio/${r.id}?layer=${layer.id}`); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };

  return (
    <>
      <PageHead
        title={<span className="inline-flex flex-wrap items-center gap-2">Studio
          <Badge tone={b.status === "published" ? "ok" : b.status === "failed" ? "bad" : b.status === "generating" ? "info" : b.status === "archived" ? "neutral" : "accent"}>
            version {b.version} · {b.status === "published" ? "live" : b.status}</Badge></span>}
        sub={b.status === "generating" ? "Aria XAI is working…" : <>The six layers of the Aria XAI framework, as they run for your product.{b.note && <> {b.note}.</>}</>}
        right={<>
          <Button icon={<History className="size-4" />} onClick={() => setModal("versions")}>Versions ({list.data!.length})</Button>
          {ready && <a href={`/api/blueprints/${b.id}/rules.yaml`} download><Button icon={<Download className="size-4" />}>Download rules</Button></a>}
          {can("blueprint:edit") && <Button icon={<Upload className="size-4" />} onClick={() => setModal("upload")}>Upload rules</Button>}
          {can("blueprint:publish") && (b.status === "draft" || b.status === "archived") &&
            <Button variant="primary" icon={<Rocket className="size-4" />} loading={busy === "publish"} disabled={!b.validation?.ok} onClick={publish}>{b.status === "archived" ? "Switch to this version" : "Publish"}</Button>}
        </>} />
      {modal === "versions" && <Versions list={list.data!} current={b} canSwitch={can("blueprint:publish")} onClose={() => setModal("")} onSwitched={() => { list.reload(); bp.reload(); }} />}
      {modal === "upload" && <UploadRules onClose={() => setModal("")} canPublish={can("blueprint:publish")} onApplied={(nid) => { setModal(""); list.reload(); nav(`/studio/${nid}?layer=cognitive`); }} />}
      {modal === "reset" && <ResetLayer layer={layer} bp={b} onClose={() => setModal("")} onDone={(r) => { setModal(""); studio.reload(); if (r) goTo(r); }} />}

      {b.status === "generating" && (
        <Card className="mb-5 p-5"><ol className="space-y-1.5">{b.progress.map((p, i) => <li key={i} className="flex items-center gap-2 text-sm"><CheckCircle2 className="size-4 text-ok" />{p.step}</li>)}
          <li className="flex items-center gap-2 text-sm text-muted"><Loader2 className="size-4 animate-spin" /> Working…</li></ol></Card>
      )}
      {b.status === "failed" && <div className="mb-5"><Alert tone="bad" title="Generation failed">{b.error}</Alert></div>}

      {ready && (
        <>
          {b.status !== "published" && <div className="mb-4"><Alert tone="info">You are looking at version {b.version} ({b.status}). Changes here create or update a draft. The agent team keeps running on the live version until this one is published.</Alert></div>}
          {(b.validation?.errors?.length > 0 || b.validation?.warnings?.length > 0) ? (
            <Card className="mb-4 p-4">
              <div className="mb-2 text-sm font-semibold">Symbolic check</div>
              {b.validation.errors.map((e, i) => <div key={i} className="flex gap-2 text-[13px] text-bad"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{e}</div>)}
              {b.validation.warnings.map((e, i) => <div key={i} className="flex gap-2 text-[13px] text-warn"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{e}</div>)}
              {b.validation.errors.length > 0 && <p className="mt-2 text-xs text-muted">Fix the errors before publishing: edit the record, or ask AI to fix them.</p>}
            </Card>
          ) : <div className="mb-4"><Alert tone="ok">Symbolic check passed: every rule, signal, action and agent refers to things that exist.</Alert></div>}

          <div>
            <LayerTabs layers={layers} value={layer.id} onChange={(id) => setSp(id === "overview" ? {} : { layer: id })} />
            <div className="mt-5 min-w-0 space-y-5">
              <Card className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0"><div className="font-mono text-xs text-faint">Layer {String(layer.number).padStart(2, "0")}</div>
                    <h2 className="text-lg font-semibold">{layer.name}</h2><p className="mt-1 max-w-2xl text-[13px] text-muted">{layer.purpose}</p></div>
                  {!layer.readonly && (layer.can_edit_records || layer.can_edit_settings) && <Button icon={<RotateCcw className="size-4" />} onClick={() => setModal("reset")}>Reset to original</Button>}
                </div>
                {layer.can_edit_records && ASK_AI.includes(layer.id) && (
                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
                    <Wand2 className="size-4 text-accent" /><span className="text-[13px] text-muted">Describe a change to this layer and AI drafts it:</span>
                    <Input className="min-w-[220px] flex-1" value={refine} aria-label={`Change to ${layer.name}`} onChange={(e) => setRefine(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && refine.trim() && askAI()} />
                    <Button loading={busy === "refine"} disabled={!refine.trim()} onClick={askAI}>Ask AI</Button>
                  </div>
                )}
              </Card>

              <LayerBody key={layer.id} layer={layer} b={b} onSaved={goTo} onSettings={studio.reload} />
            </div>
          </div>
        </>
      )}
    </>
  );
}

function LayerTabs({ layers, value, onChange }: { layers: Layer[]; value: string; onChange: (id: string) => void }) {
  return (
    <Tabs<string> value={value} onChange={onChange}
      tabs={[{ id: "overview", label: "Overview" }, ...layers.map((l) => ({ id: l.id, label: <><span className="mr-1.5 text-xs text-faint">{String(l.number).padStart(2, "0")}</span>{l.name}</> }))]} />
  );
}

// ------------------------------------------------------------------ records: table, add, edit, delete, created by
function CreatedBy({ p }: { p?: any }) {
  if (p?.kind === "human") return (
    <div><Badge tone="info"><User className="size-3" />Human</Badge><div className="mt-0.5 text-xs text-muted">{p.by}, {p.change} {fmtDate(p.at)}</div></div>
  );
  return <div><Badge><Bot className="size-3" />System</Badge><div className="mt-0.5 text-xs text-muted">Generated by Aria XAI</div></div>;
}

function RecordTable({ section, b, editable, onSaved }: { section: string; b: BP; editable: boolean; onSaved: (r: BP) => void }) {
  const toast = useToast();
  const S = SECTIONS[section];
  const items: any[] = b.content?.[section] || [];
  const [edit, setEdit] = useState<{ key: string | null; record: any } | null>(null);
  const [busy, setBusy] = useState("");
  const keyOf = (r: any) => (S.key ? r[S.key] : r);
  const send = async (op: "add" | "edit" | "delete", key: string | null, record?: any) => {
    setBusy(key || "new");
    try {
      const r = await api<BP>("/api/studio/records", { body: { blueprint_id: b.id, section, op, key, record } });
      toast(`${S.one[0].toUpperCase() + S.one.slice(1)} ${op === "add" ? "added" : op === "edit" ? "saved" : "deleted"}${r.id !== b.id ? `, in new draft version ${r.version}` : ""}`);
      setEdit(null); onSaved(r);
    } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };
  const del = (k: string) => { if (confirm(`Delete this ${S.one}? It is recorded in the audit log, and earlier versions keep it.`)) send("delete", k); };
  return (
    <Card>
      <CardHead title={<>{S.title} <span className="text-[13px] font-normal text-muted">({items.length})</span></>} sub={S.help}
        right={editable && <Button size="sm" icon={<Plus className="size-4" />} onClick={() => setEdit({ key: null, record: structuredClone(S.blank) })}>Add {S.one}</Button>} />
      {items.length === 0 ? <p className="px-5 py-4 text-sm text-muted">None yet.{editable && ` Use Add ${S.one} to create one.`}</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-5 py-2 font-medium">{S.one[0].toUpperCase() + S.one.slice(1)}</th>
              {section !== "starter_questions" && <th className="py-2 pr-4 font-medium">Details</th>}<th className="py-2 pr-4 font-medium">Created by</th>{editable && <th className="w-24 pr-5" />}</tr></thead>
            <tbody>{items.map((r, i) => {
              const k = keyOf(r);
              const sm = summary(section, r);
              return (
                <tr key={`${k}-${i}`} className="border-b border-line align-top last:border-0">
                  <td className="max-w-[260px] px-5 py-2.5 font-medium">{sm.title}</td>
                  {section !== "starter_questions" && <td className="min-w-[220px] py-2.5 pr-4 text-fg/90">{sm.detail}</td>}
                  <td className="w-44 min-w-[150px] py-2.5 pr-4"><CreatedBy p={b.provenance?.[section]?.[k]} /></td>
                  {editable && <td className="whitespace-nowrap py-2 pr-5 text-right">
                    <button className="rounded-md p-1.5 text-muted hover:bg-panel2 hover:text-fg" title="Edit" aria-label={`Edit ${k}`} onClick={() => setEdit({ key: k, record: structuredClone(r) })}><Pencil className="size-4" /></button>
                    <button className="rounded-md p-1.5 text-muted hover:bg-badsoft hover:text-bad" title="Delete" aria-label={`Delete ${k}`} disabled={busy === k} onClick={() => del(k)}><Trash2 className="size-4" /></button>
                  </td>}
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}
      {edit && <RecordModal section={section} initial={edit.record} isNew={edit.key === null} saving={!!busy}
        onClose={() => setEdit(null)} onSave={(rec) => send(edit.key === null ? "add" : "edit", edit.key, rec)} />}
    </Card>
  );
}

function RecordModal({ section, initial, isNew, saving, onClose, onSave }: { section: string; initial: any; isNew: boolean; saving: boolean; onClose: () => void; onSave: (r: any) => void }) {
  const S = SECTIONS[section];
  const [rec, setRec] = useState<any>(initial);
  const [text, setText] = useState<Record<string, string>>(() => Object.fromEntries(S.fields.filter((f) => f.kind === "json" || f.kind === "list")
    .map((f) => [f.k, f.kind === "list" ? (initial?.[f.k] || []).join(", ") : initial?.[f.k] == null ? "" : JSON.stringify(initial[f.k], null, 2)])));
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [roles, setRoles] = useState<string[]>([]);
  const [conns, setConns] = useState<any[]>([]);
  useEffect(() => {
    if (S.fields.some((f) => f.kind === "role")) api<any[]>("/api/roles").then((r) => setRoles(r.map((x) => x.name))).catch(() => {});
    if (section === "actions") api<any[]>("/api/data/connections").then(setConns).catch(() => {});
  }, [section]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k: string, v: any) => setRec({ ...rec, [k]: v });
  const save = () => {
    if (section === "starter_questions") return onSave(String(rec || "").trim());
    const out = { ...rec }, e: Record<string, string> = {};
    for (const f of S.fields) {
      if (f.kind === "list") out[f.k] = text[f.k].split(",").map((x) => x.trim()).filter(Boolean);
      if (f.kind === "json") {
        if (!text[f.k].trim()) out[f.k] = null;
        else try { out[f.k] = JSON.parse(text[f.k]); } catch (x: any) { e[f.k] = "This is not valid JSON: " + x.message; }
      }
    }
    if (!String(out[S.key] || "").trim()) e[S.key] = "Required";
    setErrs(e);
    if (!Object.keys(e).length) onSave(out);
  };
  return (
    <Modal open onClose={onClose} wide title={isNew ? `Add ${S.one}` : `Edit ${S.one}`}>
      <div className="space-y-4">
        {section === "starter_questions" ? <Field label="Question"><Input autoFocus value={rec || ""} onChange={(e) => setRec(e.target.value)} /></Field> : (
          <div className="grid gap-4 md:grid-cols-2">
            <datalist id="studio-roles">{roles.map((r) => <option key={r} value={r} />)}</datalist>
            {S.fields.map((f) => {
              const wide = ["long", "json", "executor", "tools"].includes(f.kind);
              const v = rec?.[f.k];
              const inputs: Record<F["kind"], () => ReactNode> = {
                text: () => <Input value={v ?? ""} onChange={(e) => set(f.k, e.target.value)} />,
                role: () => <Input list="studio-roles" value={v ?? ""} onChange={(e) => set(f.k, e.target.value)} />,
                long: () => <Textarea rows={3} value={v ?? ""} onChange={(e) => set(f.k, e.target.value)} />,
                number: () => <Input type="number" step="any" value={v ?? ""} onChange={(e) => set(f.k, e.target.value === "" ? null : Number(e.target.value))} />,
                bool: () => <div className="pt-1"><Toggle checked={!!v} onChange={(x) => set(f.k, x)} label={v ? "Yes" : "No"} /></div>,
                enum: () => <Select value={v ?? ""} onChange={(e) => set(f.k, e.target.value)}>{f.options!.map((o) => <option key={o} value={o}>{o === "weighted_sum" ? "weighted sum" : o === "noisy_or" ? "noisy-OR" : o}</option>)}</Select>,
                list: () => <Input value={text[f.k]} onChange={(e) => setText({ ...text, [f.k]: e.target.value })} />,
                json: () => <Textarea rows={4} className="font-mono text-xs" spellCheck={false} value={text[f.k]} onChange={(e) => setText({ ...text, [f.k]: e.target.value })} />,
                tools: () => <div className="flex flex-wrap gap-1.5">{f.options!.map((t) => { const on = (v || []).includes(t); return (
                  <button key={t} type="button" onClick={() => set(f.k, on ? v.filter((x: string) => x !== t) : [...(v || []), t])}
                    className={cx("rounded-full border px-2.5 py-0.5 text-xs", on ? "border-accent bg-accentsoft text-accent" : "border-line text-muted")}>{t}</button>); })}</div>,
                executor: () => <ExecutorField ex={v || { type: "webhook", url: "" }} conns={conns} onChange={(x) => set(f.k, x)} />,
              };
              const input = inputs[f.kind]();
              return <div key={f.k} className={wide ? "md:col-span-2" : ""}><Field label={f.label} hint={f.hint} error={errs[f.k]}>{input}</Field></div>;
            })}
          </div>
        )}
        <p className="text-xs text-muted">Saving runs the symbolic check again and is recorded in the audit log. Changing a live version creates a new draft; nothing changes for the agent team until it is published.</p>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={saving} onClick={save}>{isNew ? `Add ${S.one}` : "Save"}</Button></div>
      </div>
    </Modal>
  );
}

function ExecutorField({ ex, conns, onChange }: { ex: any; conns: any[]; onChange: (ex: any) => void }) {
  const conn = conns.find((x) => x.id === ex.connection_id);
  const cols: string[] = conn?.tables.find((t: any) => t.name === ex.table)?.columns.map((c: any) => c.name) || [];
  const set = (p: any) => onChange({ ...ex, ...p });
  return (
    <div className="space-y-3 rounded-lg bg-panel2/60 p-3">
      <Select className="w-auto" value={ex.type || "webhook"} onChange={(e) => onChange(e.target.value === "database"
        ? { type: "database", connection_id: conns.find((x) => x.kind !== "rest")?.id, table: "", operation: "update", key_column: "", columns: [] } : { type: "webhook", url: "" })}>
        <option value="webhook">calling your webhook</option><option value="database">writing one row to a connected database</option></Select>
      {(ex.type || "webhook") === "webhook" ? (
        <Field label="Webhook URL" hint="A signed POST with the decision id and the accountable person"><Input value={ex.url || ""} onChange={(e) => set({ url: e.target.value })} /></Field>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Connection"><Select value={ex.connection_id || ""} onChange={(e) => set({ connection_id: e.target.value, table: "", columns: [] })}>
              {conns.filter((x) => x.kind !== "rest").map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select></Field>
            <Field label="Table"><Select value={ex.table || ""} onChange={(e) => set({ table: e.target.value, columns: [], key_column: "" })}>
              <option value="">Choose…</option>{(conn?.tables || []).map((t: any) => <option key={t.name}>{t.name}</option>)}</Select></Field>
            <Field label="Operation"><Select value={ex.operation} onChange={(e) => set({ operation: e.target.value })}><option value="update">update one row</option><option value="insert">insert a row</option></Select></Field>
            {ex.operation === "update" && <Field label="Key column"><Select value={ex.key_column || ""} onChange={(e) => set({ key_column: e.target.value })}>
              <option value="">Choose…</option>{cols.map((c) => <option key={c}>{c}</option>)}</Select></Field>}
          </div>
          <div><div className="mb-1 text-[13px] font-medium">Columns it may write</div>
            <div className="flex flex-wrap gap-1.5">{cols.filter((c) => c !== ex.key_column).map((c) => {
              const on = (ex.columns || []).includes(c);
              return <button key={c} type="button" onClick={() => set({ columns: on ? ex.columns.filter((x: string) => x !== c) : [...(ex.columns || []), c] })}
                className={cx("rounded-full border px-2.5 py-0.5 text-xs", on ? "border-accent bg-accentsoft text-accent" : "border-line text-muted")}>{c}</button>;
            })}{!cols.length && <span className="text-xs text-muted">Choose a table</span>}</div></div>
          {conn && !conn.allow_writes && <Alert tone="warn">Writes are disabled on {conn.name}. An admin can enable them in Understand my product, Connect data.</Alert>}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ layer settings
function SettingsCard({ layer, onSaved, title = "Settings" }: { layer: Layer; onSaved: () => void; title?: string }) {
  const toast = useToast();
  const [v, setV] = useState(layer.settings);
  const [busy, setBusy] = useState(false);
  useEffect(() => setV(layer.settings), [layer]);
  const dirty = JSON.stringify(v) !== JSON.stringify(layer.settings);
  const ed = layer.can_edit_settings;
  const save = async () => {
    setBusy(true);
    try { await api(`/api/studio/${layer.id}/settings`, { method: "PUT", body: { settings: v } }); toast("Settings saved"); onSaved(); }
    catch (e: any) { toast(e.details ? e.details.join("; ") : e.message, "bad"); } finally { setBusy(false); }
  };
  return (
    <Card>
      <CardHead title={title} sub={ed ? "Applies to every conversation, API call and widget session from the next request." : "Only an Owner or Org admin can change these."}
        right={!ed && <Lock className="size-4 text-faint" />} />
      <div className="grid gap-4 p-5 sm:grid-cols-2">
        {Object.entries(layer.settings_spec).map(([k, s]) => (
          <div key={k}>
            {s.type === "bool" ? <Toggle checked={!!v[k]} onChange={(x) => ed && setV({ ...v, [k]: x })} label={s.label} /> : s.type === "text" ? (
              <Field label={s.label} hint={s.hint}><Input disabled={!ed} maxLength={s.max} value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></Field>
            ) : (
              <Field label={s.label} hint={`Default ${s.type === "choice" ? CHOICE[s.default] || s.default : s.default}${s.type === "int" ? `, from ${s.min} to ${s.max}` : ""}`}>
                {s.type === "int"
                  ? <Input type="number" min={s.min} max={s.max} disabled={!ed} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value === "" ? "" : Number(e.target.value) })} />
                  : <Select disabled={!ed} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })}>{s.choices!.map((o) => <option key={o} value={o}>{CHOICE[o] || o}</option>)}</Select>}
              </Field>
            )}
          </div>
        ))}
      </div>
      {ed && dirty && <div className="flex justify-end gap-2 border-t border-line px-5 py-3"><Button variant="ghost" onClick={() => setV(layer.settings)}>Discard</Button><Button variant="primary" loading={busy} onClick={save}>Save settings</Button></div>}
    </Card>
  );
}

// ------------------------------------------------------------------ the neuro-symbolic engine, and a way to try it
function Engine({ c, b }: { c: any; b: BP }) {
  const stages: [string, "Neural" | "Symbolic" | "Person", string][] = [
    ["Understand", "Neural", "The model reads the request, your documents and data, and states the facts with their source and confidence."],
    ["Soft signals", "Symbolic", `${(c.signals || []).length} signal(s) weigh the evidence into a score from 0 to 1.`],
    ["Gate", "Symbolic", "Thresholds turn each score into true, false or not enough evidence. Rules never see raw scores."],
    ["Hard rules", "Symbolic", `${(c.rules || []).length} rule(s) decide: valid, invalid or not enough evidence.`],
    ["Sentinel policy", "Symbolic", "Checks the step against the accountable person's authority: allow, review or block."],
    ["Approve and act", "Person", "A person approves and is accountable. Only then Aria Executor carries it out. Everything is audited."],
  ];
  const tone = { Neural: "accent", Symbolic: "ok", Person: "info" } as const;
  return (
    <Card>
      <CardHead title="Neuro-symbolic engine" sub="The model proposes, the rules decide. Every verdict can be explained part by part." />
      <ol className="grid gap-2 p-5 sm:grid-cols-2 xl:grid-cols-3">
        {stages.map(([n, k, d], i) => (
          <li key={n} className="relative rounded-lg border border-line p-3">
            <div className="flex items-center gap-2"><span className="font-mono text-xs text-faint">{i + 1}</span><b className="text-sm">{n}</b><Badge tone={tone[k]} className="ml-auto">{k}</Badge></div>
            <p className="mt-1 text-[13px] text-muted">{d}</p>
          </li>
        ))}
      </ol>
      {(c.actions || []).length > 0 && <TryEngine c={c} b={b} />}
    </Card>
  );
}

function TryEngine({ c, b }: { c: any; b: BP }) {
  const toast = useToast();
  const [action, setAction] = useState(c.actions[0].name);
  const act = c.actions.find((x: any) => x.name === action) || c.actions[0];
  const names: string[] = useMemo(() => Array.from(new Set([...(act.required_facts || []), ...(act.amount_fact ? [act.amount_fact] : []),
    ...(c.signals || []).flatMap((s: any) => (s.inputs || []).map((i: any) => i.fact))])), [act, c.signals]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const typeOf = (n: string) => (c.facts || []).find((f: any) => f.name === n)?.type || "string";
  const run = async () => {
    const facts: Record<string, any> = {};
    for (const n of names) {
      const v = (vals[n] ?? "").trim();
      if (v === "") continue;
      facts[n] = typeOf(n) === "number" ? Number(v) : typeOf(n) === "boolean" ? v === "true" : v;
    }
    setBusy(true);
    try { setRes(await api("/api/studio/engine/try", { body: { blueprint_id: b.id, action, facts } })); } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); }
  };
  const vt = (v: string) => (v === "VALID" ? "ok" : v === "INVALID" ? "bad" : "warn") as "ok" | "bad" | "warn";
  return (
    <div className="border-t border-line p-5">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><FlaskConical className="size-4 text-accent" />Try the rules</div>
      <p className="mb-3 text-[13px] text-muted">Enter facts as the model would establish them and see the verdict. Nothing is proposed, approved or sent. Leave a fact empty to see what happens when it is unknown.</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Action"><Select value={action} onChange={(e) => { setAction(e.target.value); setRes(null); }}>{c.actions.map((x: any) => <option key={x.name}>{x.name}</option>)}</Select></Field>
        {names.map((n) => (
          <Field key={n} label={<span className="font-mono text-xs">{n}</span>}>
            {typeOf(n) === "boolean"
              ? <Select value={vals[n] ?? ""} onChange={(e) => setVals({ ...vals, [n]: e.target.value })}><option value="">unknown</option><option value="true">true</option><option value="false">false</option></Select>
              : <Input type={typeOf(n) === "number" ? "number" : "text"} value={vals[n] ?? ""} onChange={(e) => setVals({ ...vals, [n]: e.target.value })} />}
          </Field>
        ))}
      </div>
      <div className="mt-3"><Button loading={busy} icon={<ArrowRight className="size-4" />} onClick={run}>Check</Button></div>
      {res && (
        <div className="mt-4 space-y-3 rounded-lg bg-panel2/60 p-4 text-[13px]">
          <div className="flex flex-wrap items-center gap-2"><span>Rules verdict</span><Badge tone={vt(res.verdict)}>{res.verdict}</Badge>
            <span className="ml-2">{res.risk} risk</span>
            <Badge tone={res.authority.within ? "ok" : "warn"}>{res.authority.within ? "Within your approval authority" : `Beyond your authority, it would go to ${res.owner_role}`}</Badge></div>
          {res.gate.length > 0 && <div><div className="mb-1 font-medium">Gate</div><ul className="space-y-0.5">{res.gate.map((g: any) => <li key={g.signal}><span className="font-mono text-xs">{g.signal}</span>: score {g.score == null ? "none" : Number(g.score).toFixed(2)}, {String(g.outcome)}</li>)}</ul></div>}
          {res.hard.length > 0 && <div><div className="mb-1 font-medium">Hard rules</div><ul className="space-y-0.5">{res.hard.map((h: any) => <li key={h.id}><span className="font-mono text-xs">{h.id}</span>: {h.status}{h.message && `, ${h.message}`}</li>)}</ul></div>}
          {!res.authority.within && res.authority.reasons?.length > 0 && <div className="text-muted">{res.authority.reasons.join(". ")}</div>}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ fixed parts of a layer (shown, not duplicated)
function Guardrails() {
  const { me, can, refresh } = useAuth();
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const ks = me?.org.kill_switch;
  const set = async (active: boolean) => {
    if (active && !confirm("Turn on the kill switch? Every medium and high risk action stops immediately, including approved ones that have not run yet.")) return;
    setBusy(true);
    try { await api("/api/org/kill-switch", { body: { active, reason } }); await refresh(); setReason(""); toast(active ? "Kill switch is on" : "Kill switch released"); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card>
        <CardHead title="Always on" sub="Built into the framework. They cannot be switched off." />
        <ul className="space-y-2 p-5 text-[13px]">
          {["Government IDs, card numbers and IBANs are removed before any data reaches an AI model.", "Every message and document is scanned for instructions hidden in the text; they are treated as data.",
            "Agents can only read data: every query passes the SQL guard (read only, allowed tables, row limit).", "Every decision, approval and change is written to the hash-chained audit ledger."].map((t) => (
            <li key={t} className="flex gap-2"><Lock className="mt-0.5 size-3.5 shrink-0 text-ok" />{t}</li>))}
          {can("audit:view") && <li><Link to="/audit" className="font-medium text-accent">Open the audit log</Link></li>}
        </ul>
      </Card>
      <Card className={ks ? "border-bad" : ""}>
        <CardHead title="Kill switch" sub="Stops every medium and high risk action at once, for example during a suspected incident. Low risk actions and questions keep working." />
        <div className="space-y-3 p-5">
          {ks ? (<>
            <Alert tone="bad" title="On">Turned on by {ks.by} at {fmtDate(ks.at)}{ks.reason && `. Reason: ${ks.reason}`}</Alert>
            {can("org:edit") && <Button variant="ok" loading={busy} onClick={() => set(false)}>Release the kill switch</Button>}
          </>) : can("org:edit") ? (<>
            <Field label="Reason (recorded in the audit log)"><Input value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <Button variant="danger" loading={busy} onClick={() => set(true)}>Turn on the kill switch</Button>
          </>) : <p className="text-[13px] text-muted">Off. Only an Owner or Org admin can turn it on.</p>}
        </div>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ reset a layer to the original
function ResetLayer({ layer, bp, onClose, onDone }: { layer: Layer; bp: BP; onClose: () => void; onDone: (r: BP | null) => void }) {
  const toast = useToast();
  const [pv, setPv] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api(`/api/studio/${layer.id}/reset`, { body: { blueprint_id: bp.id } }).then(setPv).catch((e) => setPv({ error: e.message })); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const go = async () => {
    setBusy(true);
    try { const r = await api<any>(`/api/studio/${layer.id}/reset`, { body: { blueprint_id: bp.id, confirm: true } });
      toast(`${layer.name} is back to the original${r.blueprint ? `, in draft version ${r.blueprint.version}` : ""}`); onDone(r.blueprint); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} wide title={`Reset ${layer.name} to the original`}>
      {!pv ? <Loading /> : pv.error ? <Alert tone="bad">{pv.error}</Alert> : (
        <div className="space-y-4">
          <p className="text-[13px] text-muted">Records go back to what Aria XAI generated from your product{pv.original ? ` in version ${pv.original.version}` : ""}. Settings go back to the framework defaults.
            Records are saved as a new draft, so nothing changes for the agent team until it is published, and every earlier version stays available.</p>
          {pv.changes.length === 0 ? <Alert tone="ok">This layer already matches the original. There is nothing to reset.</Alert> : (
            <><div className="text-sm font-semibold">These are the changes:</div><ChangeList changes={pv.changes} />
              <div className="flex justify-end gap-2 border-t border-line pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button>
                <Button variant="primary" loading={busy} icon={<RotateCcw className="size-4" />} onClick={go}>Yes, reset to original</Button></div></>
          )}
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ business rules via YAML, versions
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
        {res?.ok && (res.changes.length === 0 ? <Alert tone="info">This file is identical to version {res.base.version}. There is nothing to change.</Alert> : (
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
        ))}
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
              <Button size="sm" onClick={() => { nav(`/studio/${v.id}`); onClose(); }}>View</Button>
              {live && v.id !== live.id && v.status !== "generating" && v.status !== "failed" && <Button size="sm" onClick={() => compare(v)}>Compare with live</Button>}
              {canSwitch && (v.status === "draft" || v.status === "archived") &&
                <Button size="sm" variant="primary" loading={busy === v.id} onClick={() => switchTo(v)}>Switch to this version</Button>}
            </li>))}
        </ul>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ what each layer shows (live, from the organisation's own data)
const VT = (v: string) => (v === "VALID" ? "ok" : v === "INVALID" ? "bad" : "warn") as "ok" | "bad" | "warn";
const ST: Record<string, "ok" | "bad" | "warn" | "info" | "neutral" | "accent"> = {
  EXECUTED: "ok", executed: "ok", approved: "ok", suggested: "accent", PENDING_REVIEW: "warn", pending: "warn", awaiting_approval: "warn", escalated: "warn",
  investigating: "info", received: "info", REJECTED: "bad", rejected: "bad", BLOCKED: "bad", FAILED: "bad", failed: "bad", ignored: "neutral", no_action: "neutral" };
const human = (s: string) => s.replace(/_/g, " ").toLowerCase();

function Stat({ n, label, tone }: { n: ReactNode; label: string; tone?: string }) {
  return <div className="min-w-[110px] flex-1 rounded-lg border border-line px-4 py-3"><div className={cx("text-[22px] font-semibold leading-none", tone)}>{n}</div><div className="mt-1 text-xs text-muted">{label}</div></div>;
}

function LayerBody({ layer, b, onSaved, onSettings }: { layer: Layer; b: BP; onSaved: (r: BP) => void; onSettings: () => void }) {
  const live = useAsync<any>(() => api(`/api/studio/${layer.id}/live`), [layer.id]);
  const c = b.content || {};
  const rec = (s: string, editable = layer.can_edit_records) => <RecordTable key={s} section={s} b={b} editable={editable} onSaved={onSaved} />;
  const settings = (title?: string) => Object.keys(layer.settings_spec).length > 0 && !layer.readonly
    ? <SettingsCard layer={layer} title={title} onSaved={() => { onSettings(); live.reload(); }} /> : null;
  if (live.loading && !live.data) return <Loading />;
  if (live.error) return <ErrorBox error={live.error} />;
  const L = live.data;
  switch (layer.id) {
    case "cognitive": return <><Engine c={c} b={b} /><RecentVerdicts L={L} />{rec("rules")}{rec("signals")}{rec("facts")}</>;
    case "motivation": return <Motivation L={L} reload={live.reload} settings={settings("How Aria Watch observes")} records={<>{rec("watch_rules")}{rec("kpis")}</>} />;
    case "knowledge": return <Memory L={L} c={c} b={b} entities={rec("ontology", false)} />;
    case "swarm": return <Swarm L={L} settings={settings("Limits")} records={rec("agents")} />;
    case "interface": return <Persona L={L} settings={settings("Persona")} records={rec("starter_questions")} />;
    case "governance": return <Sentinel L={L} c={c} settings={settings("Guardrail settings")} records={rec("actions")} />;
    default: return null;
  }
}

// ---- Cognitive Core
function RecentVerdicts({ L }: { L: any }) {
  return (
    <Card>
      <CardHead title="What the rule engine decided recently" sub={`${L.total} decision(s) so far. Each verdict lists the rules behind it.`} />
      <div className="flex flex-wrap gap-2 px-5 pt-4">
        <Stat n={L.verdicts.VALID || 0} label="valid" tone="text-ok" /><Stat n={L.verdicts.INVALID || 0} label="invalid, blocked" tone="text-bad" />
        <Stat n={L.verdicts.INSUFFICIENT_EVIDENCE || 0} label="not enough evidence" tone="text-warn" />
      </div>
      {L.recent.length === 0 ? <p className="px-5 py-4 text-sm text-muted">No decisions yet. They appear here as soon as the agent team checks its first action.</p> : (
        <ul className="mt-3 divide-y divide-line border-t border-line">{L.recent.map((d: any) => (
          <li key={d.id} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-5 py-2.5 text-[13px]">
            <Badge tone={VT(d.verdict)}>{human(d.verdict)}</Badge><span className="font-mono text-xs">{d.action}</span>
            <span className="min-w-0 flex-1">{d.summary}{d.reasons?.[0] && <span className="block text-xs text-muted">{d.reasons[0]}</span>}</span>
            <Link to={`/approvals/${d.id}`} className="text-xs text-accent">{fmtDate(d.at)}</Link>
          </li>))}</ul>)}
    </Card>
  );
}

// ---- Motivation Engine: observe, learn from feedback, suggest, a person approves
function Motivation({ L, reload, settings, records }: { L: any; reload: () => void; settings: ReactNode; records: ReactNode }) {
  const toast = useToast();
  const [note, setNote] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  if (!L.allowed) return <><Alert tone="info">Your role does not include Aria Watch, so its observations and suggestions are hidden. Ask an Owner or Org admin.</Alert>{records}</>;
  const pending = L.suggestions.filter((s: any) => s.status === "pending");
  const decided = L.suggestions.filter((s: any) => s.status !== "pending");
  const lessons = L.learned.reduce((t: number, r: any) => t + r.lessons.length, 0);
  const decide = async (s: any, approve: boolean) => {
    setBusy(s.id);
    try { await api(`/api/suggestions/${s.id}/decide`, { body: { approve, note: note[s.id] || "" } }); toast(approve ? "Approved. Aria Executor carries it out and you are recorded as accountable." : "Rejected. Aria Watch learns from your note."); reload(); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };
  const loop: [string, ReactNode, string][] = [
    ["Observe", L.events_total, "product events seen"], ["Learn", lessons + L.feedback.length, "owner decisions it learns from"],
    ["Suggest", L.suggestions.length, "improvements proposed"], ["Person approves", pending.length, "waiting for a person"],
    ["Applied", L.suggestions.filter((s: any) => s.status === "executed").length, "carried out after approval"]];
  return (
    <>
      <Card>
        <CardHead title="The feedback loop" sub="Aria Watch observes, learns from how your people decided before, and suggests. Nothing it learns changes your product until a person approves it." />
        <ol className="grid gap-2 p-5 sm:grid-cols-5">{loop.map(([t, n, d], i) => (
          <li key={t} className={cx("rounded-lg border p-3", t === "Person approves" ? "border-warn/50 bg-warnsoft/40" : "border-line")}>
            <div className="text-xs text-faint">{i + 1}. {t}</div><div className="mt-1 text-[22px] font-semibold leading-none">{n}</div><div className="mt-1 text-xs text-muted">{d}</div>
          </li>))}</ol>
      </Card>

      <Card>
        <CardHead title={<>Waiting for your approval <span className="text-[13px] font-normal text-muted">({pending.length})</span></>} sub="Approve to hand it to Aria Executor with you as the accountable person, or reject with a note so Aria Watch learns." />
        {pending.length === 0 ? <p className="px-5 py-4 text-sm text-muted">Nothing is waiting. New suggestions appear here.</p> : (
          <ul className="divide-y divide-line">{pending.map((s: any) => (
            <li key={s.id} className="space-y-2 px-5 py-4">
              <div className="flex flex-wrap items-center gap-2"><b className="text-sm">{s.title}</b><Badge>owner: {s.owner_role}</Badge><span className="text-xs text-muted">{fmtDate(s.created_at)}</span></div>
              {s.rationale && <p className="text-[13px] text-fg/90">{s.rationale}</p>}
              {s.benefit && <p className="text-[13px] text-muted">Benefit: {s.benefit}</p>}
              {s.can_decide ? (
                <div className="flex flex-wrap items-end gap-2 pt-1">
                  <div className="min-w-[220px] flex-1"><Field label="Note for Aria Watch (optional)"><Input value={note[s.id] || ""} onChange={(e) => setNote({ ...note, [s.id]: e.target.value })} /></Field></div>
                  <Button variant="ok" loading={busy === s.id} onClick={() => decide(s, true)}>Approve</Button>
                  <Button variant="danger" disabled={busy === s.id} onClick={() => decide(s, false)}>Reject</Button>
                </div>) : <p className="text-xs text-muted">Only the {s.owner_role} role can decide this.</p>}
            </li>))}</ul>)}
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHead title="What it observed" sub="The latest events your product reported. Events no watch rule cares about are recorded and ignored without calling the model." />
          {L.recent_events.length === 0 ? <p className="px-5 py-4 text-sm text-muted">No events yet.</p> : (
            <ul className="divide-y divide-line">{L.recent_events.map((e: any) => (
              <li key={e.id} className="px-5 py-2.5 text-[13px]">
                <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs">{e.type}</span>{e.entity_id && <span className="text-xs text-muted">{e.entity_id}</span>}
                  <Badge tone={ST[e.status] || "neutral"}>{human(e.status)}</Badge><span className="ml-auto text-xs text-faint">{fmtDate(e.at)}</span></div>
                {e.note && <div className="mt-0.5 text-xs text-muted">{e.note}</div>}
              </li>))}</ul>)}
        </Card>
        <Card>
          <CardHead title="What it learned from your people" sub="How owners decided earlier suggestions, and the notes they left. Aria Watch reads these before it suggests anything new." />
          {decided.length === 0 && L.feedback.length === 0 ? <p className="px-5 py-4 text-sm text-muted">No feedback yet. Every approval or rejection teaches it.</p> : (
            <ul className="divide-y divide-line">
              {decided.slice(0, 6).map((s: any) => (
                <li key={s.id} className="px-5 py-2.5 text-[13px]">
                  <div className="flex flex-wrap items-center gap-2"><Badge tone={ST[s.status] || "neutral"}>{human(s.status)}</Badge><span className="font-medium">{s.title}</span></div>
                  <div className="mt-0.5 text-xs text-muted">{s.decided_by || "An owner"}{s.note ? `: "${s.note}"` : ", no note"}</div>
                </li>))}
              {L.feedback.slice(0, 4).map((d: any) => (
                <li key={d.id} className="px-5 py-2.5 text-[13px]">
                  <div className="flex flex-wrap items-center gap-2"><Badge tone={ST[d.status] || "neutral"}>{human(d.status)}</Badge><span className="font-mono text-xs">{d.action}</span><span className="text-xs text-muted">reviewed by {d.reviewer}</span></div>
                  {d.note && <div className="mt-0.5 text-xs text-muted">"{d.note}"</div>}
                </li>))}
            </ul>)}
        </Card>
      </div>
      {settings}
      {records}
    </>
  );
}

// ---- Knowledge Fabric: the memory, how it is stored, what changed
function Memory({ L, c, b, entities }: { L: any; c: any; b: BP; entities: ReactNode }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const search = async () => { setBusy(true); try { setHits(await api(`/api/knowledge/search?q=${encodeURIComponent(q)}`)); } catch { setHits([]); } finally { setBusy(false); } };
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {L.stores.map((s: any) => (
          <Card key={s.id} className="p-4">
            <div className="flex items-baseline justify-between gap-2"><b className="text-sm">{s.name}</b><span className="text-xs text-faint">{s.kind}</span></div>
            <div className="mt-2 flex items-baseline gap-2"><span className="text-[26px] font-semibold leading-none">{s.count}</span><span className="text-xs text-muted">{s.detail}</span></div>
            <p className="mt-2 text-xs leading-relaxed text-muted">{s.how}</p>
          </Card>))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardHead title="Recent memory updates" sub="What was added or changed, newest first." />
          {L.timeline.length === 0 ? <p className="px-5 py-4 text-sm text-muted">Nothing stored yet.</p> : (
            <ol className="relative space-y-3 px-5 py-4">{L.timeline.map((t: any, i: number) => (
              <li key={i} className="grid grid-cols-[10px_1fr] gap-3 text-[13px]">
                <span className="mt-1.5 size-2.5 rounded-full bg-accent/60" />
                <div><div>{t.text}</div><div className="text-xs text-muted">{t.store}{t.by && `, by ${t.by}`}, {fmtDate(t.at)}</div></div>
              </li>))}</ol>)}
        </Card>
        <Card>
          <CardHead title="Ask the memory" sub="Search the documents the team has learned, the same way the agents do." />
          {L.can_search ? (
            <div className="space-y-3 p-5">
              <div className="flex gap-2"><Input aria-label="Search the memory" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && q.trim() && search()} />
                <Button loading={busy} disabled={!q.trim()} onClick={search}>Search</Button></div>
              {hits && (hits.length === 0 ? <p className="text-sm text-muted">No passage matches.</p> : (
                <ul className="space-y-2">{hits.slice(0, 5).map((h, i) => (
                  <li key={i} className="rounded-lg bg-panel2/70 p-3 text-[13px]"><div className="mb-1 text-xs text-muted">{h.document}, page {h.page}</div>{h.text.slice(0, 280)}{h.text.length > 280 && "…"}</li>))}</ul>))}
            </div>) : <p className="px-5 py-4 text-sm text-muted">Your role cannot read the documents.</p>}
        </Card>
      </div>

      <Card className="p-5">
        <div className="text-sm font-semibold">What Aria XAI understood about your product</div>
        <p className="mt-1 text-[14px] leading-relaxed">{c.summary || "Not understood yet."}</p>
        <p className="mt-2 text-xs text-muted">From {b.sources?.described ? "your description, " : ""}{b.sources?.documents?.length || 0} document(s) and {b.sources?.connections?.length || 0} data connection(s). Version {b.version}.
          {" "}<Link to="/understand" className="font-medium text-accent">Add documents or data</Link></p>
      </Card>
      {entities}
      {L.connections.length > 0 && (
        <Card><CardHead title="Mapped business data" sub="Schemas the team knows. Rows are read live, never copied." />
          <ul className="divide-y divide-line">{L.connections.map((cn: any) => (
            <li key={cn.id} className="px-5 py-3 text-[13px]"><b>{cn.name}</b> <span className="text-xs text-muted">({cn.kind}{cn.at && `, read ${fmtDate(cn.at)}`})</span>
              <div className="mt-1 flex flex-wrap gap-1">{cn.tables.map((t: string) => <Badge key={t}>{t}</Badge>)}</div></li>))}</ul>
        </Card>)}
    </>
  );
}

// ---- Swarm Orchestrator: where requests go, the plans, what the team has been doing
function Swarm({ L, settings, records }: { L: any; settings: ReactNode; records: ReactNode }) {
  const w = (n: string) => L.workload[n] || 0;
  const max = Math.max(1, ...Object.values(L.workload as Record<string, number>));
  const node = (name: string, d: string, tone = "border-line bg-panel") => (
    <div className={cx("rounded-lg border px-3 py-2", tone)}><div className="flex items-center gap-2 text-[13px] font-semibold"><Bot className="size-3.5 text-accent" />{name}
      <span className="ml-auto text-xs font-normal text-muted">{w(name)}</span></div><div className="text-xs text-muted">{d}</div></div>);
  return (
    <>
      <Card>
        <CardHead title="Where a request goes" sub="Numbers show how often each agent was involved in recent work." />
        <div className="space-y-2 p-5">
          <div className="mx-auto max-w-sm rounded-lg border border-line bg-panel2 px-3 py-2 text-center text-[13px]">A person asks, in the app, the API or your product's chat</div>
          <div className="mx-auto h-4 w-px bg-line2" />
          <div className="mx-auto max-w-md">{node("Aria Orchestrator", "Understands the request, plans it, assigns the work and checks the result", "border-accent/40 bg-accentsoft/50")}</div>
          <div className="mx-auto h-4 w-px bg-line2" />
          <div className="grid gap-2 md:grid-cols-3">{L.leads.map((g: any) => <div key={g.id}>{node(g.name, g.purpose)}</div>)}</div>
          {L.specialists.length > 0 && <><div className="mx-auto h-4 w-px bg-line2" />
            <div className="flex flex-wrap justify-center gap-1.5">{L.specialists.map((s: any) => <Badge key={s.id} tone="info">{s.name}{w(s.name) ? ` · ${w(s.name)}` : ""}</Badge>)}</div></>}
          <div className="mx-auto h-4 w-px bg-line2" />
          <div className="mx-auto grid max-w-2xl gap-2 sm:grid-cols-3 text-center text-[12.5px]">
            <div className="rounded-lg border border-line px-2 py-2">Rule engine checks every step</div>
            <div className="rounded-lg border border-warn/50 bg-warnsoft/40 px-2 py-2">A person approves the plan</div>
            <div className="rounded-lg border border-line px-2 py-2">Aria Executor carries it out</div>
          </div>
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHead title="What the team has been doing" sub="The latest requests and the route each one took." />
          {L.runs.length === 0 ? <p className="px-5 py-4 text-sm text-muted">No requests yet.</p> : (
            <ul className="divide-y divide-line">{L.runs.map((r: any) => (
              <li key={r.id} className="px-5 py-3 text-[13px]">
                <div className="flex flex-wrap items-center gap-2">{r.conversation_id ? <Link to={`/chat/${r.conversation_id}`} className="font-medium hover:text-accent">{r.title}</Link> : <span className="font-medium">{r.title}</span>}
                  <Badge>{r.channel === "console" ? "app" : r.channel}</Badge><span className="ml-auto text-xs text-faint">{fmtDate(r.at)}</span></div>
                <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted">{r.route.map((x: string, i: number) => <span key={i} className="inline-flex items-center gap-1">{i > 0 && <ArrowRight className="size-3" />}{x}</span>)}</div>
                {r.steps.length > 0 && <details className="mt-1 text-xs text-muted"><summary className="cursor-pointer select-none">{r.steps.length} step(s)</summary>
                  <ul className="mt-1 space-y-0.5 pl-3">{r.steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></details>}
              </li>))}</ul>)}
        </Card>
        <div className="space-y-5">
          <Card>
            <CardHead title="Plans" sub="Changes are always planned first. Nothing runs until the responsible person approves." />
            {L.plans.length === 0 ? <p className="px-5 py-4 text-sm text-muted">No plans yet.</p> : (
              <ul className="divide-y divide-line">{L.plans.map((p: any) => (
                <li key={p.id} className="px-5 py-2.5 text-[13px]">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{p.title}</span><Badge tone={ST[p.status] || "neutral"}>{human(p.status)}</Badge></div>
                  <div className="mt-0.5 text-xs text-muted">{p.steps} step(s), from {p.source === "watch" ? "Aria Watch" : p.source}{p.accountable ? `, accountable: ${p.accountable}` : p.owner_role ? `, for ${p.owner_role}` : ""}, {fmtDate(p.created_at)}</div>
                </li>))}</ul>)}
          </Card>
          <Card>
            <CardHead title="Workload" />
            <ul className="space-y-2 p-5 text-[13px]">{Object.entries(L.workload as Record<string, number>).map(([n, v]) => (
              <li key={n} className="grid grid-cols-[150px_1fr_32px] items-center gap-3"><span className="truncate">{n}</span>
                <span className="h-2 rounded-full bg-panel2"><span className="block h-2 rounded-full bg-accent" style={{ width: `${(v / max) * 100}%` }} /></span><span className="text-right text-muted">{v}</span></li>))}</ul>
          </Card>
        </div>
      </div>
      {records}
      {settings}
    </>
  );
}

// ---- Anthropomorphic Interface: the persona that speaks for the business
const AVATAR: Record<string, string> = { teal: "bg-[#0b7a83]", indigo: "bg-[#4f46e5]", amber: "bg-[#b45309]", rose: "bg-[#be123c]", slate: "bg-[#334155]" };

export function PersonaAvatar({ p, size = "size-16" }: { p: any; size?: string }) {
  const initials = String(p.name || "A").split(/\s+/).map((x: string) => x[0]).join("").slice(0, 2).toUpperCase();
  return (
    <span className={cx("relative grid shrink-0 place-items-center rounded-full font-semibold text-white", size, AVATAR[p.avatar] || AVATAR.teal)}>
      <span className="absolute inset-0 animate-ping rounded-full bg-inherit opacity-20 motion-reduce:hidden" style={{ animationDuration: "2.4s" }} />
      <span className="relative text-[1.15em]">{initials}</span>
    </span>
  );
}

function Persona({ L, settings, records }: { L: any; settings: ReactNode; records: ReactNode }) {
  const p = L.persona;
  const sample = { plain: "Order 50817 was delivered 12 days ago, so it is still inside the 30 day return window. I can prepare the refund for approval.",
    friendly: "Good news: order 50817 arrived 12 days ago, so it's well within the 30 day return window. Shall I get the refund ready for approval?",
    formal: "Order 50817 was delivered 12 days ago and therefore remains within the 30 day return period. I can prepare the refund for approval." }[p.tone as string];
  return (
    <>
      <div className="grid gap-5 xl:grid-cols-[1fr_1.1fr]">
        <Card className="p-5">
          <div className="flex items-center gap-4"><PersonaAvatar p={p} />
            <div className="min-w-0"><div className="text-lg font-semibold">{p.name}</div><div className="text-[13px] text-muted">{p.role}</div>
              <div className="mt-1.5 flex flex-wrap gap-1">{p.traits.map((t: string) => <Badge key={t} tone="accent">{t}</Badge>)}<Badge>{CHOICE[p.tone] || p.tone} tone</Badge></div></div>
          </div>
          <p className="mt-4 text-[13px] text-muted">This is who people meet in the app, through the API and in the chat widget inside your product. Behind {p.name}, the whole agent team does the work and the rules still decide.</p>
          <Link to="/chat" className="mt-3 inline-block text-[13px] font-medium text-accent">Talk to {p.name}</Link>
        </Card>
        <Card className="p-5">
          <div className="mb-3 text-sm font-semibold">How {p.name} sounds</div>
          <div className="space-y-2.5 text-[13.5px]">
            <div className="flex gap-2"><PersonaAvatar p={p} size="size-7 text-[11px]" /><div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-panel2 px-3 py-2">{p.greeting}</div></div>
            <div className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent px-3 py-2 text-white dark:text-ink">Can I still return my tent?</div></div>
            <div className="flex gap-2"><PersonaAvatar p={p} size="size-7 text-[11px]" /><div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-panel2 px-3 py-2">{sample}</div></div>
          </div>
          <p className="mt-3 text-xs text-muted">An example of the tone. Real answers come from your data, documents and rules.</p>
        </Card>
      </div>
      <div className="flex flex-wrap gap-2">
        <Stat n={L.channels.console || 0} label="conversations in the app" /><Stat n={L.channels.api || 0} label="through the API" /><Stat n={L.channels.widget || 0} label="in your product's chat" />
      </div>
      {settings}
      {records}
    </>
  );
}

// ---- Governance Sentinel: soft and hard rules, policy, guardrails, audit
function Sentinel({ L, c, settings, records }: { L: any; c: any; settings: ReactNode; records: ReactNode }) {
  const { can } = useAuth();
  const list = (section: string, items: any[], empty: string) => items.length === 0 ? <p className="px-5 py-4 text-sm text-muted">{empty}</p> : (
    <ul className="divide-y divide-line">{items.map((r, i) => { const sm = summary(section, r); return (
      <li key={i} className="px-5 py-2.5 text-[13px]"><div className="font-medium">{sm.title}</div><div className="mt-0.5 text-fg/90">{sm.detail}</div></li>); })}</ul>);
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Stat n={L.effects.ALLOW || 0} label="allowed" tone="text-ok" /><Stat n={L.effects.REVIEW || 0} label="sent for review" tone="text-warn" />
        <Stat n={L.effects.BLOCK || 0} label="blocked" tone="text-bad" /><Stat n={L.pending_plans} label="plans waiting for a person" />
        {L.audit && <Stat n={L.audit.verify.ok ? "Intact" : "Broken"} label={`audit chain, ${L.audit.verify.entries} entries`} tone={L.audit.verify.ok ? "text-ok" : "text-bad"} />}
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card><CardHead title={<>Soft rules <span className="text-[13px] font-normal text-muted">({(c.signals || []).length})</span></>} sub="Weigh the evidence. A gate turns each score into true, false or not enough evidence."
          right={<Link to="/studio?layer=cognitive" className="text-xs font-medium text-accent">Change in Cognitive Core</Link>} />
          {list("signals", c.signals || [], "No soft rules.")}</Card>
        <Card><CardHead title={<>Hard rules <span className="text-[13px] font-normal text-muted">({(c.rules || []).length})</span></>} sub="Always applied. A failing hard rule blocks the action or asks for more evidence."
          right={<Link to="/studio?layer=cognitive" className="text-xs font-medium text-accent">Change in Cognitive Core</Link>} />
          {list("rules", c.rules || [], "No hard rules.")}</Card>
      </div>
      {records}
      <Guardrails />
      {settings}
      {L.audit && (
        <Card>
          <CardHead title="Audit trail" sub="Every sign-in, change, approval and action, chained so that any edit to the history is detected."
            right={can("audit:view") && <Link to="/audit" className="text-xs font-medium text-accent">Open the full audit log</Link>} />
          <ul className="divide-y divide-line">{L.audit.recent.map((e: any) => (
            <li key={e.seq} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 px-5 py-2 text-[13px]">
              <span className="w-10 font-mono text-xs text-faint">#{e.seq}</span><span className="font-mono text-xs">{e.kind}</span>
              <span className="min-w-0 flex-1 truncate text-muted">{e.actor}</span><span className="text-xs text-faint">{fmtDate(e.at)}</span></li>))}</ul>
        </Card>)}
    </>
  );
}
