-- 001: initial schema (matches what is already in Neon; safe to re-run)

CREATE TABLE IF NOT EXISTS users (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  display_name  TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'student'
                CHECK (role IN ('student', 'teacher', 'admin')),
  data_origin   TEXT NOT NULL DEFAULT 'live'
                CHECK (data_origin IN ('live', 'synthetic')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS skills (
  id          SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  sort_order  INT  NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  skill_id       SMALLINT NOT NULL REFERENCES skills(id),
  difficulty     TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
  question_text  TEXT NOT NULL,
  correct_answer TEXT NOT NULL,
  source         TEXT NOT NULL DEFAULT 'bank'
                 CHECK (source IN ('bank', 'generated', 'llm')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bkt_parameters (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  skill_id    SMALLINT NOT NULL REFERENCES skills(id),
  p_l0        DOUBLE PRECISION NOT NULL CHECK (p_l0 BETWEEN 0 AND 1),
  p_t         DOUBLE PRECISION NOT NULL CHECK (p_t  BETWEEN 0 AND 1),
  p_g         DOUBLE PRECISION NOT NULL CHECK (p_g  BETWEEN 0 AND 1),
  p_s         DOUBLE PRECISION NOT NULL CHECK (p_s  BETWEEN 0 AND 1),
  source      TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'fitted')),
  fitted_on_n INT,
  is_active   BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_params_per_skill
  ON bkt_parameters(skill_id) WHERE is_active;

CREATE TABLE IF NOT EXISTS mastery_state (
  user_id    BIGINT   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  skill_id   SMALLINT NOT NULL REFERENCES skills(id),
  p_known    DOUBLE PRECISION NOT NULL CHECK (p_known BETWEEN 0 AND 1),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS interactions (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id             BIGINT   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  skill_id            SMALLINT NOT NULL REFERENCES skills(id),
  question_text       TEXT NOT NULL,
  correct_answer      TEXT NOT NULL,
  student_answer      TEXT NOT NULL,
  response            SMALLINT NOT NULL CHECK (response IN (0, 1)),
  difficulty          TEXT CHECK (difficulty IN ('easy', 'medium', 'hard')),
  predicted_p_correct DOUBLE PRECISION,
  mastery_before      DOUBLE PRECISION,
  mastery_after       DOUBLE PRECISION,
  action              TEXT,
  answered_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_interactions_user_skill_time
  ON interactions(user_id, skill_id, answered_at);

CREATE TABLE IF NOT EXISTS teacher_students (
  teacher_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  student_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (teacher_id, student_id)
);