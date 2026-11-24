import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCheck, Eye, Gavel } from "lucide-react";
import { api, fmtDate, fmtNum } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Badge, Button, Card, CardHead, Empty, ErrorBox, Loading, PageHead, Tabs, Textarea, useAsync, useToast } from "../components/ui";

const tone = (s: string) => (s === "EXECUTED" || s === "VALID" || s === "ALLOW" ? "ok" : s === "PENDING_REVIEW" || s === "REVIEW" || s === "INSUFFICIENT_EVIDENCE" ? "warn" : "bad") as "ok" | "warn" | "bad";
const label = (s: string) => s.replace(/_/g, " ").toLowerCase();

export default function Approvals() {
  const { did } = useParams();
  return did ? <DecisionDetail id={did} /> : <Queue />;
}

function Queue() {
  const [tab, setTab] = useState<"suggestions" | "pending" | "all">("suggestions");
  const list = useAsync<any[]>(() => tab === "suggestions" ? Promise.resolve([]) : api(`/api/decisions${tab === "pending" ? "?status=PENDING_REVIEW&mine=true" : ""}`), [tab]);
  return (
    <>
      <PageHead title="Approvals" sub="Suggestions from Aria Watch for your area, and actions escalated to your role because they went beyond the requester's authority. Whoever approves is accountable." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "suggestions", label: "Suggestions (Aria Watch)" }, { id: "pending", label: "Escalated to my role" }, { id: "all", label: "All decisions" }]} />
      <div className="mt-4">
        {tab === "suggestions" ? <Suggestions /> : list.loading ? <Loading /> : list.error ? <ErrorBox error={list.error} /> : !list.data!.length ? (
          <Empty icon={<CheckCheck className="size-8" />} title={tab === "pending" ? "Nothing escalated to you" : "No decisions yet"}>Actions appear here when a plan step goes beyond the approver's authority and your role owns that area.</Empty>
        ) : (
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-4 py-2.5">Action</th><th>Agent</th><th>Amount</th><th>Rules</th><th>Status</th><th>Requested</th><th /></tr></thead>
              <tbody>
                {list.data!.map((d) => (
                  <tr key={d.id} className="border-b border-line last:border-0 hover:bg-panel2/50">
                    <td className="px-4 py-3"><div className="font-mono text-[13px] font-medium">{d.action}</div><div className="line-clamp-1 max-w-sm text-xs text-muted">{d.summary}</div></td>
                    <td className="text-[13px]">{d.agent}</td><td>{fmtNum(d.amount)}</td>
                    <td><Badge tone={tone(d.verdict)}>{label(d.verdict)}</Badge></td><td><Badge tone={tone(d.status)}>{label(d.status)}</Badge></td>
                    <td className="text-xs text-muted">{fmtDate(d.created_at)}<div>{d.accountable ? <>accountable: {d.accountable}</> : d.requested_by}</div>{d.owner_role && <div>owner: {d.owner_role}</div>}</td>
                    <td className="pr-4 text-right"><Link to={`/approvals/${d.id}`}><Button size="sm">{d.status === "PENDING_REVIEW" ? "Review" : "Open"}</Button></Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </>
  );
}

function Suggestions() {
  const toast = useToast();
  const [show, setShow] = useState<"pending" | "">("pending");
  const list = useAsync<any[]>(() => api(`/api/suggestions${show ? "?status=pending" : ""}`), [show]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const decide = async (s: any, approve: boolean) => {
    setBusy(s.id + approve);
    try {
      const r = await api(`/api/suggestions/${s.id}/decide`, { body: { approve, note: notes[s.id] || "" } });
      toast(approve ? `Approved, Aria Executor ran it: ${r.plan?.status ?? r.status}` : "Suggestion rejected");
      list.reload();
    } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };
  return (
    <div className="space-y-3">
      <div className="flex gap-2"><Button size="sm" variant={show ? "primary" : "secondary"} onClick={() => setShow("pending")}>Waiting</Button><Button size="sm" variant={show ? "secondary" : "primary"} onClick={() => setShow("")}>All</Button></div>
      {list.loading ? <Loading /> : !list.data!.length ? (
        <Empty icon={<Eye className="size-8" />} title="No suggestions">Aria Watch suggests a change only when an event in your product matches a watch rule and the evidence shows a clear benefit. See <Link to="/activity" className="text-accent">Activity</Link>.</Empty>
      ) : list.data!.map((s) => (
        <Card key={s.id} className="p-5">
          <div className="flex flex-wrap items-center gap-2"><Eye className="size-4 text-accent" /><b>{s.title}</b><Badge>owner: {s.owner_role}</Badge>
            <Badge tone={s.status === "executed" ? "ok" : s.status === "pending" ? "warn" : s.status === "rejected" ? "neutral" : "bad"}>{s.status}</Badge>
            <span className="ml-auto text-xs text-muted">{fmtDate(s.created_at)}</span></div>
          <div className="mt-2 grid gap-3 md:grid-cols-2 text-[13px]">
            <div><div className="text-xs font-semibold uppercase tracking-wide text-faint">What Aria Watch found</div><p className="mt-1">{s.rationale}</p></div>
            <div><div className="text-xs font-semibold uppercase tracking-wide text-faint">Benefit</div><p className="mt-1">{s.benefit}</p></div>
          </div>
          <ol className="mt-3 space-y-1 text-[13px]">{s.steps.map((st: any, i: number) => <li key={i}><span className="font-mono font-medium">{st.action}</span>, {st.summary}</li>)}</ol>
          {s.status === "pending" && s.can_decide && (
            <div className="mt-3 space-y-2 border-t border-line pt-3">
              <p className="text-xs text-muted">Approving hands this to <b className="text-fg">Aria Executor</b>, which runs it with <b className="text-fg">you accountable</b>. The rules and your approval limit still apply.</p>
              <Textarea rows={2} value={notes[s.id] || ""} onChange={(e) => setNotes({ ...notes, [s.id]: e.target.value })} />
              <div className="flex gap-2"><Button variant="ok" loading={busy === s.id + "true"} onClick={() => decide(s, true)}>Approve & run</Button><Button variant="danger" loading={busy === s.id + "false"} onClick={() => decide(s, false)}>Reject</Button></div>
            </div>
          )}
          {s.status === "pending" && !s.can_decide && <p className="mt-3 text-xs text-muted">Waiting for the {s.owner_role} role.</p>}
          {s.decided_by && <p className="mt-2 text-xs text-muted">{s.status === "rejected" ? "Rejected" : "Approved"} by {s.decided_by}{s.note && `: “${s.note}”`}</p>}
        </Card>
      ))}
    </div>
  );
}

function DecisionDetail({ id }: { id: string }) {
  const { can, me } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const d = useAsync<any>(() => api(`/api/decisions/${id}`), [id]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  if (d.loading) return <Loading />;
  if (d.error) return <ErrorBox error={d.error} />;
  const x = d.data;
  const ex = x.explanation || {};
  const limit = me?.scopes.approval_limit;
  const overLimit = limit != null && (x.amount || 0) > limit;
  const act = async (approve: boolean) => {
    setBusy(approve ? "a" : "r");
    try { const r = await api(`/api/decisions/${id}/review`, { body: { approve, note } }); toast(approve ? `Approved, ${label(r.status)}` : "Rejected"); d.reload(); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };
  return (
    <>
      <button onClick={() => nav("/approvals")} className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-fg"><ArrowLeft className="size-4" /> Approvals</button>
      <PageHead title={<span className="inline-flex flex-wrap items-center gap-2"><Gavel className="size-5" /><span className="font-mono">{x.action}</span><Badge tone={tone(x.status)}>{label(x.status)}</Badge></span>}
        sub={<>Proposed by <b>{x.agent === "executor" ? "Aria Executor" : x.agent}</b> for {x.requested_by} · {fmtDate(x.created_at)} · blueprint v{x.blueprint_version} · <span className="font-mono">{x.id}</span>
          <br />Accountable: <b className="text-fg">{x.accountable || "not yet, waiting for " + (x.owner_role || "a reviewer")}</b>{x.owner_role && <> · area owner: {x.owner_role}</>}</>} />

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card><CardHead title="Why the agent asked" />
            <div className="p-5 text-[14px] leading-relaxed">{x.summary || "-"}</div></Card>
          <Card><CardHead title="Part 1 · Facts the agent established" sub="Neural: extracted by the model from your data and documents, with where each came from" />
            <div className="overflow-x-auto p-5"><table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted"><th className="pb-1 pr-6">Fact</th><th className="pb-1 pr-6">Value</th><th className="pb-1 pr-6">Source</th><th className="pb-1">Confidence</th></tr></thead>
              <tbody>{(ex.extraction || Object.entries(x.facts || {}).map(([fact, value]) => ({ fact, value }))).map((e: any) => (
                <tr key={e.fact} className="border-t border-line"><td className="py-1 pr-6 font-mono text-xs text-muted">{e.fact}</td><td className="pr-6">{String(e.value)}</td>
                  <td className="pr-6 text-xs text-muted">{e.source || "not stated"}</td>
                  <td className="text-xs">{e.confidence == null ? <span className="text-faint">not stated</span> : <Badge tone={e.confidence >= 0.8 ? "ok" : e.confidence >= 0.5 ? "warn" : "bad"}>{Math.round(e.confidence * 100)}%</Badge>}</td></tr>))}</tbody>
            </table></div></Card>
          <Card><CardHead title="Parts 2 to 4 · How the rule engine judged it" sub="Symbolic: soft signals → gate → hard rules" right={<Badge tone={tone(x.verdict)}>{label(x.verdict)}</Badge>} />
            <div className="space-y-4 p-5">
              {(ex.gate || []).map((g: any) => (
                <div key={g.signal} className="text-sm"><b>signals.{g.signal}</b> = {g.outcome} <span className="text-muted">(score {g.score ?? "-"}; TRUE ≥ {g.assert_above}, FALSE ≤ {g.deny_below}; {g.why})</span></div>
              ))}
              {(ex.hard || []).map((h: any) => (
                <div key={h.id} className="rounded-lg border border-line p-3">
                  <div className="flex flex-wrap items-center gap-2"><Badge tone={h.status === "PASS" ? "ok" : h.status === "NOT_APPLICABLE" ? "info" : "bad"}>{label(h.status)}</Badge><b className="text-sm">{h.description}</b></div>
                  {h.condition && <div className="mt-1 font-mono text-xs text-muted">{h.condition}</div>}
                  {h.citation && <div className="mt-1 text-xs text-faint">Source: {h.citation}</div>}
                </div>
              ))}
              {!ex.hard && <p className="text-sm text-muted">Not evaluated (blocked before the rules ran).</p>}
            </div></Card>
          <Card><CardHead title="Audit trail" sub="Hash-chained; editing history breaks the chain" />
            <ul className="divide-y divide-line">{x.audit.map((a: any) => <li key={a.seq} className="flex flex-wrap gap-3 px-5 py-2.5 text-[13px]"><span className="w-40 text-muted">{fmtDate(a.at)}</span><b>{a.kind}</b><span className="text-muted">{a.actor}</span><span className="ml-auto font-mono text-xs text-faint">{a.hash.slice(0, 12)}…</span></li>)}</ul></Card>
        </div>

        <div className="space-y-5">
          <Card className="p-5">
            <div className="text-xs font-semibold uppercase tracking-wide text-faint">Sentinel decision</div>
            <div className="mt-2 flex items-center gap-2"><Badge tone={tone(x.effect)}>{x.effect}</Badge><Badge tone={x.risk === "HIGH" ? "bad" : x.risk === "MEDIUM" ? "warn" : "ok"}>{x.risk} risk</Badge>{x.amount != null && <span className="text-sm">amount <b>{fmtNum(x.amount)}</b></span>}</div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[13px]">{x.reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
          </Card>

          {x.status === "PENDING_REVIEW" && !(can("approvals:approve") && (me?.permissions.includes("*") || me?.role === x.owner_role)) && (
            <Card className="p-5 text-[13px] text-muted">Waiting for the <b className="text-fg">{x.owner_role}</b> role to decide.</Card>
          )}
          {x.status === "PENDING_REVIEW" && can("approvals:approve") && (me?.permissions.includes("*") || me?.role === x.owner_role) && (
            <Card className="p-5">
              <div className="font-semibold">Your decision</div>
              {overLimit && <div className="mt-2"><Alert tone="warn">Your approval limit is {fmtNum(limit)}. You can reject, but someone with a higher limit must approve.</Alert></div>}
              <Textarea rows={3} className="mt-3" value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="mt-3 flex gap-2"><Button variant="ok" className="flex-1" loading={busy === "a"} disabled={overLimit} onClick={() => act(true)}>Approve & execute</Button>
                <Button variant="danger" className="flex-1" loading={busy === "r"} onClick={() => act(false)}>Reject</Button></div>
            </Card>
          )}

          {(x.status === "EXECUTED" || x.status === "FAILED" || x.status === "REJECTED") && (
            <Card className="p-5 text-[13px]">
              <div className="font-semibold">{x.status === "REJECTED" ? "Rejected" : "Execution"}</div>
              {x.reviewer && <div className="mt-1 text-muted">Reviewed by {x.reviewer}{x.review_note && <>: “{x.review_note}”</>}</div>}
              {x.execution?.note && <div className="mt-2">{x.execution.note}</div>}
              {x.execution?.url && <div className="mt-2 break-all">POST {x.execution.url} → {x.execution.status_code ?? x.execution.error}</div>}
            </Card>
          )}
          <Card className="p-5"><div className="text-xs font-semibold uppercase tracking-wide text-faint">Payload</div><pre className="mt-2 overflow-x-auto rounded bg-panel2 p-2 text-xs">{JSON.stringify(x.payload, null, 2)}</pre>
            <div className="mt-2 break-all font-mono text-[11px] text-faint">sha256 {x.payload_hash}</div></Card>
        </div>
      </div>
    </>
  );
}
