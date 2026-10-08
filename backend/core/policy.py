from __future__ import annotations

from typing import List, Optional, Tuple

from config import SKILL_ORDER

"""
Small interpretable policy. These thresholds are prototype decisions,
not validated educational thresholds.
"""


def choose_action(
    mastery: float,
    recent: Optional[List[int]] = None,
) -> Tuple[str, str]:
    recent = recent or []

    if mastery < 0.40:
        return "TEACH / REMEDIATE", "easy"

    if mastery < 0.70:
        return "PRACTICE", "easy"

    if mastery < 0.85:
        return "PRACTICE", "medium"

    if recent and recent[-1] == 0:
        return "REVIEW / CHECK UNDERSTANDING", "medium"

    if len(recent) >= 2 and recent[-2:] == [1, 1]:
        return "MASTERED / ADVANCE", "hard"

    return "PRACTICE / CONFIRM MASTERY", "medium"


def is_mastered(mastery: float, recent: List[int]) -> bool:
    return (
        mastery >= 0.85
        and len(recent) >= 2
        and recent[-2:] == [1, 1]
    )


def next_skill(current_skill: str) -> Optional[str]:
    try:
        idx = SKILL_ORDER.index(current_skill)
        return SKILL_ORDER[idx + 1] if idx + 1 < len(SKILL_ORDER) else None
    except ValueError:
        return None