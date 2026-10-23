-- Additive: original visits, daily and weekly records are retained.
CREATE TABLE IF NOT EXISTS portal_daily_details (
 visit_id BIGINT PRIMARY KEY REFERENCES portal_gym_visits(id),
 payload TEXT NOT NULL, version INTEGER NOT NULL,
 actor TEXT NOT NULL, actor_role TEXT NOT NULL, professor_at_record TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portal_followup_actions (
 id TEXT PRIMARY KEY, visit_id BIGINT NOT NULL UNIQUE REFERENCES portal_gym_visits(id),
 client_id TEXT NOT NULL, title TEXT NOT NULL, assigned_to TEXT NOT NULL,
 due_date TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
 priority TEXT NOT NULL DEFAULT 'normal', instruction TEXT NOT NULL DEFAULT '',
 result TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS portal_followup_client ON portal_followup_actions(client_id, status);
CREATE TABLE IF NOT EXISTS portal_daily_audit (
 id TEXT PRIMARY KEY, entity TEXT NOT NULL, entity_id TEXT NOT NULL,
 actor TEXT NOT NULL, actor_role TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS portal_daily_audit_entity ON portal_daily_audit(entity, entity_id, created_at);
