from __future__ import annotations

from typing import Dict, Tuple

from core.repository import pick_question

# The policy speaks in labels; polynomial_questions stores a number.
# Each label maps to a target number, and the closest stored question is used.
DIFFICULTY_TARGET = {"easy": 30, "medium": 60, "hard": 85}

CURRENT_QUESTION: Dict[Tuple[str, str], dict] = {}


def local_question(student_id: str, skill: str, difficulty: str) -> dict:
    """Pick a question for this skill (concept_id) near the requested difficulty."""
    previous = CURRENT_QUESTION.get((student_id, skill))
    exclude_id = previous.get("question_id") if previous else None

    row = pick_question(skill, DIFFICULTY_TARGET.get(difficulty, 60), exclude_id)
    if row is None:
        raise LookupError(
            f"No questions found in polynomial_questions for concept_id '{skill}'."
        )

    return {
        "question": row["question_text"],
        "answer": row["answer"],
        "skill": skill,
        "difficulty": difficulty,
        "question_id": row["id"],
    }


def get_current_question(student_id: str, skill: str, difficulty: str) -> dict:
    key = (student_id, skill)
    existing = CURRENT_QUESTION.get(key)

    if existing and existing["difficulty"] == difficulty:
        return existing

    q = local_question(student_id, skill, difficulty)
    CURRENT_QUESTION[key] = q
    return q


def set_current_question(student_id: str, skill: str, question: dict) -> None:
    CURRENT_QUESTION[(student_id, skill)] = question


def reset_questions() -> None:
    CURRENT_QUESTION.clear()