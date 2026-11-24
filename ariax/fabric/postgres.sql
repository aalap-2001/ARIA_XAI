-- Production enforcement for the Knowledge Fabric on Postgres (§05).
-- The reference build uses SQLite with session-scoped views; on Postgres the same guarantee is
-- enforced by row-level security, so the application login cannot read base tables at all.

CREATE ROLE fabric_app LOGIN;
REVOKE ALL ON facts, episodes, receipts, provenance FROM fabric_app;
GRANT SELECT, INSERT ON facts, episodes, receipts, provenance TO fabric_app;
GRANT UPDATE (invalidated_at, superseded_by, value) ON facts TO fabric_app;  -- invalidate / forget only

ALTER TABLE facts    ENABLE ROW LEVEL SECURITY;  ALTER TABLE facts    FORCE ROW LEVEL SECURITY;
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;  ALTER TABLE episodes FORCE ROW LEVEL SECURITY;
ALTER TABLE receipts ENABLE ROW LEVEL SECURITY;  ALTER TABLE receipts FORCE ROW LEVEL SECURITY;

-- A query with no declared identity is valid SQL, raises no error, and returns zero rows.
CREATE POLICY tenant_case_scope ON facts USING (
      tenant = current_setting('app.tenant', true)
  AND domain = current_setting('app.domain', true)
  AND entity = ANY (string_to_array(current_setting('app.entities', true), ','))
  AND (case_id IS NULL OR current_setting('app.scope', true) = 'tenant'
       OR case_id = current_setting('app.case', true)));

CREATE POLICY tenant_case_scope ON episodes USING (
      tenant = current_setting('app.tenant', true) AND domain = current_setting('app.domain', true)
  AND (current_setting('app.scope', true) = 'tenant' OR case_id = current_setting('app.case', true)));

CREATE POLICY tenant_case_scope ON receipts USING (
      tenant = current_setting('app.tenant', true) AND domain = current_setting('app.domain', true)
  AND (current_setting('app.scope', true) = 'tenant' OR case_id = current_setting('app.case', true)));

CREATE RULE episodes_append_only AS ON UPDATE TO episodes DO INSTEAD NOTHING;
