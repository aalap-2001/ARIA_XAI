import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, Gauge, Inbox, Sparkles, Zap } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Badge, Button, Card, CardHead, ErrorBox, Loading, PageHead, cx, useAsync } from "../components/ui";
import { PersonaAvatar } from "./Studio";
import { useSetup } from "./Setup";

/** The Command Centre: what needs you, what the AI team is doing for you, and what it delivered. */

const STATE: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "info" | "neutral" | "accent" }> = {
  EXECUTED: { label: "done", tone: "ok" }, executed: { label: "done", tone: "ok" }, answered: { label: "answered", tone: "info" },
  PENDING_REVIEW: { label: "needs approval", tone: "warn" }, awaiting_approval: { label: "needs approval", tone: "warn" }, pending: { label: "needs approval", tone: "warn" },
  escalated: { label: "escalated", tone: "warn" }, approved: { label: "approved", tone: "ok" }, BLOCKED: { label: "blocked by rules", tone: "bad" },
  REJECTED: { label: "rejected", tone: "neutral" }, rejected: { label: "rejected", tone: "neutral" }, FAILED: { label: "failed", tone: "bad" }, failed: { label: "failed", tone: "bad" },
};
const money = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });
const hello = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; };
const ago = (iso: string | null) => {
  if (!iso) return "not used yet";
  const d = (Date.now() - new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").getTime()) / 86400000;
  return d < 1 ? "active today" : d < 2 ? "active yesterday" : `active ${Math.floor(d)} days ago`;
};

function Kpi({ icon, value, label, sub, to, tone }: { icon: ReactNode; value: ReactNode; label: string; sub?: ReactNode; to?: string; tone?: string }) {
  const body = (
    <Card className={cx("h-full px-4 py-3.5 transition", to && "hover:border-line2")}>
      <div className="flex items-center gap-1.5 text-[12.5px] text-muted">{icon}{label}</div>
      <div className={cx("mt-1.5 text-[26px] font-semibold leading-none tracking-tight", tone)}>{value}</div>
      {sub && <div className="mt-1.5 text-xs text-muted">{sub}</div>}
    </Card>
  );
  return to ? <Link to={to} className="block h-full">{body}</Link> : body;
}

function ActivityChart({ series }: { series: { day: string; requests: number; decisions: number; completed: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const total = (s: (typeof series)[number]) => s.requests + s.decisions;
  const max = Math.max(1, ...series.map(total));
  const sum = series.reduce((t, s) => t + total(s), 0);
  const label = (d: string) => new Date(d + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });
  const h = hover !== null ? series[hover] : null;
  return (
    <Card>
      <CardHead title="Work handled by the agent team" sub={`Requests answered and actions checked per day, last 30 days. ${sum} in total.`} />
      <div className="relative px-5 pb-4 pt-6">
        {h && (
          <div className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg border border-line bg-panel px-3 py-2 text-xs shadow-md"
            style={{ left: `calc(20px + ${((hover! + 0.5) / series.length) * 100}% - ${((hover! + 0.5) / series.length) * 40}px)` }}>
            <div className="font-medium">{label(h.day)}</div>
            <div className="text-muted">{h.requests} request(s), {h.decisions} action(s) checked, {h.completed} completed</div>
          </div>
        )}
        <div className="flex h-36 items-end gap-[2px] border-b border-line" role="img" aria-label={`Bar chart of work per day over the last 30 days, ${sum} in total`}
          onMouseLeave={() => setHover(null)}>
          {series.map((s, i) => (
            <div key={s.day} className="flex h-full flex-1 items-end" onMouseEnter={() => setHover(i)}>
              <div className={cx("w-full rounded-t-[4px] transition-colors", hover === i ? "bg-accent2" : "bg-accent", total(s) === 0 && "bg-transparent")}
                style={{ height: `${(total(s) / max) * 100}%`, minHeight: total(s) ? 3 : 0 }} />
            </div>
          ))}
        </div>
        <div className="mt-1.5 flex justify-between text-[11px] text-faint"><span>{label(series[0].day)}</span><span>{label(series[series.length - 1].day)}</span></div>
      </div>
    </Card>
  );
}

export default function Home() {
  const { me, can } = useAuth();
  const d = useAsync<any>(() => api("/api/dashboard"));
  const setup = useSetup();
  if (d.loading) return <Loading />;
  if (d.error) return <ErrorBox error={d.error} />;
  const x = d.data, k = x.kpis, p = x.persona;
  const first = me?.user.name.split(" ")[0];
  const setupLeft = setup.steps.length - setup.done;

  return (
    <>
      <PageHead title={`${hello()}, ${first}`}
        sub={x.blueprint ? <>Here is what your agent team is doing for {x.org.replace(" (demo)", "")}. It runs on blueprint version {x.blueprint.version}{x.blueprint.industry && <>, {x.blueprint.industry}</>}.</>
          : "Your agent team is not live yet. Finish the setup to start."}
        right={can("chat:use") && <Link to="/chat"><Button variant="primary" icon={<PersonaAvatar p={p} size="size-5 text-[9px]" />}>Talk to {p.name}</Button></Link>} />

      {!setup.loading && setupLeft > 0 && (
        <Link to="/settings/org" className="mb-5 flex items-center gap-3 rounded-xl border border-accent/30 bg-accentsoft/60 px-4 py-3 text-[13.5px] hover:border-accent/60">
          <Sparkles className="size-4 shrink-0 text-accent" />
          <span className="flex-1"><b>Setup is {setup.done} of {setup.steps.length} done.</b> <span className="text-muted">{setupLeft} step{setupLeft > 1 ? "s" : ""} left before your agent team is fully live.</span></span>
          <span className="flex items-center gap-1 font-medium text-accent">Continue setup<ArrowRight className="size-4" /></span>
        </Link>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi icon={<Inbox className="size-3.5" />} label="Needs you" value={k.attention} tone={k.attention ? "text-warn" : "text-ok"} sub={k.attention ? "waiting for your decision" : "you are all caught up"} />
        <Kpi icon={<Clock className="size-3.5" />} label="In progress" value={k.in_progress} sub="plans and checks under way" to={x.sees.decisions ? "/approvals" : undefined} />
        <Kpi icon={<CheckCircle2 className="size-3.5" />} label="Completed" value={k.completed} sub={k.value ? <>worth {money(k.value)}, last 30 days</> : "last 30 days"} to={x.sees.decisions ? "/approvals" : undefined} />
        <Kpi icon={<AlertTriangle className="size-3.5" />} label="Exceptions" value={k.exceptions} tone={k.exceptions ? "text-bad" : undefined} sub="blocked or failed, 30 days" />
        <Kpi icon={<Zap className="size-3.5" />} label="Handled automatically" value={k.auto_rate === null ? "-" : `${k.auto_rate}%`} sub={k.decisions ? `of ${k.decisions} action(s); rules passed ${k.pass_rate}%` : "no actions yet"} />
        {x.usage ? <Kpi icon={<Gauge className="size-3.5" />} label="AI usage" value={x.usage.calls} sub={x.usage.calls ? `model calls, ${money(x.usage.tokens)} tokens` : "model calls, last 30 days"} to="/settings/usage" />
          : <Kpi icon={<Gauge className="size-3.5" />} label="Your conversations" value={x.mine.conversations} sub="with the agent team" to="/history" />}
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.25fr_1fr] [&>*]:min-w-0">
        <Card>
          <CardHead title="Needs your attention" sub="Approvals, plans and suggestions that wait for you. Nothing runs until a person decides." />
          {x.attention.length === 0 ? (
            <div className="flex items-center gap-3 px-5 py-6 text-[13.5px] text-muted"><CheckCircle2 className="size-5 text-ok" />Nothing is waiting for you. The team asks here when a change needs your approval.</div>
          ) : (
            <ul className="divide-y divide-line">{x.attention.map((a: any, i: number) => (
              <li key={i}>
                <Link to={a.to} className="flex items-start gap-3 px-5 py-3 hover:bg-panel2/60">
                  <Badge tone={a.tone} className="mt-0.5 shrink-0">{a.kind}</Badge>
                  <span className="min-w-0 flex-1"><span className="block truncate text-[13.5px] font-medium">{a.title}</span>
                    <span className="block truncate text-xs text-muted">{a.detail}</span></span>
                  <span className="shrink-0 text-xs text-faint">{fmtDate(a.at)}</span>
                </Link>
              </li>))}</ul>
          )}
        </Card>

        <Card>
          <CardHead title="Your AI workforce" sub={`${k.team} agents, ${k.active_agents} active in the last 30 days.`}
            right={can("blueprint:view") && <Link to="/studio?layer=swarm" className="text-xs font-medium text-accent">How work flows</Link>} />
          <ul className="divide-y divide-line">{x.team.map((g: any) => (
            <li key={g.id} className="flex items-center gap-3 px-5 py-2.5">
              <span className={cx("size-2 shrink-0 rounded-full", g.status === "active" ? "bg-ok" : g.status === "recent" ? "bg-accent" : "bg-line2")} aria-hidden />
              <span className="min-w-0 flex-1"><span className="block truncate text-[13.5px] font-medium">{g.name}{g.kind === "specialist" && <span className="ml-1.5 text-xs font-normal text-faint">specialist</span>}</span>
                <span className="block truncate text-xs text-muted">{g.role}</span></span>
              <span className="shrink-0 text-right"><span className="block text-[13px] font-medium">{g.work}</span><span className="block text-[11px] text-faint">{ago(g.last)}</span></span>
            </li>))}</ul>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.25fr_1fr] [&>*]:min-w-0">
        <ActivityChart series={x.series} />
        <Card>
          <CardHead title="Outcomes delivered" sub="Approved actions carried out in the last 30 days." />
          {x.outcomes.length === 0 ? <p className="px-5 py-5 text-[13.5px] text-muted">No completed actions in the last 30 days.</p> : (
            <ul className="divide-y divide-line">{x.outcomes.map((o: any) => (
              <li key={o.action} className="flex items-center gap-3 px-5 py-2.5 text-[13px]">
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{o.action}</span>
                <span className="text-muted">{o.count} time{o.count > 1 ? "s" : ""}</span>
                {o.amount > 0 && <span className="w-20 text-right font-medium">{money(o.amount)}</span>}
              </li>))}</ul>
          )}
          {x.goals.length > 0 && (
            <div className="border-t border-line px-5 py-3">
              <div className="mb-1.5 text-xs font-medium text-faint">Goals the team works towards</div>
              <div className="flex flex-wrap gap-1.5">{x.goals.map((g: any) => <Badge key={g.name} tone="accent">{g.name}</Badge>)}</div>
            </div>
          )}
        </Card>
      </div>

      <Card className="mt-5">
        <CardHead title="Recent activity" sub="The latest five things the agents did."
          right={<Link to="/history" className="flex items-center gap-1 text-[13px] font-medium text-accent">View all<ArrowRight className="size-3.5" /></Link>} />
        {x.feed.length === 0 ? <p className="px-5 py-5 text-[13.5px] text-muted">Nothing yet. Ask {p.name} something to get started.</p> : (
          <ul className="divide-y divide-line">{x.feed.slice(0, 5).map((f: any, i: number) => {
            const st = STATE[f.state] || { label: String(f.state).replace(/_/g, " ").toLowerCase(), tone: "neutral" as const };
            const row = (
              <>
                <span className="w-28 shrink-0 text-xs text-faint">{fmtDate(f.at)}</span>
                <span className="min-w-0 flex-1"><span className="block truncate text-[13.5px]">{f.text}</span><span className="block truncate text-xs text-muted">{f.who}</span></span>
                <Badge tone={st.tone} className="shrink-0">{st.label}</Badge>
              </>
            );
            return <li key={i}>{f.to ? <Link to={f.to} className="flex items-center gap-3 px-5 py-2.5 hover:bg-panel2/60">{row}</Link> : <div className="flex items-center gap-3 px-5 py-2.5">{row}</div>}</li>;
          })}</ul>
        )}
      </Card>
    </>
  );
}
