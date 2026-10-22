CREATE TABLE IF NOT EXISTS auth_login_attempts (
    fingerprint TEXT NOT NULL,
    attempted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS auth_login_attempts_fingerprint_time_idx
    ON auth_login_attempts (fingerprint, attempted_at);
