import { useState } from "react";
import { ShieldCheck, ShieldX } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import { Alert, Badge, Button, Card, ErrorBox, Input, Loading, PageHead, useAsync } from "../components/ui";

export default function Audit() {
  const log = useAsync<any[]>(() => api("/api/audit?limit=1000"));
  const [verify, setVerify] = useState<any>(null);
  const [wd, setWd] = useState<any>(null);
  const [q, setQ] = useState("");
  const rows = (log.data || []).filter((e) => !q || JSON.stringify(e).toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <PageHead title="Audit log" sub="Every sign-in, configuration change, model call setting, blueprint, decision and approval, in a per-organisation hash chain."
        right={<><Input value={q} onChange={(e) => setQ(e.target.value)} className="w-56" /><Button onClick={async () => setVerify(await api("/api/audit/verify"))}>Verify chain</Button>
          <Button onClick={async () => setWd(await api("/api/audit/watchdog"))}>Run watchdog</Button></>} />
      {wd && <div className="mb-4">{wd.ok
        ? <Alert tone="ok" title={<span className="inline-flex items-center gap-1.5"><ShieldCheck className="size-4" /> Watchdog: every send was approved</span>}>{wd.checked} outbound send(s) reconciled with approved decisions.</Alert>
        : <Alert tone="bad" title={<span className="inline-flex items-center gap-1.5"><ShieldX className="size-4" /> Watchdog found {wd.incidents.length} incident(s)</span>}>
            <ul className="mt-1 list-disc pl-4">{wd.incidents.slice(0, 10).map((i: any, k: number) => <li key={k}>{i.issue}{i.target && `: ${i.target}`}{i.decision_id && ` (${i.decision_id})`}</li>)}</ul></Alert>}</div>}
      {verify && <div className="mb-4">{verify.ok
        ? <Alert tone="ok" title={<span className="inline-flex items-center gap-1.5"><ShieldCheck className="size-4" /> Chain intact</span>}>{verify.entries} entries verified; head {verify.head.slice(0, 16)}…</Alert>
        : <Alert tone="bad" title={<span className="inline-flex items-center gap-1.5"><ShieldX className="size-4" /> Chain broken</span>}>History was modified at entry #{verify.broken_at}.</Alert>}</div>}
      {log.loading ? <Loading /> : log.error ? <ErrorBox error={log.error} /> : (
        <Card className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-4 py-2.5">#</th><th>When</th><th>Who</th><th>Event</th><th>Target</th><th>Details</th><th className="pr-4">Hash</th></tr></thead>
            <tbody>{rows.map((e) => (
              <tr key={e.seq} className="border-b border-line align-top last:border-0">
                <td className="px-4 py-2 text-faint">{e.seq}</td><td className="whitespace-nowrap py-2 text-muted">{fmtDate(e.at)}</td><td className="py-2">{e.actor}</td>
                <td className="py-2"><Badge>{e.kind}</Badge></td><td className="max-w-[180px] truncate py-2 font-mono text-xs">{e.target}</td>
                <td className="max-w-[340px] py-2 text-xs text-muted"><span className="line-clamp-2">{Object.keys(e.detail || {}).length ? JSON.stringify(e.detail) : ""}</span></td>
                <td className="py-2 pr-4 font-mono text-xs text-faint">{e.hash.slice(0, 10)}</td>
              </tr>))}</tbody>
          </table>
        </Card>
      )}
    </>
  );
}
