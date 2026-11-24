import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ClipboardList, Database, Send, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { api, fmtNum } from "../lib/api";
import { Badge, Button, Spinner, Textarea, cx, useToast } from "./ui";

export type Plan = {
  id: string; title: string; summary: string; status: string; source: string; owner_role: string | null; accountable: string | null;
  can_decide: boolean; results: any[]; steps: any[];
};
const tone = (s: string) => (["EXECUTED", "VALID", "ALLOW", "executed"].includes(s) ? "ok" : ["PENDING_REVIEW", "REVIEW", "INSUFFICIENT_EVIDENCE", "escalated", "awaiting_approval", "partial"].includes(s) ? "warn" : "bad") as "ok" | "warn" | "bad";
const label = (s: string) => s.replace(/_/g, " ").toLowerCase();

export default function PlanCard({ id, initial }: { id: string; initial?: Plan }) {
  const toast = useToast();
  const [p, setP] = useState<Plan | null>(initial || null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"" | "a" | "r">("");
  useEffect(() => { api<Plan>(`/api/plans/${id}`).then(setP).catch(() => {}); }, [id]);
  if (!p) return <div className="mt-2 flex items-center gap-2 text-xs text-muted"><Spinner /> Loading plan…</div>;

  const decide = async (approve: boolean) => {
    setBusy(approve ? "a" : "r");
    try { setP(await api<Plan>(`/api/plans/${id}/decide`, { body: { approve, note } })); toast(approve ? "Plan approved, see the results" : "Plan rejected"); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(""); }
  };
  const waiting = p.status === "awaiting_approval";
  const escalate = p.steps.filter((s) => s.authority && !s.authority.within);
  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-accent/40 bg-panel text-left">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-accentsoft/50 px-4 py-2.5">
        <ClipboardList className="size-4 text-accent" />
        <span className="text-sm font-semibold">{p.title}</span>
        <span className="text-xs text-muted">· proposed by Aria Executor{p.source === "watch" && " from an Aria Watch suggestion"}</span>
        <Badge tone={waiting ? "warn" : tone(p.status)} className="ml-auto">{waiting ? "waiting for your approval" : label(p.status)}</Badge>
      </div>
      {p.summary && <p className="px-4 pt-3 text-[13px] text-muted">{p.summary}</p>}
      <ol className="space-y-2 p-4">
        {p.steps.map((s, i) => {
          const r = p.results?.[i];
          return (
            <li key={i} className="rounded-lg border border-line p-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="grid size-5 place-items-center rounded-full bg-panel2 text-[11px] font-semibold">{i + 1}</span>
                <span className="font-mono text-[13px] font-semibold">{s.action}</span>
                {s.risk && <Badge tone={s.risk === "HIGH" ? "bad" : s.risk === "MEDIUM" ? "warn" : "ok"}>{s.risk} risk</Badge>}
                {s.verdict && <Badge tone={tone(s.verdict)}>rules: {label(s.verdict)}</Badge>}
                {s.amount != null && <span className="text-xs text-muted">amount {fmtNum(s.amount)}</span>}
                <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted">{s.executor === "database" ? <><Database className="size-3" /> database write</> : <><Send className="size-3" /> webhook</>}</span>
              </div>
              <div className="mt-1 text-[13px]">{s.summary}</div>
              {s.rules?.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{s.rules.map((h: any) => <Badge key={h.id} tone={h.status === "PASS" ? "ok" : h.status === "NOT_APPLICABLE" ? "neutral" : "bad"}>{h.id}</Badge>)}</div>}
              {waiting && s.authority && (
                <div className={cx("mt-2 flex items-start gap-1.5 text-xs", s.authority.within ? "text-ok" : "text-warn")}>
                  {s.authority.within ? <ShieldCheck className="mt-px size-3.5" /> : <ShieldAlert className="mt-px size-3.5" />}
                  <span>{s.authority.within ? "Within your authority." : s.authority.reasons.join("; ") + `, will go to ${s.owner_role} for approval.`}</span>
                </div>
              )}
              {s.error && <div className="mt-1 text-xs text-bad">{s.error}</div>}
              {r && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-line pt-2 text-xs">
                  <Badge tone={tone(r.status)}>{label(r.status)}</Badge>
                  <span className="text-muted">{(r.reasons || []).join("; ")}</span>
                  {r.execution?.error && <span className="text-bad">{r.execution.error}</span>}
                  {r.execution?.operation && <span className="text-muted">· {r.execution.operation} on {r.execution.table}</span>}
                  {r.decision_id && <Link to={`/approvals/${r.decision_id}`} className="ml-auto text-accent">decision →</Link>}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {waiting && p.can_decide && (
        <div className="space-y-2 border-t border-line px-4 py-3">
          <p className="text-xs text-muted">By approving, <b className="text-fg">you are accountable</b> for these actions, not Aria. Each step is still checked by the rules
            {escalate.length > 0 ? `, and ${escalate.length} step(s) beyond your authority will go to their owner for approval.` : "."}</p>
          <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2">
            <Button variant="ok" icon={<CheckCircle2 className="size-4" />} loading={busy === "a"} onClick={() => decide(true)}>Approve & run</Button>
            <Button variant="danger" icon={<XCircle className="size-4" />} loading={busy === "r"} onClick={() => decide(false)}>Reject</Button>
          </div>
        </div>
      )}
      {waiting && !p.can_decide && <div className="border-t border-line px-4 py-2.5 text-xs text-muted">Waiting for {p.owner_role ? `the ${p.owner_role} role` : "the person it was proposed to"}.</div>}
      {p.accountable && !waiting && <div className="border-t border-line px-4 py-2 text-xs text-muted">{p.status === "rejected" ? "Rejected" : "Approved"} by <b className="text-fg">{p.accountable}</b>, accountable for this plan.</div>}
    </div>
  );
}
