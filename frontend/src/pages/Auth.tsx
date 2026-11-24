import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, setCsrf } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Button, Field, Input, Loading, Select } from "../components/ui";

function Frame({ title, sub, children, foot }: { title: string; sub: string; children: ReactNode; foot?: ReactNode }) {
  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-ink p-10 text-white lg:flex">
        <Link to="/" className="text-lg font-semibold tracking-tight">Aria XAI</Link>
        <div>
          <h2 className="max-w-md text-3xl font-semibold leading-tight">Turn any product into a governed team of AI agents.</h2>
          <p className="mt-4 max-w-md text-white/70">Describe your product, upload your documents and connect your data. Aria XAI works out the rest: the agents, the rules and the guardrails, with a human in control.</p>
          <ul className="mt-8 space-y-3 text-sm text-white/80">
            <li>● Neuro-symbolic: the AI proposes, rules and policies decide</li>
            <li>● Roles, approvals and a tamper-evident audit trail from day one</li>
          </ul>
        </div>
        <div className="text-xs text-white/40">© Aria XAI</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-6 block text-lg font-semibold tracking-tight lg:hidden">Aria XAI</Link>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted">{sub}</p>
          <div className="mt-6">{children}</div>
          {foot && <div className="mt-6 text-sm text-muted">{foot}</div>}
        </div>
      </div>
    </div>
  );
}

export function Login() {
  const { refresh } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  // People who belong to more than one business choose which one to open after signing in.
  const [choose, setChoose] = useState<{ current: string; orgs: { id: string; name: string; role: string }[] } | null>(null);
  const [pick, setPick] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api("/api/auth/login", { body: f });
      const me = await api<any>("/api/auth/me");
      setCsrf(me.csrf);
      if (me.orgs.length > 1) { setChoose({ current: me.org.id, orgs: me.orgs }); setPick(me.org.id); return; }
      await refresh(); nav("/");
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  const open = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { if (pick !== choose!.current) await api("/api/auth/switch", { body: { org_id: pick } }); await refresh(); nav("/"); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  if (choose) return (
    <Frame title="Choose a business" sub="You have access to more than one business. Pick the one to open; you can switch later from the sidebar.">
      <form onSubmit={open} className="space-y-4">
        {err && <Alert tone="bad">{err}</Alert>}
        <Field label="Business">
          <Select value={pick} onChange={(e) => setPick(e.target.value)} autoFocus>
            {choose.orgs.map((o) => <option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}
          </Select>
        </Field>
        <Button variant="primary" className="w-full" loading={busy}>Open</Button>
      </form>
    </Frame>
  );
  return (
    <Frame title="Sign in" sub="Welcome back to Aria XAI." foot={<>New to Aria XAI? <Link to="/signup" className="font-medium text-accent">Create an organisation</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        {err && <Alert tone="bad">{err}</Alert>}
        <Field label="Email or username"><Input type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Password"><Input type="password" autoComplete="current-password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
        <Button variant="primary" className="w-full" loading={busy}>Sign in</Button>
      </form>
    </Frame>
  );
}

export function Signup() {
  const { refresh } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ org_name: "", name: "", email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await api("/api/auth/signup", { body: f }); await refresh(); nav("/"); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <Frame title="Create your organisation" sub="You'll be its Owner. Invite your team afterwards."
      foot={<>Already have an account? <Link to="/login" className="font-medium text-accent">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        {err && <Alert tone="bad">{err}</Alert>}
        <Field label="Organisation name"><Input required minLength={2} value={f.org_name} onChange={(e) => setF({ ...f, org_name: e.target.value })} /></Field>
        <Field label="Your name"><Input required autoComplete="name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Work email"><Input type="email" required autoComplete="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Password" hint="At least 10 characters, with upper and lower case letters and a digit.">
          <Input type="password" required autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        </Field>
        <Button variant="primary" className="w-full" loading={busy}>Create organisation</Button>
      </form>
    </Frame>
  );
}

export function Invite() {
  const { token } = useParams();
  const { refresh } = useAuth();
  const nav = useNavigate();
  const [info, setInfo] = useState<any>(null);
  const [err, setErr] = useState("");
  const [f, setF] = useState({ name: "", password: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { api(`/api/invites/${token}`).then(setInfo).catch((e) => setErr(e.message)); }, [token]);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await api(`/api/invites/${token}/accept`, { body: f }); await refresh(); nav("/"); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  if (!info && !err) return <Loading />;
  return (
    <Frame title={info ? `Join ${info.org}` : "Invitation"} sub={info ? `You've been invited as ${info.role}.` : ""}>
      {err && <Alert tone="bad">{err}</Alert>}
      {info && (
        <form onSubmit={submit} className="mt-4 space-y-4">
          <Field label="Email"><Input value={info.email} disabled /></Field>
          {!info.existing_account && <Field label="Your name"><Input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>}
          <Field label={info.existing_account ? "Your existing Aria XAI password" : "Choose a password"} hint={info.existing_account ? undefined : "At least 10 characters, mixed case and a digit."}>
            <Input type="password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
          </Field>
          <Button variant="primary" className="w-full" loading={busy}>Accept invitation</Button>
        </form>
      )}
    </Frame>
  );
}
