CREATE TABLE IF NOT EXISTS tasks (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    subject TEXT NOT NULL DEFAULT 'General',
    description TEXT NOT NULL DEFAULT '',
    due_date TEXT,
    estimated_minutes INTEGER NOT NULL DEFAULT 30 CHECK (estimated_minutes > 0),
    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS tasks_due_date_idx ON tasks (due_date);
CREATE INDEX IF NOT EXISTS tasks_completed_idx ON tasks (completed);
CREATE INDEX IF NOT EXISTS tasks_status_due_id_idx ON tasks (completed, due_date, id DESC);
