CREATE TABLE IF NOT EXISTS ewu_lab.students (
  student_id text PRIMARY KEY CHECK (student_id ~ '^[A-Z0-9][A-Z0-9-]{0,39}$'),
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE ewu_lab.students ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE ewu_lab.students FROM PUBLIC, anon, authenticated;
