from __future__ import annotations

from typing import Optional

from psycopg.rows import dict_row

from core.db import connection

_PICK_SQL = """
    SELECT id::text AS id, concept_id, difficulty, question_text, answer
    FROM polynomial_questions
    WHERE concept_id = %s
      AND (%s::uuid IS NULL OR id <> %s::uuid)
    ORDER BY ABS(difficulty - %s), random()
    LIMIT 1
"""


def pick_question(
    concept_id: str,
    target_difficulty: int,
    exclude_id: Optional[str] = None,
) -> Optional[dict]:
    """Question closest to the target difficulty, avoiding exclude_id when possible."""
    with connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_PICK_SQL, (concept_id, exclude_id, exclude_id, target_difficulty))
        row = cur.fetchone()
        if row is None and exclude_id is not None:   # only one question exists: allow a repeat
            cur.execute(_PICK_SQL, (concept_id, None, None, target_difficulty))
            row = cur.fetchone()
    return row