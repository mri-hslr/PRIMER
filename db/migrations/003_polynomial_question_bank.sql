-- 003: polynomial_questions becomes the only question bank

-- Table already exists in Neon (created manually); this makes the repo able to rebuild it.
CREATE TABLE IF NOT EXISTS polynomial_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id VARCHAR(255) NOT NULL,
    prerequisites TEXT[] NOT NULL,
    difficulty INTEGER NOT NULL,
    question_type VARCHAR(50) NOT NULL,
    cognitive_level VARCHAR(50) NOT NULL,
    question_text TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_format VARCHAR(50) NOT NULL,
    solution_steps JSONB NOT NULL,
    common_mistakes JSONB NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_polyq_concept_difficulty
  ON polynomial_questions(concept_id, difficulty);

-- Remove the old addition/subtraction seed data and the old question bank.
DELETE FROM bkt_parameters
  WHERE skill_id IN (SELECT id FROM skills WHERE name IN ('addition', 'subtraction'));
DELETE FROM skills WHERE name IN ('addition', 'subtraction');
DROP TABLE IF EXISTS questions;

-- skills.name now holds the concept_id
INSERT INTO skills (name, sort_order)
VALUES ('poly.division.addition_subtraction', 1)
ON CONFLICT (name) DO NOTHING;

INSERT INTO bkt_parameters (skill_id, p_l0, p_t, p_g, p_s, source, is_active)
SELECT s.id, 0.30, 0.20, 0.20, 0.10, 'manual', TRUE
FROM skills s
WHERE s.name = 'poly.division.addition_subtraction'
  AND NOT EXISTS (SELECT 1 FROM bkt_parameters b WHERE b.skill_id = s.id);

-- interactions: numeric difficulty + link to the question that was answered
ALTER TABLE interactions DROP CONSTRAINT IF EXISTS interactions_difficulty_check;
ALTER TABLE interactions ALTER COLUMN difficulty TYPE INTEGER USING NULL;
ALTER TABLE interactions
  ADD COLUMN IF NOT EXISTS question_id UUID REFERENCES polynomial_questions(id);
CREATE INDEX IF NOT EXISTS idx_interactions_question ON interactions(question_id);