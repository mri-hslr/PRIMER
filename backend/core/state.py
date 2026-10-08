from __future__ import annotations

from typing import Dict, List, Tuple

from config import P_L0, P_T, P_G, P_S
from core.bkt import bkt_update
from core.data import load_interactions

# ============================================================
# SESSION STATE
# ============================================================
# CSV = historical evidence (read-only, never mutated here)
# SESSION_STATE = current learner state for this running demo session
SESSION_STATE: Dict[Tuple[str, str], float] = {}
SESSION_HISTORY: Dict[Tuple[str, str], List[dict]] = {}


def historical_mastery(student_id: str, skill: str) -> float:
    """Replay a student's full CSV history to get a starting mastery."""
    mastery = P_L0

    for row in load_interactions():
        if row["student_id"] == student_id and row["skill"] == skill:
            mastery = bkt_update(mastery, int(row["response"]), P_T, P_G, P_S)

    return mastery


def get_current_mastery(student_id: str, skill: str) -> float:
    """Initialise from CSV once, then continue from in-memory session state."""
    key = (student_id, skill)

    if key not in SESSION_STATE:
        SESSION_STATE[key] = historical_mastery(student_id, skill)
        SESSION_HISTORY[key] = []

    return SESSION_STATE[key]


def update_current_mastery(
    student_id: str,
    skill: str,
    response: int,
) -> Tuple[float, float]:
    key = (student_id, skill)

    before = get_current_mastery(student_id, skill)
    after = bkt_update(before, response, P_T, P_G, P_S)

    SESSION_STATE[key] = after
    return before, after


def record_answer(student_id: str, skill: str, entry: dict) -> None:
    key = (student_id, skill)
    SESSION_HISTORY.setdefault(key, []).append(entry)


def recent_responses(student_id: str, skill: str) -> List[int]:
    key = (student_id, skill)
    return [item["correct"] for item in SESSION_HISTORY.get(key, [])]


def reset_state() -> None:
    SESSION_STATE.clear()
    SESSION_HISTORY.clear()