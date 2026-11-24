import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity as ActivityIcon, Eye } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import { Badge, Card, Empty, ErrorBox, Loading, Modal, PageHead, Select, useAsync } from "../components/ui";

const TONE: Record<string, "neutral" | "info" | "ok" | "warn" | "bad"> = { received: "info", investigating: "info", ignored: "neutral", no_action: "ok", suggested: "warn", failed: "bad" };
const LABEL: Record<string, string> = { received: "queued", investigating: "investigating", ignored: "ignored", no_action: "no change needed", suggested: "suggestion made", failed: "failed" };

export default function Activity() {
  const [status, setStatus] = useState("");
  const ev = useAsync<any[]>(() => api(`/api/events${status ? `?status=${status}` : ""}`), [status]);
  const [open, setOpen] = useState<any | null>(null);
  const busy = (ev.data || []).some((e) => e.status === "received" || e.status === "investigating");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => ev.reload(), 3000);
    return () => clearInterval(t);
  }, [busy]); // eslint-disable-line react-hooks/exhaustive-deps
  const counts: Record<string, number> = {};
  for (const e of ev.data || []) counts[e.status] = (counts[e.status] || 0) + 1;
  return (
    <>
      <PageHead title="Aria Watch" sub="Monitors activity and suggests improvements. Each event your product sends is checked against the watch rules; only matching events are investigated, and only a clear benefit becomes a suggestion for the responsible owner in Approvals."
        right={<Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-48">
          <option value="">All events</option>{Object.keys(LABEL).map((s) => <option key={s} value={s}>{LABEL[s]}</option>)}</Select>} />
      {(ev.data || []).length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2 text-[13px]">{Object.entries(counts).map(([s, n]) => <Badge key={s} tone={TONE[s]}>{LABEL[s] || s}: {n}</Badge>)}</div>
      )}
      {ev.loading ? <Loading /> : ev.error ? <ErrorBox error={ev.error} /> : !ev.data!.length ? (
        <Empty icon={<ActivityIcon className="size-8" />} title="No events yet">Send events from your product with a secret API key, see <Link to="/settings/api" className="text-accent">API & widget</Link> for the snippet.</Empty>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-5 py-2.5">Event</th><th>Entity</th><th>Watch rule</th><th>Outcome</th><th>Received</th><th /></tr></thead>
            <tbody>{ev.data!.map((e) => (
              <tr key={e.id} className="border-b border-line align-top last:border-0">
                <td className="px-5 py-3 font-mono text-[13px]">{e.type}</td>
                <td className="py-3 text-[13px]">{e.entity_id || "-"}</td>
                <td className="py-3 text-xs">{e.matched_rule ? <Badge tone="accent">{e.matched_rule}</Badge> : <span className="text-faint">none</span>}</td>
                <td className="max-w-md py-3"><Badge tone={TONE[e.status]}>{LABEL[e.status] || e.status}</Badge>{e.note && <div className="mt-1 line-clamp-2 text-xs text-muted">{e.note}</div>}</td>
                <td className="whitespace-nowrap py-3 text-xs text-muted">{fmtDate(e.received_at)}</td>
                <td className="pr-5 text-right">{e.trace?.length > 0 && <button onClick={() => setOpen(e)} className="text-xs text-accent">trace</button>}
                  {e.suggestion_id && <div><Link to="/approvals" className="text-xs text-accent">suggestion →</Link></div>}</td>
              </tr>))}</tbody>
          </table>
        </Card>
      )}
      <Modal open={!!open} onClose={() => setOpen(null)} wide title={<span className="inline-flex items-center gap-2"><Eye className="size-4" /> Aria Watch · {open?.type}</span>}>
        {open && (
          <div className="space-y-3 text-[13px]">
            <pre className="overflow-x-auto rounded-lg bg-panel2 p-3 text-xs">{JSON.stringify(open.data, null, 2)}</pre>
            <ol className="space-y-2">{open.trace.filter((t: any) => t.type !== "tool_call").map((t: any, i: number) => (
              <li key={i} className="rounded-lg border border-line p-2.5" style={{ marginLeft: Math.min(t.depth || 0, 3) * 14 }}>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-faint">{t.name || t.agent} · {t.type.replace("_", " ")}</div>
                <div className="mt-0.5">{t.report || t.task || t.sql || t.query || t.reason || t.text || (t.verdict && `${t.action}: ${t.verdict}`) || ""}</div>
              </li>))}</ol>
          </div>
        )}
      </Modal>
    </>
  );
}
