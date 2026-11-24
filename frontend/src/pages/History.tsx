import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, History as HistoryIcon, Network, User } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import { Badge, Card, Empty, ErrorBox, Loading, PageHead, Select, cx, useAsync } from "../components/ui";
import PlanCard from "../components/PlanCard";

type Conv = { id: string; title: string; channel: string; end_user_id: string; messages: number; user: { id: string; name: string; email: string } | null; updated_at: string };
const CHANNEL: Record<string, string> = { console: "Console", api: "API", widget: "Widget" };

export default function History() {
  const { cid } = useParams();
  return cid ? <Conversation id={cid} /> : <List />;
}

function List() {
  const [user, setUser] = useState("");
  const [channel, setChannel] = useState("");
  const h = useAsync<{ conversations: Conv[]; can_see_everyone: boolean; users?: { id: string; name: string; email: string }[] }>(
    () => api(`/api/history?${new URLSearchParams({ ...(user && { user_id: user }), ...(channel && { channel }) })}`), [user, channel]);
  return (
    <>
      <PageHead title="History" sub={h.data?.can_see_everyone ? "Every conversation with the agent team, by user. Open one to see what each agent did and which plans were approved." : "Your conversations with the agent team, with what each agent did."}
        right={h.data?.can_see_everyone && <>
          <Select value={user} onChange={(e) => setUser(e.target.value)} className="w-56" aria-label="User">
            <option value="">All users</option>{(h.data.users || []).map((u) => <option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</Select>
          <Select value={channel} onChange={(e) => setChannel(e.target.value)} className="w-36" aria-label="Channel">
            <option value="">All channels</option>{Object.entries(CHANNEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
        </>} />
      {h.loading ? <Loading /> : h.error ? <ErrorBox error={h.error} /> : !h.data!.conversations.length ? (
        <Empty icon={<HistoryIcon className="size-8" />} title="No conversations">Conversations with the agent team appear here.</Empty>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-5 py-2.5">Conversation</th><th>User</th><th>Channel</th><th className="text-right">Messages</th><th className="pr-5">Last activity</th></tr></thead>
            <tbody>{h.data!.conversations.map((c) => (
              <tr key={c.id} className="border-b border-line last:border-0 hover:bg-panel2/50">
                <td className="px-5 py-3"><Link to={`/history/${c.id}`} className="font-medium hover:text-accent">{c.title}</Link></td>
                <td className="text-[13px]">{c.user ? <>{c.user.name}<div className="text-xs text-muted">{c.user.email}</div></> : <span className="text-muted">{c.end_user_id ? `End user ${c.end_user_id}` : "External"}</span>}</td>
                <td><Badge>{CHANNEL[c.channel] || c.channel}</Badge></td>
                <td className="text-right">{c.messages}</td>
                <td className="pr-5 text-xs text-muted">{fmtDate(c.updated_at)}</td>
              </tr>))}</tbody>
          </table>
        </Card>
      )}
    </>
  );
}

function Conversation({ id }: { id: string }) {
  const nav = useNavigate();
  const c = useAsync<any>(() => api(`/api/history/${id}`), [id]);
  if (c.loading) return <Loading />;
  if (c.error) return <ErrorBox error={c.error} />;
  const x = c.data;
  return (
    <>
      <button onClick={() => nav("/history")} className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-fg"><ArrowLeft className="size-4" /> History</button>
      <PageHead title={x.title} sub={<>{x.user ? `${x.user.name} (${x.user.email})` : x.end_user_id ? `End user ${x.end_user_id}` : "External"} · {CHANNEL[x.channel] || x.channel} · started {fmtDate(x.created_at)}</>} />
      <div className="mx-auto max-w-3xl space-y-5">
        {x.messages.map((m: any) => (
          <div key={m.id} className={cx("flex gap-3", m.role === "user" && "flex-row-reverse")}>
            <div className={cx("grid size-8 shrink-0 place-items-center rounded-full", m.role === "user" ? "bg-panel2" : "bg-accent text-white")}>{m.role === "user" ? <User className="size-4" /> : <Network className="size-4" />}</div>
            <div className={cx("min-w-0 max-w-[85%]", m.role === "user" && "text-right")}>
              <div className={cx("inline-block whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-left text-[14px]", m.role === "user" ? "bg-accent text-white" : "border border-line bg-panel")}>{m.content}</div>
              <div className="mt-1 text-xs text-faint">{fmtDate(m.created_at)}</div>
              {m.role === "assistant" && (m.trace || []).filter((e: any) => e.type === "plan").map((e: any) => <PlanCard key={e.plan_id} id={e.plan_id} />)}
              {m.role === "assistant" && m.trace?.length > 0 && (
                <details className="mt-1 text-left"><summary className="cursor-pointer text-xs text-muted">What the agents did ({m.trace.length} steps)</summary>
                  <ol className="mt-2 space-y-1 rounded-lg border border-line bg-panel p-3 text-xs">
                    {m.trace.filter((e: any) => !["tool_call"].includes(e.type)).map((e: any, i: number) => (
                      <li key={i} style={{ marginLeft: Math.min(e.depth || 0, 3) * 14 }}><b>{e.name || e.agent || "Aria Orchestrator"}</b> · {e.type.replace("_", " ")}
                        <span className="text-muted"> {e.task || e.report || e.sql || e.title || e.text || e.query || (e.verdict ? `${e.action}: ${e.verdict}` : "")}</span></li>))}
                  </ol></details>)}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
