import { useState } from "react";
import { UserPlus } from "lucide-react";
import { api, fmtDate } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Alert, Badge, Button, Card, CardHead, ErrorBox, Field, Input, Loading, Modal, PageHead, Secret, Select, useAsync, useToast } from "../../components/ui";

export default function Users() {
  const { can } = useAuth();
  const toast = useToast();
  const users = useAsync<any>(() => api("/api/users"));
  const roles = useAsync<any[]>(() => api("/api/roles"));
  const [inviting, setInviting] = useState(false);
  const [form, setForm] = useState({ email: "", role_id: "" });
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const invite = async () => {
    setBusy(true);
    try { const r = await api("/api/users/invite", { body: form }); setLink(r.invite_url); users.reload(); } catch (e: any) { toast(e.message, "bad"); } finally { setBusy(false); }
  };
  const update = async (id: string, body: any) => { try { await api(`/api/users/${id}`, { method: "PATCH", body }); toast("Updated"); users.reload(); } catch (e: any) { toast(e.message, "bad"); } };
  const revoke = async (id: string) => { await api(`/api/invites/${id}`, { method: "DELETE" }); users.reload(); };

  if (users.loading || roles.loading) return <Loading />;
  if (users.error) return <ErrorBox error={users.error} />;
  return (
    <>
      <PageHead title="Users" sub="Everyone in your organisation and the role that decides what they can see and do."
        right={can("users:create") && <Button variant="primary" icon={<UserPlus className="size-4" />} onClick={() => { setForm({ email: "", role_id: roles.data!.find((r) => r.name === "Operator")?.id || "" }); setLink(null); setInviting(true); }}>Invite user</Button>} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-5 py-2.5">Person</th><th>Role</th><th>Status</th><th>Last sign-in</th><th /></tr></thead>
          <tbody>
            {users.data.members.map((m: any) => (
              <tr key={m.id} className="border-b border-line last:border-0">
                <td className="px-5 py-3"><div className="font-medium">{m.name} {m.you && <Badge tone="accent">you</Badge>}</div><div className="text-xs text-muted">{m.email}</div></td>
                <td>{can("users:edit") && !m.you ? (
                  <Select value={m.role_id} onChange={(e) => update(m.id, { role_id: e.target.value })} className="w-44">{roles.data!.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>
                ) : m.role}</td>
                <td><Badge tone={m.status === "active" ? "ok" : "neutral"}>{m.status}</Badge></td>
                <td className="text-xs text-muted">{fmtDate(m.last_login_at)}</td>
                <td className="pr-5 text-right">{can("users:edit") && !m.you && (
                  <Button size="sm" variant={m.status === "active" ? "danger" : "secondary"} onClick={() => update(m.id, { status: m.status === "active" ? "deactivated" : "active" })}>{m.status === "active" ? "Deactivate" : "Reactivate"}</Button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {users.data.invites.length > 0 && (
        <Card className="mt-5"><CardHead title="Pending invitations" />
          <ul className="divide-y divide-line">{users.data.invites.map((i: any) => (
            <li key={i.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm"><span className="font-medium">{i.email}</span><Badge>{i.role}</Badge>
              {i.expired ? <Badge tone="bad">expired</Badge> : <span className="text-xs text-muted">expires {fmtDate(i.expires_at)}</span>}
              {can("users:delete") && <Button size="sm" variant="ghost" className="ml-auto" onClick={() => revoke(i.id)}>Revoke</Button>}</li>))}</ul>
        </Card>
      )}

      <Modal open={inviting} onClose={() => setInviting(false)} title="Invite a user">
        {link ? (
          <div className="space-y-3">
            <Alert tone="ok" title="Invitation created">Send this link to {form.email}. It works once and expires in 7 days.</Alert>
            <Secret value={link} />
          </div>
        ) : (
          <div className="space-y-4">
            <Field label="Email"><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label="Role" hint={roles.data!.find((r) => r.id === form.role_id)?.description}>
              <Select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>{roles.data!.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>
            </Field>
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setInviting(false)}>Cancel</Button><Button variant="primary" loading={busy} disabled={!form.email || !form.role_id} onClick={invite}>Create invitation</Button></div>
          </div>
        )}
      </Modal>
    </>
  );
}
