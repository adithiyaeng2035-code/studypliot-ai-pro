ALTER TABLE tasks ADD COLUMN recurrence_rule TEXT NOT NULL DEFAULT 'none';
ALTER TABLE tasks ADD COLUMN recurrence_until TEXT;
ALTER TABLE tasks ADD COLUMN recurrence_series_id INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS tasks_recurring_series_due_idx
    ON tasks (recurrence_series_id, due_date)
    WHERE recurrence_series_id IS NOT NULL;
