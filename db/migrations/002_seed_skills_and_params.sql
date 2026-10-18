-- 002: starting data (safe to re-run)

INSERT INTO skills (name, sort_order)
VALUES ('addition', 1), ('subtraction', 2)
ON CONFLICT (name) DO NOTHING;

INSERT INTO bkt_parameters (skill_id, p_l0, p_t, p_g, p_s, source, is_active)
SELECT s.id, 0.30, 0.20, 0.20, 0.10, 'manual', TRUE
FROM skills s
WHERE NOT EXISTS (SELECT 1 FROM bkt_parameters b WHERE b.skill_id = s.id);