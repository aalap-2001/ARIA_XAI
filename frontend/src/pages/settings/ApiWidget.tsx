import { useState } from "react";
import { KeyRound, Plus } from "lucide-react";
import { api, fmtDate } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Alert, Badge, Button, Card, CardHead, Copy, Empty, Field, Input, Loading, Modal, PageHead, Secret, Select, useAsync, useToast } from "../../components/ui";

export default function ApiWidget() {
  const { can } = useAuth();
  const toast = useToast();
  const keys = useAsync<any[]>(() => api("/api/api-keys"));
  const roles = useAsync<any[]>(() => api("/api/roles"));
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", kind: "publishable", role_id: "", origins: "" });
  const [created, setCreated] = useState<{ key: string; kind: string } | null>(null);
  const base = window.location.origin;
  const usable = (roles.data || []).filter((r) => !r.permissions.includes("*") && r.permissions.includes("chat:use"));

  const create = async () => {
    try {
      const r = await api("/api/api-keys", { body: { name: form.name, kind: form.kind, role_id: form.role_id, allowed_origins: form.origins.split(/[\s,]+/).filter(Boolean) } });
      setCreated({ key: r.key, kind: form.kind }); keys.reload();
    } catch (e: any) { toast(e.message, "bad"); }
  };
  const revoke = async (id: string) => { if (!confirm("Revoke this key? Apps using it stop working immediately.")) return; await api(`/api/api-keys/${id}`, { method: "DELETE" }); keys.reload(); };

  if (keys.loading || roles.loading) return <Loading />;
  const widget = (k: string) => `<script src="${base}/widget.js" data-key="${k}" data-title="Ask our AI team" data-user="CURRENT_USER_ID" async></script>`;
  const curl = (k: string) => `curl -X POST ${base}/v1/agents/chat \\\n  -H "Authorization: Bearer ${k}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"message": "Hello", "end_user_id": "user-123"}'`;
  return (
    <>
      <PageHead title="API & widget" sub="Put your agent team inside your own product. Every call runs under the key's role, with the same rules, approvals and audit as the console."
        right={can("api_keys:create") && <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => { setCreated(null); setForm({ name: "", kind: "publishable", role_id: usable.find((r) => r.name === "Operator")?.id || usable[0]?.id || "", origins: "" }); setOpen(true); }}>Create key</Button>} />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card><CardHead title="Embed the chat widget" sub="Paste before </body> in your web app. Uses a publishable key locked to your domains." />
          <div className="p-5"><pre className="overflow-x-auto rounded-lg bg-panel2 p-3 text-xs">{widget("ax_pk_…")}</pre></div></Card>
        <Card><CardHead title="Call from your backend" sub="Server-to-server with a secret key. Never ship it to browsers." />
          <div className="p-5"><pre className="overflow-x-auto rounded-lg bg-panel2 p-3 text-xs">{curl("ax_sk_…")}</pre></div></Card>
        <Card className="lg:col-span-2"><CardHead title="Send events to Aria Watch" sub="Report activity from your product (orders, refunds, sign-ups, failures…). Aria Watch checks each event against the blueprint's watch rules and only investigates the ones that matter." />
          <div className="p-5"><pre className="overflow-x-auto rounded-lg bg-panel2 p-3 text-xs">{`curl -X POST ${base}/v1/events \\\n  -H "Authorization: Bearer ax_sk_…" \\\n  -H "Content-Type: application/json" \\\n  -d '{"type": "refund.requested", "entity_id": "order-1002", "data": {"order_id": 1002, "amount": 900}, "actor": {"id": "user-7"}}'`}</pre></div></Card>
      </div>

      <Card className="mt-5"><CardHead title="Keys" />
        {!keys.data!.length ? <div className="p-5"><Empty icon={<KeyRound className="size-7" />} title="No keys yet">Create a publishable key for the widget or a secret key for your servers.</Empty></div> : (
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs text-muted"><th className="px-5 py-2.5">Name</th><th>Type</th><th>Acts as role</th><th>Origins</th><th>Last used</th><th /></tr></thead>
            <tbody>{keys.data!.map((k) => (
              <tr key={k.id} className="border-b border-line last:border-0">
                <td className="px-5 py-3"><div className="font-medium">{k.name}</div><div className="text-xs text-muted">Key hidden</div></td>
                <td><Badge tone={k.kind === "secret" ? "warn" : "info"}>{k.kind}</Badge></td><td>{k.role}</td>
                <td className="text-xs text-muted">{k.allowed_origins.join(", ") || "-"}</td><td className="text-xs text-muted">{fmtDate(k.last_used_at)}</td>
                <td className="pr-5 text-right">{k.revoked ? <Badge>revoked</Badge> : can("api_keys:delete") && <Button size="sm" variant="danger" onClick={() => revoke(k.id)}>Revoke</Button>}</td>
              </tr>))}</tbody></table></div>
        )}
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="Create API key" wide={!!created}>
        {created ? (
          <div className="space-y-3">
            <Alert tone="warn" title="Copy this key now">It is shown only once.</Alert>
            <Secret value={created.key} />
            <div className="text-sm font-medium">{created.kind === "publishable" ? "Widget snippet" : "Example request"}</div>
            <pre className="overflow-x-auto rounded-lg bg-panel2 p-3 text-xs">{created.kind === "publishable" ? widget(created.key.slice(0, 6) + "•".repeat(12)) : curl(created.key.slice(0, 6) + "•".repeat(12))}</pre>
            <p className="text-xs text-muted">The key is hidden in the preview. Copy snippet includes the full key.</p>
            <Copy text={created.kind === "publishable" ? widget(created.key) : curl(created.key)} label="Copy snippet" />
          </div>
        ) : (
          <div className="space-y-4">
            <Field label="Name"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Type"><Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <option value="publishable">Publishable, chat widget in browsers, locked to your domains</option><option value="secret">Secret, server-to-server API</option></Select></Field>
            <Field label="Acts as role" hint="The key can only do what this role allows. Owner is not allowed for keys.">
              <Select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>{usable.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select></Field>
            {form.kind === "publishable" && <Field label="Allowed origins" hint="Space or comma separated, e.g. https://app.example.com"><Input value={form.origins} onChange={(e) => setForm({ ...form, origins: e.target.value })} /></Field>}
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary" disabled={!form.name || !form.role_id || (form.kind === "publishable" && !form.origins.trim())} onClick={create}>Create key</Button></div>
          </div>
        )}
      </Modal>
    </>
  );
}
