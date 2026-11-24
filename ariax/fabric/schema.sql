-- Knowledge Fabric, the four framework tiers. Fixed in every deployment; domains add around them.
--   facts       invalidated, never deleted
--   episodes    append only, never edited (trajectory-shaped: observation, action, actor, outcome)
--   receipts    written at decisions, expire early
--   provenance  written with every fact
-- Four dates on facts: effective_from (world), published_at (source said so), ingested_at (we had it),
-- and as_known_at, a query parameter, never a column.

CREATE TABLE IF NOT EXISTS _provenance (
    id TEXT PRIMARY KEY, source TEXT NOT NULL, locator TEXT, ingest_job TEXT, recorded_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS _facts (
    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, domain TEXT NOT NULL, case_id TEXT,
    entity TEXT NOT NULL, subject TEXT NOT NULL, predicate TEXT NOT NULL, value TEXT,
    effective_from TEXT NOT NULL, effective_to TEXT, published_at TEXT NOT NULL, ingested_at TEXT NOT NULL,
    invalidated_at TEXT, superseded_by TEXT, provenance_id TEXT NOT NULL REFERENCES _provenance(id),
    natural_key TEXT UNIQUE);

CREATE TABLE IF NOT EXISTS _episodes (
    id TEXT PRIMARY KEY, seq INTEGER, tenant TEXT NOT NULL, domain TEXT NOT NULL, case_id TEXT, agent TEXT,
    trace_id TEXT, decision_id TEXT, kind TEXT NOT NULL, observation TEXT, action TEXT, actor TEXT,
    outcome TEXT, data TEXT, at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS _receipts (
    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, domain TEXT NOT NULL, case_id TEXT, agent TEXT,
    trace_id TEXT, decision_id TEXT NOT NULL, shown TEXT, passed_over TEXT, conditions TEXT,
    hash TEXT NOT NULL, at TEXT NOT NULL, expires_at TEXT);

CREATE TABLE IF NOT EXISTS _proposals (
    id TEXT PRIMARY KEY, tenant TEXT, domain TEXT, entity TEXT, subject TEXT, predicate TEXT, value TEXT,
    evidence_count INTEGER, evidence TEXT, gate_outcome TEXT, status TEXT, decided_by TEXT, decided_at TEXT,
    created_at TEXT);

-- Append-only enforcement in the store itself, not in the caller.
CREATE TRIGGER IF NOT EXISTS episodes_no_update BEFORE UPDATE ON _episodes
BEGIN SELECT RAISE(ABORT, 'episodes are append only'); END;
CREATE TRIGGER IF NOT EXISTS episodes_no_delete BEFORE DELETE ON _episodes
BEGIN SELECT RAISE(ABORT, 'episodes are append only'); END;
CREATE TRIGGER IF NOT EXISTS facts_no_delete BEFORE DELETE ON _facts
BEGIN SELECT RAISE(ABORT, 'facts are invalidated, never deleted'); END;

-- Session identity. A row exists only inside the Fabric's own open transaction, so any other
-- connection (a bypass) sees an empty table and every scoped view returns zero rows.
CREATE TABLE IF NOT EXISTS session_ctx (tenant TEXT, domain TEXT, case_id TEXT, scope TEXT, entities TEXT, agent TEXT);

CREATE VIEW IF NOT EXISTS facts AS
SELECT f.* FROM _facts f JOIN session_ctx s
  ON f.tenant = s.tenant AND f.domain = s.domain
 AND instr(',' || s.entities || ',', ',' || f.entity || ',') > 0
 AND (f.case_id IS NULL OR s.scope = 'tenant' OR f.case_id = s.case_id);

CREATE VIEW IF NOT EXISTS episodes AS
SELECT e.* FROM _episodes e JOIN session_ctx s
  ON e.tenant = s.tenant AND e.domain = s.domain AND (s.scope = 'tenant' OR e.case_id = s.case_id);

CREATE VIEW IF NOT EXISTS receipts AS
SELECT r.* FROM _receipts r JOIN session_ctx s
  ON r.tenant = s.tenant AND r.domain = s.domain AND (s.scope = 'tenant' OR r.case_id = s.case_id);
