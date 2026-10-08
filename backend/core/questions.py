from __future__ import annotations

import json
from typing import Dict, Tuple

from config import QUESTIONS_FILE

QUESTION_INDEX: Dict[Tuple[str, str, str], int] = {}
CURRENT_QUESTION: Dict[Tuple[str, str], dict] = {}


def load_question_bank() -> dict:
    with QUESTIONS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


QUESTION_BANK = load_question_bank()


def local_question(student_id: str, skill: str, difficulty: str) -> dict:
    """Return a different question from the bank each time it's called."""
    key = (student_id, skill, difficulty)

    skill_bank = QUESTION_BANK.get(skill, QUESTION_BANK["addition"])
    questions = skill_bank.get(difficulty, skill_bank["easy"])

    index = QUESTION_INDEX.get(key, 0)
    item = questions[index % len(questions)]
    QUESTION_INDEX[key] = index + 1

    return {
        "question": item["question"],
        "answer": item["answer"],
        "skill": skill,
        "difficulty": difficulty,
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
    QUESTION_INDEX.clear()
    CURRENT_QUESTION.clear()