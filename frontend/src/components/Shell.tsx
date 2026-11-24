import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Bot, BrainCircuit, ChevronRight, Building2, CheckCheck, Cpu, Database, Eye, Gauge, History, Home, KeyRound, Layers, LogOut, Menu, Moon, Network, OctagonX, ScrollText, Shield, ShieldCheck, Smile, Sparkles, Sun, Target, Users as UsersIcon } from "lucide-react";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { CountBadge, cx } from "./ui";

type Item = { to: string; label: string; icon: ReactNode; perm?: string; badge?: number; count?: number };
type Exp = "work" | "build" | "control";

export default function Shell({ children }: { children: ReactNode }) {
  const { me, can, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(0);
  const [watch, setWatch] = useState<number | null>(null);
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark") ||
    (!document.documentElement.classList.contains("light") && matchMedia("(prefers-color-scheme: dark)").matches));

  useEffect(() => { setOpen(false); }, [loc.pathname]);
  useEffect(() => {
    try { const t = localStorage.getItem("ariax-theme"); if (t) { document.documentElement.classList.add(t); setDark(t === "dark"); } } catch { /* storage blocked */ }
  }, []);
  useEffect(() => {
    if (!can("approvals:view")) return;
    const load = () => {
      api<any[]>("/api/decisions?status=PENDING_REVIEW&mine=true").then((d) => setPending(d.length)).catch(() => {});
      api<any[]>("/api/suggestions?status=pending").then((s) => setWatch(s.filter((x) => x.can_decide).length)).catch(() => setWatch(null));
    };
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [loc.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleTheme = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(next);
    try { localStorage.setItem("ariax-theme", next); } catch { /* ignore */ }
    setDark(!dark);
  };

  // Three experiences, as in the information architecture: people use AI in the Workspace, builders shape it in the Build
  // Studio, admins run it from the Control Centre. Each shows only the pages the person's role allows.
  const L = (id: string) => `/studio?layer=${id}`;
  const all: { id: Exp; label: string; sections: { title: string; items: Item[] }[] }[] = [
    { id: "work", label: "Workspace", sections: [{ title: "", items: [
      { to: "/", label: "Overview", icon: <Home className="size-4" />, perm: "chat:use" },
      { to: "/chat", label: "Workplace", icon: <Bot className="size-4" />, perm: "chat:use" },
      { to: "/approvals", label: "Tasks and approvals", icon: <CheckCheck className="size-4" />, perm: "approvals:view", badge: pending },
      ...(watch === null ? [] : [{ to: "/activity", label: "Aria Watch suggestions", icon: <Eye className="size-4" />, perm: "approvals:view", count: watch }]),
      { to: "/history", label: "Activity", icon: <History className="size-4" />, perm: "chat:use" },
    ] }] },
    { id: "build", label: "Build Studio", sections: [
      { title: "", items: [
        { to: "/studio", label: "Studio", icon: <Layers className="size-4" />, perm: "blueprint:view" },
        { to: "/understand", label: "Understand my product", icon: <Sparkles className="size-4" />, perm: "blueprint:view" },
        { to: "/blueprint", label: "Blueprint and releases", icon: <BrainCircuit className="size-4" />, perm: "blueprint:view" },
      ] },
      { title: "Framework layers", items: [
        { to: L("cognitive"), label: "Cognitive Core", icon: <Cpu className="size-4" />, perm: "blueprint:view" },
        { to: L("motivation"), label: "Motivation Engine", icon: <Target className="size-4" />, perm: "blueprint:view" },
        { to: L("knowledge"), label: "Knowledge Fabric", icon: <Database className="size-4" />, perm: "blueprint:view" },
        { to: L("swarm"), label: "Swarm Orchestrator", icon: <Network className="size-4" />, perm: "blueprint:view" },
        { to: L("interface"), label: "Anthropomorphic Interface", icon: <Smile className="size-4" />, perm: "blueprint:view" },
        { to: L("governance"), label: "Governance Sentinel", icon: <ShieldCheck className="size-4" />, perm: "blueprint:view" },
      ] },
    ] },
    { id: "control", label: "Control Centre", sections: [
      { title: "Organisation", items: [
        { to: "/settings/org", label: "Organisation", icon: <Building2 className="size-4" />, perm: "org:view" },
        { to: "/settings/users", label: "Users", icon: <UsersIcon className="size-4" />, perm: "users:view" },
        { to: "/settings/roles", label: "Roles and access", icon: <Shield className="size-4" />, perm: "roles:view" },
      ] },
      { title: "Integrations", items: [
        { to: "/settings/api", label: "API and widget", icon: <KeyRound className="size-4" />, perm: "api_keys:view" },
      ] },
      { title: "Governance", items: [
        { to: "/audit", label: "Audit log", icon: <ScrollText className="size-4" />, perm: "audit:view" },
        { to: "/settings/usage", label: "Usage", icon: <Gauge className="size-4" />, perm: "usage:view" },
      ] },
    ] },
  ];
  const experiences = all.map((x) => ({ ...x, sections: x.sections.map((s) => ({ ...s, items: s.items.filter((i) => !i.perm || can(i.perm)) }))
    .filter((s) => s.items.length) })).filter((x) => x.sections.length);
  type X = (typeof experiences)[number];

  const here = loc.pathname, layer = new URLSearchParams(loc.search).get("layer");
  const matches = (to: string) => {
    const [path, q] = to.split("?");
    const want = q ? new URLSearchParams(q).get("layer") : null;
    const onPath = path === "/" ? here === "/" : here === path || here.startsWith(path + "/");
    return onPath && (want ? want === layer : !(path === "/studio" && layer));
  };
  // Every area the person may use is in one vertical menu, open by default; a heading folds its group and the choice is remembered.
  const [folded, setFolded] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem("ariax-menu") || "{}"); } catch { return {}; } });
  const fold = (id: string) => {
    const next = { ...folded, [id]: !folded[id] };
    setFolded(next);
    try { localStorage.setItem("ariax-menu", JSON.stringify(next)); } catch { /* storage blocked */ }
  };
  const holds = (x: X) => x.sections.some((sec) => sec.items.some((i) => matches(i.to)));

  const [mini, setMini] = useState(() => { try { return localStorage.getItem("ariax-rail") === "1"; } catch { return false; } });
  const [wide, setWide] = useState(() => matchMedia("(min-width: 1024px)").matches);
  useEffect(() => { const q = matchMedia("(min-width: 1024px)"); const f = () => setWide(q.matches); q.addEventListener("change", f); return () => q.removeEventListener("change", f); }, []);
  const rail = mini && wide;
  const toggleRail = () => { const n = !mini; setMini(n); setOrgsOpen(false); try { localStorage.setItem("ariax-rail", n ? "1" : "0"); } catch { /* storage blocked */ } };
  const initials = (n = "") => n.replace(" (demo)", "").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  // the businesses this person belongs to, newest first (the six vertical demos come before the older ones)
  const [switching, setSwitching] = useState("");
  const [orgsOpen, setOrgsOpen] = useState(false);
  const day = (o: { created?: string }) => (o.created || "").slice(0, 10);
  const orgs = [...(me?.orgs || [])].sort((x, y) => (x.industry ? 0 : 1) - (y.industry ? 0 : 1) || day(y).localeCompare(day(x)));
  const switchOrg = async (id: string) => {
    setSwitching(id);
    try { await api("/api/auth/switch", { body: { org_id: id } }); window.location.assign("/"); } catch { setSwitching(""); }
  };

  return (
    <div className="flex h-full">
      {open && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={cx("fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-panel transition-[transform,width] lg:static lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full", rail && "lg:w-16")}>
        <div className={cx("flex items-center gap-2 pb-2 pt-3", rail ? "justify-center px-2" : "pl-5 pr-3")}>
          {!rail && <span className="flex-1 text-[17px] font-semibold tracking-tight">Aria XAI</span>}
          <button onClick={toggleRail} className="hidden rounded-md p-1.5 text-muted hover:bg-panel2 hover:text-fg lg:block"
            aria-label={rail ? "Expand menu" : "Collapse menu"} aria-expanded={!rail} title={rail ? "Expand menu" : "Collapse menu"}><Menu className="size-5" /></button>
        </div>
        {rail ? (
          <div className="flex justify-center pb-2">
            <button onClick={toggleRail} title={`${me?.org.name}. Expand the menu to switch business.`} aria-label="Current business"
              className="grid size-9 place-items-center rounded-lg border border-line text-[11px] font-semibold text-accent hover:border-line2">{initials(me?.org.name)}</button>
          </div>
        ) : (
        <div className="px-3 pb-2">
          <button type="button" disabled={orgs.length < 2} onClick={() => setOrgsOpen(!orgsOpen)} aria-expanded={orgs.length > 1 ? orgsOpen : undefined}
            className={cx("flex w-full items-center gap-2 rounded-lg border border-line px-3 py-2 text-left", orgs.length > 1 && "hover:border-line2")}>
            <span className="min-w-0 flex-1">
              <span className="block text-[11px] text-faint">Business{orgs.length > 1 && `, ${orgs.length} available`}</span>
              <span className="block truncate text-sm font-medium">{me?.org.name}</span><span className="block text-xs text-muted">{me?.role}</span>
            </span>
            {orgs.length > 1 && <ChevronRight className={cx("size-4 shrink-0 text-faint transition-transform", orgsOpen && "rotate-90")} />}
          </button>
          {orgsOpen && (
            <div className="mt-1 max-h-72 overflow-y-auto scroll-thin" role="list">
              {orgs.filter((o) => o.id !== me?.org.id).map((o) => (
                <button key={o.id} role="listitem" disabled={switching !== ""} onClick={() => switchOrg(o.id)}
                  className={cx("block w-full rounded-md px-3 py-1.5 text-left hover:bg-panel2", switching === o.id && "opacity-60")}>
                  <span className="block truncate text-[12.5px] text-fg">{o.name.replace(" (demo)", "")}</span>
                  <span className="block truncate text-[11px] text-muted">{o.industry ? o.industry.replace(/ \(.*\)$/, "") : "Setting up"}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        )}
        <nav className={cx("flex-1 overflow-y-auto pb-3 scroll-thin", rail ? "px-2" : "px-3")} aria-label="Main">
          {experiences.map((x) => {
            const shut = !!folded[x.id] && !holds(x);
            return (
              <div key={x.id} className="mt-3 first:mt-1">
                {rail ? <div className="mx-2 my-2 border-t border-line" title={x.label} /> : experiences.length > 1 && (
                  <button onClick={() => fold(x.id)} aria-expanded={!shut}
                    className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[12px] font-semibold text-fg/80 hover:bg-panel2">
                    <ChevronRight className={cx("size-3.5 text-faint transition-transform", !shut && "rotate-90")} />{x.label}
                  </button>
                )}
                {(rail || !shut) && x.sections.map((sec) => (
                  <div key={sec.title || "main"} className={!rail && experiences.length > 1 ? "ml-2 border-l border-line pl-1.5" : ""}>
                    {sec.title && !rail && <div className="px-2 pb-0.5 pt-2 text-[11px] font-medium text-faint">{sec.title}</div>}
                    {sec.items.map((i) => {
                      const on = matches(i.to);
                      return (
                        <Link key={i.to} to={i.to} aria-current={on ? "page" : undefined} title={rail ? i.label : undefined} aria-label={rail ? i.label : undefined}
                          className={cx("relative flex items-center gap-2.5 rounded-lg text-[13.5px]", rail ? "justify-center px-0 py-2" : "px-2.5 py-1.5",
                            on ? "bg-accentsoft font-medium text-accent" : "text-muted hover:bg-panel2 hover:text-fg")}>
                          {i.icon}{!rail && <span className="flex-1 truncate">{i.label}</span>}
                          {!rail && !!i.badge && <CountBadge n={i.badge} />}
                          {!rail && i.count !== undefined && <CountBadge n={i.count} />}
                          {rail && (!!i.badge || !!i.count) && <span className="absolute right-1.5 top-1 size-2 rounded-full bg-bad" aria-hidden />}
                        </Link>
                      );
                    })}
                  </div>
                ))}
              </div>
            );
          })}
        </nav>
        <div className={cx("border-t border-line", rail ? "px-2 py-3" : "p-3")}>
          <div className={cx("flex items-center gap-2.5", rail && "flex-col gap-1")}>
            <div className="grid size-8 place-items-center rounded-full bg-panel2 text-xs font-semibold" title={rail ? `${me?.user.name}, ${me?.user.email}` : undefined}>{me?.user.name.slice(0, 2).toUpperCase()}</div>
            {!rail && <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{me?.user.name}</div><div className="truncate text-xs text-muted">{me?.user.email}</div></div>}
            <button onClick={toggleTheme} className="rounded-md p-1.5 text-muted hover:bg-panel2" title="Toggle theme" aria-label="Toggle theme">{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}</button>
            <button onClick={async () => { await logout(); nav("/login"); }} className="rounded-md p-1.5 text-muted hover:bg-panel2" title="Sign out" aria-label="Sign out"><LogOut className="size-4" /></button>
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 items-center gap-3 border-b border-line bg-panel px-4 lg:hidden">
          <button onClick={() => setOpen(true)} className="rounded-md p-1.5 hover:bg-panel2" aria-label="Menu"><Menu className="size-5" /></button>
          <span className="font-semibold">Aria XAI</span>
        </header>
        {me?.org.kill_switch && (
          <div role="alert" className="flex flex-wrap items-center gap-2 bg-bad px-4 py-2 text-[13px] text-white">
            <OctagonX className="size-4" /><b>Kill switch is on.</b> Medium and high risk actions are halted.
            {me.org.kill_switch.reason && <span className="opacity-90">Reason: {me.org.kill_switch.reason}</span>}
            <span className="opacity-80">Turned on by {me.org.kill_switch.by}.</span>
            {can("org:edit") && <NavLink to="/studio?layer=governance" className="ml-auto underline">Manage</NavLink>}
          </div>
        )}
        <main className="min-w-0 flex-1 overflow-y-auto scroll-thin">
          <div className="mx-auto max-w-[1280px] p-4 sm:p-5 lg:px-7 lg:py-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
