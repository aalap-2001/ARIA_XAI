import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowUp, Bot, BookOpen, CheckCircle2, ClipboardList, Database, Eye, Gavel, Globe, History, Network, Plus, PenLine, ShieldAlert, Trash2, User } from "lucide-react";
import PlanCard from "../components/PlanCard";
import { api, stream } from "../lib/api";
import { useAuth } from "../lib/auth";
import { PersonaAvatar } from "./Studio";
import { Alert, Badge, Button, CountBadge, Empty, cx, useAsync, useToast } from "../components/ui";

type Msg = { id?: string; role: string; content: string; trace?: any[] };
type Ag = { id: string; name: string; purpose: string; tools: string[]; actions: string[] };
type Team = { published: boolean; version: number | null; summary?: string; industry?: string; starter_questions: string[]; leads: Ag[]; agents: Ag[]; watch: { rules: number };
  persona?: { name: string; role: string; greeting: string; traits: string[]; avatar: string; tone: string } };

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
function md(text: string) {
  const lines = esc(text).split("\n");
  let html = "", list: string | null = null, table: string[] = [];
  const inline = (s: string) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/(^|\s)\*(\S[^*]*)\*/g, "$1<em>$2</em>");
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\|\s*:?-+/.test(r)).map((r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
    html += "<table>" + rows.map((r, i) => "<tr>" + r.map((c) => (i === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`)).join("") + "</tr>").join("") + "</table>";
    table = [];
  };
  for (const raw of lines) {
    const l = raw.trimEnd();
    if (l.startsWith("|")) { table.push(l); continue; } else flushTable();
    const ul = l.match(/^\s*[-*•]\s+(.*)/), ol = l.match(/^\s*\d+[.)]\s+(.*)/);
    if (ul || ol) {
      const tag = ul ? "ul" : "ol";
      if (list !== tag) { if (list) html += `</${list}>`; html += `<${tag}>`; list = tag; }
      html += `<li>${inline((ul || ol)![1])}</li>`;
      continue;
    }
    if (list) { html += `</${list}>`; list = null; }
    const h = l.match(/^#{1,4}\s+(.*)/);
    if (h) html += `<p><strong>${inline(h[1])}</strong></p>`;
    else if (l.trim()) html += `<p>${inline(l)}</p>`;
  }
  flushTable();
  if (list) html += `</${list}>`;
  return html;
}

export default function Chat() {
  const { cid } = useParams();
  const nav = useNavigate();
  const { can } = useAuth();
  const toast = useToast();
  const team = useAsync<Team>(() => api("/api/team"));
  const watch = useAsync<number>(() => api<any[]>("/api/suggestions?status=pending").then((s) => s.filter((x) => x.can_decide).length).catch(() => 0));
  const watchCount = watch.data ?? 0;
  const convs = useAsync<{ id: string; title: string }[]>(() => api("/api/conversations"));
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [live, setLive] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [selTrace, setSelTrace] = useState<any[] | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLive([]); setSelTrace(null);
    if (!cid) { setMsgs([]); return; }
    api(`/api/conversations/${cid}`).then((c) => { setMsgs(c.messages); const last = [...c.messages].reverse().find((m: Msg) => m.role === "assistant"); setSelTrace(last?.trace || null); })
      .catch(() => nav("/chat"));
  }, [cid]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, live]);

  const send = async (message: string) => {
    if (!message.trim() || busy) return;
    let id = cid;
    if (!id) { id = (await api<{ id: string }>("/api/conversations", { method: "POST" })).id; }
    setMsgs((m) => [...m, { role: "user", content: message }]);
    setText(""); setBusy(true); setLive([]); setSelTrace(null);
    const trace: any[] = [];
    try {
      await stream(`/api/conversations/${id}/messages`, { message }, (type, data) => {
        if (type === "trace") { trace.push(data); setLive([...trace]); }
        if (type === "final") setMsgs((m) => [...m, { role: "assistant", content: data.text, trace }]);
      });
      setSelTrace(trace);
    } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); setLive([]); convs.reload(); if (!cid) nav(`/chat/${id}`, { replace: true }); }
  };
  const del = async (id: string) => { await api(`/api/conversations/${id}`, { method: "DELETE" }); convs.reload(); if (id === cid) nav("/chat"); };

  const t = team.data;
  return (
    <div className="-m-4 flex h-[calc(100vh-3rem)] sm:-m-6 lg:-m-8 lg:h-screen">
      <section className="relative flex min-w-0 flex-1 flex-col">
        <div className="absolute right-3 top-3 z-20 flex gap-1">
          <button onClick={() => setShowHistory(!showHistory)} title="History" aria-label="History" aria-expanded={showHistory}
            className={cx("grid size-8 place-items-center rounded-lg border border-line bg-panel text-muted hover:bg-panel2 hover:text-fg", showHistory && "border-accent text-accent")}>
            <History className="size-4" /></button>
          <button onClick={() => { setShowHistory(false); nav("/chat"); }} title="New chat" aria-label="New chat"
            className="grid size-8 place-items-center rounded-lg border border-line bg-panel text-muted hover:bg-panel2 hover:text-fg"><Plus className="size-4" /></button>
          {showHistory && (
            <div className="absolute right-0 top-10 w-80 overflow-hidden rounded-xl border border-line bg-panel shadow-lg">
              <div className="border-b border-line px-3 py-2 text-xs font-semibold uppercase tracking-wide text-faint">Your conversations</div>
              <div className="max-h-80 overflow-y-auto p-1 scroll-thin">
                {(convs.data || []).length ? (convs.data || []).map((c) => (
                  <div key={c.id} className={cx("group flex items-center rounded-lg", c.id === cid ? "bg-accentsoft" : "hover:bg-panel2")}>
                    <Link to={`/chat/${c.id}`} onClick={() => setShowHistory(false)}
                      className={cx("min-w-0 flex-1 truncate px-2.5 py-2 text-[13px]", c.id === cid ? "font-medium text-accent" : "text-fg")}>{c.title}</Link>
                    <button onClick={() => del(c.id)} className="mr-1 hidden rounded p-1 text-faint hover:text-bad group-hover:block" aria-label="Delete"><Trash2 className="size-3.5" /></button>
                  </div>)) : <div className="px-3 py-4 text-center text-[13px] text-muted">No conversations yet.</div>}
              </div>
              <Link to="/history" className="block border-t border-line px-3 py-2 text-center text-[13px] text-accent hover:bg-panel2">See full history</Link>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-6 scroll-thin sm:px-8">
          <div className="mx-auto max-w-3xl space-y-5">
            {!msgs.length && t && (
              <div className="pt-6">
                {t.persona ? (
                  <div className="flex items-start gap-4">
                    <PersonaAvatar p={t.persona} size="size-14" />
                    <div className="min-w-0">
                      <h1 className="text-2xl font-semibold tracking-tight">{t.persona.name}</h1>
                      <div className="text-[13px] text-muted">{t.persona.role}</div>
                      <div className="mt-3 inline-block rounded-2xl rounded-tl-sm bg-panel2 px-4 py-2.5 text-[14.5px]">{t.persona.greeting}</div>
                    </div>
                  </div>
                ) : <h1 className="text-2xl font-semibold tracking-tight">Your agent team</h1>}
                <p className="mt-4 text-muted">{t.summary || "Ask anything about your product, documents or data."}</p>
                {!t.published && <div className="mt-4"><Alert tone="warn" title="No published blueprint yet">Aria Analyst answers from your documents and data. Aria Executor needs a published blueprint to know which actions exist. {can("blueprint:view") && <Link to="/understand" className="font-medium underline">Understand your product</Link>}</Alert></div>}
                <div className="mt-6 rounded-xl border border-accent/40 bg-accentsoft/60 p-4">
                  <div className="flex items-center gap-2 font-semibold"><Network className="size-5 text-accent" /> Aria · Orchestrator</div>
                  <div className="mt-0.5 text-[13px] text-muted">Plans, coordinates and ensures everything follows the rules.</div>                </div>
                <div className="ml-6 h-3 border-l-2 border-accent/30" />
                <div className="grid gap-2 sm:grid-cols-3">
                  {t.leads.map((a) => (
                    <div key={a.id} className="rounded-xl border border-line bg-panel p-3">
                      <div className="flex items-center gap-2 text-sm font-semibold">{a.id === "executor" ? <PenLine className="size-4 text-warn" /> : <Bot className="size-4 text-info" />}{a.name}</div>
                      <div className="mt-0.5 text-xs text-muted">{a.id === "executor" ? "Makes approved changes to the product." : "Reads company data and answers questions."}</div>
                    </div>))}
                  {can("approvals:view") && (
                    <Link to="/activity" className="rounded-xl border border-line bg-panel p-3 hover:border-line2">
                      <div className="flex items-center gap-2 text-sm font-semibold"><Eye className="size-4 text-muted" />Aria Watch<CountBadge n={watchCount} className="ml-auto" /></div>
                      <div className="mt-0.5 text-xs text-muted">Monitors activity and suggests improvements.</div>
                    </Link>)}
                </div>
                {t.agents.length > 0 && <div className="mt-3 text-xs text-muted">Specialists the agents can call on: {t.agents.map((a) => a.name).join(", ")}</div>}
                {t.starter_questions.length > 0 && (
                  <div className="mt-6 flex flex-wrap gap-2">{t.starter_questions.slice(0, 6).map((q) => <button key={q} onClick={() => send(q)} className="rounded-full border border-line2 bg-panel px-3 py-1.5 text-[13px] text-muted hover:border-accent hover:text-fg">{q}</button>)}</div>
                )}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={cx("fade-in flex gap-3", m.role === "user" && "flex-row-reverse")}>
                <div className={cx("grid size-8 shrink-0 place-items-center rounded-full", m.role === "user" ? "bg-panel2" : "bg-accent text-white")}>{m.role === "user" ? <User className="size-4" /> : <Network className="size-4" />}</div>
                <div className={cx("min-w-0 max-w-[85%]", m.role === "user" && "text-right")}>
                  <div className={cx("inline-block rounded-2xl px-4 py-2.5 text-left text-[14px] leading-relaxed", m.role === "user" ? "bg-accent text-white" : "border border-line bg-panel")}>
                    {m.role === "user" ? <span className="whitespace-pre-wrap">{m.content}</span> : <div className="prose-chat" dangerouslySetInnerHTML={{ __html: md(m.content) }} />}
                  </div>
                  {m.role === "assistant" && (m.trace || []).filter((e) => e.type === "plan").map((e) => <PlanCard key={e.plan_id} id={e.plan_id} />)}
                  {m.role === "assistant" && m.trace && m.trace.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <button onClick={() => setSelTrace(m.trace!)} className="text-xs text-muted hover:text-accent">View trace ({m.trace.length} steps)</button>
                      {m.trace.filter((e) => e.type === "decision").map((d) => <DecisionChip key={d.decision_id} d={d} />)}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex gap-3"><div className="grid size-8 place-items-center rounded-full bg-accent text-white"><Network className="size-4" /></div>
                <div className="rounded-2xl border border-line bg-panel px-4 py-3 text-sm text-muted"><span className="typing mr-2"><span /><span /><span /></span>{liveStatus(live)}</div></div>
            )}
            <div ref={end} />
          </div>
        </div>
        <div className="border-t border-line bg-panel px-4 py-3 sm:px-8">
          <form onSubmit={(e) => { e.preventDefault(); send(text); }} className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={1}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }}
              className="max-h-40 min-h-[42px] flex-1 resize-none rounded-xl border border-line2 bg-panel px-4 py-2.5 text-sm outline-none focus:border-accent focus:ring-3 focus:ring-accent/20" />
            <Button variant="primary" className="h-[42px] w-[42px] !px-0" disabled={!text.trim() || busy} aria-label="Send"><ArrowUp className="size-4" /></Button>
          </form>
        </div>
      </section>

      <aside className="hidden w-[380px] shrink-0 flex-col border-l border-line bg-panel xl:flex">
        <div className="border-b border-line px-4 py-3"><div className="font-semibold">Live trace</div><div className="text-xs text-muted">Every agent step, tool call, rule check and decision</div></div>
        <div className="flex-1 overflow-y-auto p-4 scroll-thin">
          {(busy ? live : selTrace)?.length ? <Trace events={(busy ? live : selTrace)!} /> : <Empty title="Nothing yet">Send a message to watch the team work.</Empty>}
        </div>
      </aside>
    </div>
  );
}

function liveStatus(live: any[]) {
  const e = [...live].reverse().find((x) => ["delegate", "tool_call", "agent_start", "plan_start", "plan"].includes(x.type));
  if (!e) return "Aria is planning…";
  if (e.type === "delegate") return `${who(e.agent)} → ${who(e.to)}…`;
  if (e.type === "agent_start") return `${e.name} is working…`;
  if (e.type === "tool_call") return `${who(e.agent)}: ${e.tool.replace("_", " ")}…`;
  if (e.type === "plan") return "Plan ready for your approval…";
  return "Aria is planning…";
}

function DecisionChip({ d }: { d: any }) {
  const tone = d.status === "EXECUTED" ? "ok" : d.status === "PENDING_REVIEW" ? "warn" : "bad";
  return <Link to={`/approvals/${d.decision_id}`}><Badge tone={tone}><Gavel className="size-3" />{d.action}: {d.status.replace("_", " ").toLowerCase()}</Badge></Link>;
}

const NAMES: Record<string, string> = { aria: "Aria Orchestrator", analyst: "Aria Analyst", executor: "Aria Executor", watch: "Aria Watch" };
const who = (id: string) => NAMES[id] || id;

function Row({ icon, who, children, tone, depth = 0 }: { icon: ReactNode; who: string; children: ReactNode; tone?: string; depth?: number }) {
  return (
    <div className="relative pb-4 pl-7 last:pb-0" style={{ marginLeft: Math.min(depth, 3) * 14 }}>
      <div className="absolute left-[11px] top-6 h-[calc(100%-18px)] w-px bg-line" />
      <div className={cx("absolute left-0 top-0.5 grid size-6 place-items-center rounded-full border border-line bg-panel", tone)}>{icon}</div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-faint">{who}</div>
      <div className="mt-0.5 text-[13px]">{children}</div>
    </div>
  );
}

function Trace({ events }: { events: any[] }) {
  return (
    <div>
      {events.map((e, i) => {
        const d = e.depth ?? 0;
        switch (e.type) {
          case "plan_start": return <Row key={i} depth={d} icon={<Network className="size-3 text-accent" />} who="Aria Orchestrator · understanding your request">{e.text}</Row>;
          case "delegate": return <Row key={i} depth={d} icon={<Network className="size-3 text-accent" />} who={`${who(e.agent)} → ${who(e.to)}`}><span className="text-muted">{e.task}</span></Row>;
          case "agent_start": return <Row key={i} depth={d} icon={<Bot className="size-3" />} who={e.name}>Working…</Row>;
          case "agent_end": return <Row key={i} depth={d} icon={<CheckCircle2 className="size-3 text-ok" />} who={`${who(e.agent)} · report`}><span className="line-clamp-4 text-muted">{e.report}</span></Row>;
          case "plan": return (
            <Row key={i} depth={d} icon={<ClipboardList className="size-3 text-warn" />} who={`${who(e.agent)} · plan proposed`} tone="!bg-warnsoft">
              <b>{e.title}</b>, {e.steps} step(s), nothing has run. Waiting for <b>{e.approver}</b>.
            </Row>);
          case "tool_call": return null;
          case "data": return (
            <Row key={i} depth={d} icon={<Database className="size-3 text-info" />} who={`${who(e.agent)} · query_data`}>
              <div className="rounded bg-panel2 px-2 py-1 font-mono text-[11px] break-all">{e.sql}</div>
              <div className="mt-1 text-xs text-muted">{e.connection} · {e.rows} row(s) · SQL guard passed</div>
            </Row>);
          case "knowledge": return <Row key={i} depth={d} icon={<BookOpen className="size-3 text-info" />} who={`${who(e.agent)} · search`}>"{e.query}" → {e.hits.length ? e.hits.map((h: any) => `${h.document} p.${h.page}`).join(", ") : "no passages"}</Row>;
          case "api": return <Row key={i} depth={d} icon={<Globe className="size-3 text-info" />} who={`${who(e.agent)} · call_api`}>GET {e.path} → {e.status}</Row>;
          case "rules": return (
            <Row key={i} depth={d} icon={<Gavel className="size-3 text-warn" />} who={`${who(e.agent)} · rule engine`}>
              {e.action}: <b>{e.verdict}</b>
              <div className="mt-1 flex flex-wrap gap-1">{e.hard.map((h: any) => <Badge key={h.id} tone={h.status === "PASS" ? "ok" : h.status === "NOT_APPLICABLE" ? "neutral" : "bad"}>{h.id}</Badge>)}</div>
            </Row>);
          case "decision": return (
            <Row key={i} icon={<Gavel className="size-3" />} who={`${e.agent} · Sentinel`} tone={e.effect === "ALLOW" ? "!bg-oksoft" : e.effect === "REVIEW" ? "!bg-warnsoft" : "!bg-badsoft"}>
              <div className="flex flex-wrap items-center gap-1.5"><b>{e.action}</b><Badge tone={e.verdict === "VALID" ? "ok" : e.verdict === "INVALID" ? "bad" : "warn"}>{e.verdict}</Badge>
                <Badge tone={e.effect === "ALLOW" ? "ok" : e.effect === "REVIEW" ? "warn" : "bad"}>{e.effect}</Badge></div>
              <ul className="mt-1 list-disc pl-4 text-xs text-muted">{e.reasons.map((r: string, j: number) => <li key={j}>{r}</li>)}</ul>
              <Link to={`/approvals/${e.decision_id}`} className="text-xs text-accent">Open decision →</Link>
            </Row>);
          case "blocked": return <Row key={i} depth={d} icon={<ShieldAlert className="size-3 text-bad" />} who={`${who(e.agent)} · refused`}><span className="text-bad">{e.reason}</span></Row>;
          case "warning": return <Row key={i} icon={<AlertTriangle className="size-3 text-warn" />} who="Sentinel">{e.text}</Row>;
          case "error": return <Row key={i} icon={<AlertTriangle className="size-3 text-bad" />} who="Error"><span className="text-bad">{e.text}</span></Row>;
          case "final": return <Row key={i} icon={<CheckCircle2 className="size-3 text-ok" />} who="Aria Orchestrator · results collected">Answered in {e.seconds}s</Row>;
          default: return null;
        }
      })}
    </div>
  );
}
