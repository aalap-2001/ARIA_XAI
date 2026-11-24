import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BrainCircuit, ChevronRight, CheckCircle2, Circle, KeyRound, Sparkles, Users } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card, Loading, cx, useAsync } from "../components/ui";

export type Step = { done: boolean; title: string; text: string; to: string; icon: ReactNode; perm: string };

/** The go-live steps for this business, only those the person's role can act on. */
export function useSetup() {
  const { can } = useAuth();
  const setup = useAsync<any>(() => api("/api/setup"));
  const s = setup.data;
  const steps: Step[] = !s ? [] : [
    { done: s.described || s.documents > 0 || s.connections > 0, title: "Tell Aria XAI about your product", text: "Describe it, upload documents, connect data.", to: "/understand", icon: <Sparkles className="size-4" />, perm: "blueprint:view" },
    { done: !!s.blueprint.published, title: "Review and publish the blueprint", text: "Approve the agent team, rules and approval policies Aria XAI proposes.", to: "/blueprint", icon: <BrainCircuit className="size-4" />, perm: "blueprint:view" },
    { done: s.members > 1, title: "Invite your team", text: "Give people roles: builders, reviewers, operators, or your own.", to: "/settings/users", icon: <Users className="size-4" />, perm: "users:view" },
    { done: s.api_keys > 0, title: "Put the agents in your product", text: "Use the API or drop the chat widget into your app.", to: "/settings/api", icon: <KeyRound className="size-4" />, perm: "api_keys:view" },
  ].filter((x) => can(x.perm));
  return { loading: setup.loading, steps, done: steps.filter((x) => x.done).length };
}

/** The go-live checklist, shown on the Organisation page. */
export function SetupChecklist() {
  const { loading, steps, done } = useSetup();
  const [show, setShow] = useState<boolean | null>(null);
  if (loading) return <Loading />;
  if (!steps.length) return null;
  const open = show ?? done < steps.length; // finished setups fold to one line
  return (
    <>
      <Card>
        <button type="button" onClick={() => setShow(!open)} aria-expanded={open}
          className={cx("flex w-full items-center justify-between gap-4 px-5 py-4 text-left", open && "border-b border-line")}>
          <div className="flex items-center gap-2"><ChevronRight className={cx("size-4 text-faint transition-transform", open && "rotate-90")} />
            <div><div className="font-semibold">Go-live setup</div><div className="text-[13px] text-muted">{done === steps.length ? "Everything is set up." : `${done} of ${steps.length} done`}</div></div></div>
          <div className="h-2 w-40 overflow-hidden rounded-full bg-panel2"><div className="h-full bg-accent transition-all" style={{ width: `${steps.length ? (done / steps.length) * 100 : 0}%` }} /></div>
        </button>
        {open && <ul className="divide-y divide-line">
          {steps.map((x) => (
            <li key={x.title}>
              <Link to={x.to} className="flex items-center gap-4 px-5 py-4 hover:bg-panel2/60">
                {x.done ? <CheckCircle2 className="size-5 text-ok" /> : <Circle className="size-5 text-line2" />}
                <div className="grid size-8 place-items-center rounded-lg bg-panel2 text-muted">{x.icon}</div>
                <div className="min-w-0 flex-1"><div className={cx("font-medium", x.done && "text-muted line-through decoration-1")}>{x.title}</div><div className="text-[13px] text-muted">{x.text}</div></div>
                <ArrowRight className="size-4 text-faint" />
              </Link>
            </li>
          ))}
        </ul>}
      </Card>
    </>
  );
}
