import { useState } from "react";
import { Lock, Plus, Shield, Trash2 } from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Badge, Button, Card, ErrorBox, Field, Input, Loading, Modal, PageHead, Textarea, cx, useAsync, useToast } from "../../components/ui";

type Role = { id: string; name: string; description: string; builtin: boolean; permissions: string[]; scopes: any; members: number; locked: boolean };
type Catalog = { resources: { id: string; label: string; actions: string[] }[]; team: { id: string; name: string; purpose: string }[]; agents: { id: string; name: string }[]; actions: { name: string; risk: string }[]; data: { id: string; name: string; tables: string[] }[] };

export default function Roles() {
  const { can } = useAuth();
  const toast = useToast();
  const roles = useAsync<Role[]>(() => api("/api/roles"));
  const cat = useAsync<Catalog>(() => api("/api/roles/catalog"));
  const [edit, setEdit] = useState<Role | "new" | null>(null);
  const del = async (r: Role) => {
    if (!confirm(`Delete the role "${r.name}"?`)) return;
    try { await api(`/api/roles/${r.id}`, { method: "DELETE" }); toast("Role deleted"); roles.reload(); } catch (e: any) { toast(e.message, "bad"); }
  };
  if (roles.loading || cat.loading) return <Loading />;
  if (roles.error || cat.error) return <ErrorBox error={(roles.error || cat.error)!} />;
  return (
    <>
      <PageHead title="Roles & access" sub="What each role can do (permissions) and what it can reach (agents, data tables, actions and how much it may approve)."
        right={can("roles:create") && <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEdit("new")}>New role</Button>} />
      <div className="grid gap-3 md:grid-cols-2">
        {roles.data!.map((r) => (
          <Card key={r.id} className="flex flex-col p-5">
            <div className="flex items-center gap-2"><Shield className="size-4 text-muted" /><b>{r.name}</b>{r.builtin && <Badge>built in</Badge>}<span className="ml-auto text-xs text-muted">{r.members} member(s)</span></div>
            <p className="mt-1 text-[13px] text-muted">{r.description || "-"}</p>
            <div className="mt-3 text-xs text-muted">{r.permissions.includes("*") ? "Full access" : `${r.permissions.length} permission(s)`} ·
              {" "}approval limit {r.scopes?.approval_limit == null ? "unlimited" : r.scopes.approval_limit} · agents {(r.scopes?.agents || []).includes("*") ? "all" : (r.scopes?.agents || []).length}</div>
            <div className="mt-4 flex gap-2">
              {r.locked ? <span className="inline-flex items-center gap-1 text-xs text-faint"><Lock className="size-3" /> Owner always has full access</span> : can("roles:edit") && <Button size="sm" onClick={() => setEdit(r)}>Configure</Button>}
              {!r.builtin && can("roles:delete") && <Button size="sm" variant="danger" icon={<Trash2 className="size-3.5" />} onClick={() => del(r)}>Delete</Button>}
            </div>
          </Card>
        ))}
      </div>
      {edit && <RoleEditor role={edit === "new" ? null : edit} cat={cat.data!} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); roles.reload(); }} />}
    </>
  );
}

