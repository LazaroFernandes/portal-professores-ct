CREATE TABLE IF NOT EXISTS portal_gym_visits (
 id BIGSERIAL PRIMARY KEY, event_key TEXT NOT NULL UNIQUE,
 client_id TEXT NOT NULL, student_name TEXT NOT NULL, entered_at TEXT NOT NULL,
 finished_at TEXT, finished_by TEXT, professor TEXT, student_shift TEXT,
 training_id BIGINT, training_name TEXT, training_session INTEGER,
 training_total_sessions INTEGER, training_weekly_frequency INTEGER,
 training_usage_baseline INTEGER, training_usage_current INTEGER,
 workout_finished_at TEXT, student_lookup_error TEXT, training_error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS portal_gym_visits_client_day ON portal_gym_visits(client_id, left(entered_at, 10));
CREATE INDEX IF NOT EXISTS portal_gym_visits_day ON portal_gym_visits(entered_at);
CREATE INDEX IF NOT EXISTS portal_gym_visits_client ON portal_gym_visits(client_id, entered_at);
CREATE TABLE IF NOT EXISTS portal_gym_presence_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS portal_daily_attendance_records (
 id BIGSERIAL PRIMARY KEY, visit_id BIGINT NOT NULL UNIQUE REFERENCES portal_gym_visits(id),
 client_id TEXT NOT NULL, professor TEXT NOT NULL, attendance_date TEXT NOT NULL,
 performance TEXT NOT NULL, had_pain INTEGER NOT NULL DEFAULT 0,
 pain_description TEXT NOT NULL DEFAULT '', observation TEXT NOT NULL DEFAULT '',
 evolution TEXT NOT NULL DEFAULT '', finalized_by TEXT NOT NULL,
 finalized_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
