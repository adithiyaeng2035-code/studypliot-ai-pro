CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

CREATE TABLE IF NOT EXISTS study_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    subject TEXT NOT NULL DEFAULT 'General',
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 1 AND 240),
    notes TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS study_sessions_completed_at_idx
    ON study_sessions (completed_at DESC, id DESC);