function RoleEditor({ role, cat, onClose, onSaved }: { role: Role | null; cat: Catalog; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(role?.name || "");
  const [desc, setDesc] = useState(role?.description || "");
  const [perms, setPerms] = useState<string[]>(role?.permissions || ["chat:use"]);
  const s = role?.scopes || { agents: ["*"], data: { "*": ["*"] }, actions: ["*"], approval_limit: 0 };
  const [agents, setAgents] = useState<string[]>(s.agents || []);
  const [actions, setActions] = useState<string[]>(s.actions || []);
  const [data, setData] = useState<Record<string, string[]>>(s.data || {});
  const [limit, setLimit] = useState<string>(s.approval_limit == null ? "" : String(s.approval_limit));
  const [busy, setBusy] = useState(false);

  const has = (p: string) => perms.includes(p) || perms.includes("*");
  const togglePerm = (p: string) => setPerms(has(p) ? perms.filter((x) => x !== p && x !== "*") : [...perms, p]);
  const toggleIn = (list: string[], set: (v: string[]) => void, v: string) => set(list.includes(v) ? list.filter((x) => x !== v) : [...list.filter((x) => x !== "*"), v]);
  const allData = data["*"]?.includes("*");
  const tableOn = (cid: string, t: string) => allData || data[cid]?.includes("*") || data[cid]?.includes(t);
  const toggleTable = (cid: string, t: string, tables: string[]) => {
    const cur = allData ? Object.fromEntries(cat.data.map((c) => [c.id, [...c.tables]])) : { ...data };
    const set = new Set(cur[cid]?.includes("*") ? tables : cur[cid] || []);
    set.has(t) ? set.delete(t) : set.add(t);
    cur[cid] = [...set];
    delete cur["*"];
    setData(cur);
  };
  const save = async () => {
    setBusy(true);
    const body = { name, description: desc, permissions: perms, scopes: { agents, actions, data, approval_limit: limit === "" ? null : Number(limit) } };
    try { role ? await api(`/api/roles/${role.id}`, { method: "PATCH", body }) : await api("/api/roles", { body }); toast(role ? "Role updated" : "Role created"); onSaved(); }
    catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); }
  };

  return (
    <Modal open onClose={onClose} wide title={role ? `Configure ${role.name}` : "New role"}>
      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name"><Input value={name} disabled={role?.builtin} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Approval limit" hint="Highest amount this role may approve. Blank = unlimited; 0 = cannot approve amounts.">
            <Input type="number" value={limit} onChange={(e) => setLimit(e.target.value)} /></Field>
        </div>
        <Field label="Description"><Textarea rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>

        <section>
          <h3 className="mb-2 text-sm font-semibold">Permissions</h3>
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full text-[13px]">
              <tbody>{cat.resources.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0">
                  <td className="px-3 py-2 font-medium">{r.label}</td>
                  <td className="px-3 py-2"><div className="flex flex-wrap gap-1.5">{r.actions.map((a) => {
                    const p = `${r.id}:${a}`;
                    return <button key={p} type="button" onClick={() => togglePerm(p)} className={cx("rounded-md border px-2 py-0.5 text-xs", has(p) ? "border-accent bg-accentsoft text-accent" : "border-line text-muted hover:bg-panel2")}>{a}</button>;
                  })}</div></td>
                </tr>))}</tbody>
            </table>
          </div>
        </section>

        <section>
          <h3 className="mb-1 text-sm font-semibold">Agent team</h3>
          <p className="mb-2 text-xs text-muted">Which agents people in this role can work with. Without Aria Orchestrator they cannot use the agent team at all.</p>
          {(() => {
            const allIds = [...cat.team.map((x) => x.id), ...cat.agents.map((x) => x.id)];
            const on = (id: string) => agents.includes("*") || agents.includes(id);
            const flip = (id: string) => toggleIn(agents.includes("*") ? allIds : agents, setAgents, id);
            return (
              <>
                <div className="grid gap-2 sm:grid-cols-2">
                  {cat.team.map((a) => (
                    <button key={a.id} type="button" onClick={() => flip(a.id)}
                      className={cx("rounded-lg border p-2.5 text-left", on(a.id) ? "border-accent bg-accentsoft" : "border-line hover:bg-panel2")}>
                      <div className={cx("text-sm font-medium", on(a.id) && "text-accent")}>{on(a.id) ? "✓ " : ""}{a.name}</div>
                      <div className="text-xs text-muted">{a.purpose}</div>
                    </button>))}
                </div>
                {cat.agents.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5"><span className="self-center text-xs text-muted">Specialists:</span>
                  {cat.agents.map((a) => <Chip key={a.id} on={on(a.id)} onClick={() => flip(a.id)}>{a.name}</Chip>)}</div>}
                <div className="mt-2"><Chip on={agents.includes("*")} onClick={() => setAgents(agents.includes("*") ? [] : ["*"])}>All agents, including future ones</Chip></div>
              </>
            );
          })()}
        </section>

        <section>
          <h3 className="mb-1 text-sm font-semibold">What Aria Executor may do for this role</h3>
          <p className="mb-2 text-xs text-muted">Aria Executor can only propose these actions for people in this role, and anything else is blocked. Amounts above the approval limit go to the action's owner role.</p>
          <div className="flex flex-wrap gap-1.5">
            <Chip on={actions.includes("*")} onClick={() => setActions(actions.includes("*") ? [] : ["*"])}>All actions</Chip>
            {cat.actions.map((a) => <Chip key={a.name} on={actions.includes("*") || actions.includes(a.name)} onClick={() => toggleIn(actions.includes("*") ? cat.actions.map((x) => x.name) : actions, setActions, a.name)}>{a.name}</Chip>)}
          </div>
        </section>

        <section>
          <h3 className="mb-1 text-sm font-semibold">Data this role's agents may read</h3>
          <Chip on={!!allData} onClick={() => setData(allData ? {} : { "*": ["*"] })}>All connected data</Chip>
          <div className="mt-2 space-y-2">{cat.data.map((c) => (
            <div key={c.id} className="rounded-lg border border-line p-2.5"><div className="text-[13px] font-medium">{c.name}</div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">{c.tables.map((t) => <Chip key={t} on={!!tableOn(c.id, t)} onClick={() => toggleTable(c.id, t, c.tables)}>{t}</Chip>)}</div></div>
          ))}</div>
        </section>

        <div className="flex justify-end gap-2 border-t border-line pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={name.trim().length < 2} onClick={save}>Save role</Button></div>
      </div>
    </Modal>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className={cx("rounded-full border px-2.5 py-0.5 text-xs", on ? "border-accent bg-accentsoft text-accent" : "border-line text-muted hover:bg-panel2")}>{children}</button>;
}
