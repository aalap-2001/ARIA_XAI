import { useState } from "react";
import { Gauge } from "lucide-react";
import { api, fmtNum } from "../../lib/api";
import { Card, Empty, ErrorBox, Loading, PageHead, Select, useAsync } from "../../components/ui";

export default function Usage() {
  const [days, setDays] = useState(30);
  const u = useAsync<any[]>(() => api(`/api/usage?days=${days}`), [days]);
  const rows = u.data || [];
  const tot = rows.reduce((a, r) => ({ calls: a.calls + r.calls, inp: a.inp + r.input_tokens, out: a.out + r.output_tokens, err: a.err + r.errors }), { calls: 0, inp: 0, out: 0, err: 0 });
  return (
    <>
      <PageHead title="Usage" sub="Model calls made by your agents and by product understanding, per day, provider and model."
        right={<Select value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-36"><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></Select>} />
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["Model calls", tot.calls], ["Input tokens", tot.inp], ["Output tokens", tot.out], ["Failed calls", tot.err]].map(([l, v]) => (
          <Card key={l as string} className="px-5 py-4"><div className="text-2xl font-semibold">{fmtNum(v as number)}</div><div className="text-[13px] text-muted">{l}</div></Card>))}
      </div>
      {u.loading ? <Loading /> : u.error ? <ErrorBox error={u.error} /> : !rows.length ? <Empty icon={<Gauge className="size-8" />} title="No usage yet">Usage appears once agents start working.</Empty> : (
        <Card className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-5 py-2.5">Day</th><th>Provider</th><th>Model</th><th className="text-right">Calls</th><th className="text-right">Input</th><th className="text-right">Output</th><th className="text-right">Errors</th><th className="pr-5 text-right">Avg latency</th></tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i} className="border-b border-line last:border-0"><td className="px-5 py-2.5">{r.day}</td><td>{r.provider}</td><td className="font-mono text-xs">{r.model}</td>
            <td className="text-right">{fmtNum(r.calls)}</td><td className="text-right">{fmtNum(r.input_tokens)}</td><td className="text-right">{fmtNum(r.output_tokens)}</td><td className="text-right">{r.errors}</td><td className="pr-5 text-right">{fmtNum(r.avg_latency_ms)} ms</td></tr>)}</tbody>
        </table></Card>
      )}
    </>
  );
}
