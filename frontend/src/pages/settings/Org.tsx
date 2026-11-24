import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { SetupChecklist } from "../Setup";
import { Button, Card, CardHead, Field, Input, Loading, PageHead, Secret, useAsync, useToast } from "../../components/ui";

export default function Org() {
  const { can, refresh } = useAuth();
  const toast = useToast();
  const org = useAsync<any>(() => api("/api/org"));
  const [name, setName] = useState("");
  const [secret, setSecret] = useState<string>("");
  useEffect(() => { if (org.data) setName(org.data.name); }, [org.data]);
  useEffect(() => { if (can("org:edit")) api("/api/webhook-secret").then((r) => setSecret(r.secret)).catch(() => {}); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    try { await api("/api/org", { method: "PATCH", body: { name } }); toast("Saved"); refresh(); } catch (e: any) { toast(e.message, "bad"); }
  };
  if (org.loading) return <Loading />;
  const ed = can("org:edit");
  return (
    <>
      <PageHead title="Organisation" sub={`Created ${fmtDate(org.data.created_at)} · ${org.data.id}`} />
      <div className="mb-5"><SetupChecklist /></div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card><CardHead title="General" />
          <div className="space-y-4 p-5">
            <Field label="Organisation name"><Input value={name} disabled={!ed} onChange={(e) => setName(e.target.value)} /></Field>
            {can("blueprint:view") && <p className="text-[13px] text-muted">Guardrails, data redaction and the kill switch are in the <Link to="/studio?layer=governance" className="font-medium text-accent">Studio, Governance Sentinel</Link>.</p>}
            {ed && <Button variant="primary" onClick={save}>Save</Button>}
          </div>
        </Card>
        {ed && (
          <Card><CardHead title="Webhook signing secret" sub="Approved actions are POSTed to your webhooks with header X-AriaX-Signature: sha256=HMAC(body, secret). Verify it before acting." />
            <div className="space-y-3 p-5">
              <Secret value={secret} onReveal={async () => (await api("/api/webhook-secret?reveal=true")).secret} />
              <Button variant="danger" size="sm" onClick={async () => { if (!confirm("Rotate the secret? Existing webhook receivers must be updated.")) return; await api("/api/webhook-secret/rotate", { method: "POST" }); setSecret((await api("/api/webhook-secret")).secret); toast("Secret rotated"); }}>Rotate secret</Button>
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
