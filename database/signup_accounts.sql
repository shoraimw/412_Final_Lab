ALTER TABLE ewu_lab.students ADD COLUMN IF NOT EXISTS approved integer NOT NULL DEFAULT 1 CHECK (approved IN (0,1));
CREATE TABLE IF NOT EXISTS ewu_lab.admins (
 username text PRIMARY KEY,
 password_hash text NOT NULL DEFAULT '',
 enabled integer NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
);
ALTER TABLE ewu_lab.admins ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE ewu_lab.admins FROM PUBLIC, anon, authenticated;
INSERT INTO ewu_lab.admins(username) VALUES ('ADMIN') ON CONFLICT (username) DO NOTHING;
INSERT INTO ewu_lab.students(student_id,password_hash,approved) VALUES ('DEMO-STUDENT','',0) ON CONFLICT (student_id) DO NOTHING;
