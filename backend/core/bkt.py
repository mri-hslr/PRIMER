from __future__ import annotations

"""
Pure BKT math. No I/O, no globals, no session state here.

Every function takes p_t/p_g/p_s explicitly instead of reading them
from config. This is deliberate: once you fit P(L0)/P(T)/P(G)/P(S)
per skill (or per student) instead of one fixed set for everything,
these functions must already accept different numbers without being
rewritten.
"""


def bkt_update(
    p_knowledge: float,
    response: int,
    p_t: float,
    p_g: float,
    p_s: float,
) -> float:
    """
    One standard BKT update:
    1) revise belief using the observed response (Bayes' rule)
    2) apply the learning transition
    """
    if response == 1:
        p_correct_given_knowledge = 1 - p_s
        p_correct_given_not_knowledge = p_g

        p_correct = (
            p_knowledge * p_correct_given_knowledge
            + (1 - p_knowledge) * p_correct_given_not_knowledge
        )

        p_after_observation = (
            p_knowledge * p_correct_given_knowledge
        ) / p_correct

    elif response == 0:
        p_wrong_given_knowledge = p_s
        p_wrong_given_not_knowledge = 1 - p_g

        p_wrong = (
            p_knowledge * p_wrong_given_knowledge
            + (1 - p_knowledge) * p_wrong_given_not_knowledge
        )

        p_after_observation = (
            p_knowledge * p_wrong_given_knowledge
        ) / p_wrong

    else:
        raise ValueError("response must be 0 or 1")

    return (
        p_after_observation
        + (1 - p_after_observation) * p_t
    )


def predict_correct(p_knowledge: float, p_g: float, p_s: float) -> float:
    """Probability that the NEXT answer will be correct."""
    return (
        p_knowledge * (1 - p_s)
        + (1 - p_knowledge) * p_g
    )