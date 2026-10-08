from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from flask import Flask, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from groq import Groq
except ImportError:
    Groq = None


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR.parent / "data" / "student_interactions.csv"

app = Flask(__name__, static_folder="static", static_url_path="")

# ============================================================
# BKT PARAMETERS
# ============================================================
P_L0 = 0.30
P_T = 0.20
P_G = 0.20
P_S = 0.10


# ============================================================
# DEMO SESSION STATE
# ============================================================
# CSV = historical evidence
# SESSION_STATE = current learner state in this demo session
SESSION_STATE: Dict[Tuple[str, str], float] = {}
SESSION_HISTORY: Dict[Tuple[str, str], List[dict]] = {}

# Current question shown to the user.
CURRENT_QUESTION: Dict[Tuple[str, str], dict] = {}

# Used to cycle through local questions.
QUESTION_INDEX: Dict[Tuple[str, str, str], int] = {}


# ============================================================
# GROQ CLIENT (native groq package, free tier, no card required)
# ============================================================
# "llama-3.3-70b-versatile" is NOT available on this account (confirmed
# via client.models.list() during setup — Groq's hosted lineup changes
# over time, so don't trust a hardcoded name from docs/memory).
# "openai/gpt-oss-20b" was confirmed working for this key.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

client = (
    Groq(api_key=GROQ_API_KEY)
    if (GROQ_API_KEY and Groq)
    else None
)


# ============================================================
# QUESTION BANK
# ============================================================
QUESTION_BANK = {
    "addition": {
        "easy": [
            ("3 + 4 = ?", "7"),
            ("5 + 2 = ?", "7"),
            ("6 + 3 = ?", "9"),
            ("8 + 1 = ?", "9"),
        ],
        "medium": [
            ("14 + 8 = ?", "22"),
            ("17 + 6 = ?", "23"),
            ("24 + 9 = ?", "33"),
            ("26 + 17 = ?", "43"),
        ],
        "hard": [
            ("38 + 27 = ?", "65"),
            ("46 + 39 = ?", "85"),
            ("57 + 28 = ?", "85"),
            ("68 + 27 = ?", "95"),
        ],
    },
    "subtraction": {
        "easy": [
            ("8 - 3 = ?", "5"),
            ("10 - 4 = ?", "6"),
            ("12 - 7 = ?", "5"),
            ("9 - 2 = ?", "7"),
        ],
        "medium": [
            ("17 - 9 = ?", "8"),
            ("23 - 8 = ?", "15"),
            ("31 - 14 = ?", "17"),
            ("42 - 19 = ?", "23"),
        ],
        "hard": [
            ("52 - 27 = ?", "25"),
            ("74 - 38 = ?", "36"),
            ("91 - 47 = ?", "44"),
            ("83 - 29 = ?", "54"),
        ],
    },
}

SKILL_ORDER = ["addition", "subtraction"]


# ============================================================
# DATA HELPERS
# ============================================================
def load_interactions() -> List[dict]:
    with DATA_FILE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ============================================================
# BKT
# ============================================================
def bkt_update(p_knowledge: float, response: int) -> float:
    """
    One standard BKT update:
    1) update belief using the observed response
    2) apply learning transition
    """

    if response == 1:
        p_correct_given_knowledge = 1 - P_S
        p_correct_given_not_knowledge = P_G

        p_correct = (
            p_knowledge * p_correct_given_knowledge
            + (1 - p_knowledge) * p_correct_given_not_knowledge
        )

        p_after_observation = (
            p_knowledge * p_correct_given_knowledge
        ) / p_correct

    elif response == 0:
        p_wrong_given_knowledge = P_S
        p_wrong_given_not_knowledge = 1 - P_G

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
        + (1 - p_after_observation) * P_T
    )


def historical_mastery(student_id: str, skill: str) -> float:
    """Calculate starting mastery from CSV history."""
    mastery = P_L0

    for row in load_interactions():
        if row["student_id"] == student_id and row["skill"] == skill:
            mastery = bkt_update(mastery, int(row["response"]))

    return mastery


def get_current_mastery(student_id: str, skill: str) -> float:
    """Initialise from CSV once, then continue from session state."""
    key = (student_id, skill)

    if key not in SESSION_STATE:
        SESSION_STATE[key] = historical_mastery(student_id, skill)
        SESSION_HISTORY[key] = []

    return SESSION_STATE[key]


def update_current_mastery(
    student_id: str,
    skill: str,
    response: int
) -> Tuple[float, float]:
    key = (student_id, skill)

    before = get_current_mastery(student_id, skill)
    after = bkt_update(before, response)

    SESSION_STATE[key] = after
    return before, after


def predict_correct(p_knowledge: float) -> float:
    """Probability that the NEXT answer will be correct."""
    return (
        p_knowledge * (1 - P_S)
        + (1 - p_knowledge) * P_G
    )


# ============================================================
# ADAPTIVE POLICY
# ============================================================
def choose_action(
    mastery: float,
    recent_responses: List[int] | None = None
) -> Tuple[str, str]:
    """
    Small interpretable policy.

    These thresholds are prototype decisions, not universal
    educational thresholds.
    """
    recent_responses = recent_responses or []

    if mastery < 0.40:
        return "TEACH / REMEDIATE", "easy"

    if mastery < 0.70:
        return "PRACTICE", "easy"

    if mastery < 0.85:
        return "PRACTICE", "medium"

    # If mastery is high but the latest response was wrong,
    # review before advancing.
    if recent_responses and recent_responses[-1] == 0:
        return "REVIEW / CHECK UNDERSTANDING", "medium"

    # Require two recent successes before calling the skill mastered.
    if len(recent_responses) >= 2 and recent_responses[-2:] == [1, 1]:
        return "MASTERED / ADVANCE", "hard"

    return "PRACTICE / CONFIRM MASTERY", "medium"


def is_mastered(
    mastery: float,
    recent_responses: List[int]
) -> bool:
    return (
        mastery >= 0.85
        and len(recent_responses) >= 2
        and recent_responses[-2:] == [1, 1]
    )


def next_skill(current_skill: str) -> str | None:
    try:
        idx = SKILL_ORDER.index(current_skill)
        return (
            SKILL_ORDER[idx + 1]
            if idx + 1 < len(SKILL_ORDER)
            else None
        )
    except ValueError:
        return None


# ============================================================
# QUESTION MANAGEMENT
# ============================================================
def local_question(student_id: str, skill: str, difficulty: str) -> dict:
    """
    Return a different question from the local bank each time.
    """
    key = (student_id, skill, difficulty)

    skill_bank = QUESTION_BANK.get(
        skill,
        QUESTION_BANK["addition"]
    )

    questions = skill_bank.get(
        difficulty,
        skill_bank["easy"]
    )

    index = QUESTION_INDEX.get(key, 0)
    question, answer = questions[index % len(questions)]
    QUESTION_INDEX[key] = index + 1

    return {
        "question": question,
        "answer": answer,
        "skill": skill,
        "difficulty": difficulty,
    }


def get_current_question(
    student_id: str,
    skill: str,
    difficulty: str
) -> dict:
    key = (student_id, skill)

    existing = CURRENT_QUESTION.get(key)

    if existing and existing["difficulty"] == difficulty:
        return existing

    q = local_question(student_id, skill, difficulty)
    CURRENT_QUESTION[key] = q
    return q


# ============================================================
# JSON / LLM HELPERS
# ============================================================
def parse_json_output(text: str) -> dict | None:
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(value, dict):
        return None

    return value


def ask_llm_for_feedback_and_question(
    student_id: str,
    skill: str,
    current_question: str,
    student_answer: str,
    correct_answer: str,
    was_correct: bool,
    mastery_before: float,
    mastery_after: float,
    action: str,
    difficulty: str,
) -> Tuple[dict | None, str | None]:
    """
    Returns:
        (LLM result, error type)

    result is None when the real API call failed.
    """
    if client is None:
        return None, "LLM_NOT_CONFIGURED"

    instructions = f"""
You are the communication layer of an adaptive educational tutor for a young learner.

The application has already computed the learner state and next action.
You must NOT change, override, or invent those values.

Student: {student_id}
Skill: {skill}
Mastery before answer: {mastery_before:.2f}
Mastery after answer: {mastery_after:.2f}
Adaptive action: {action}
Target difficulty: {difficulty}

Current question:
{current_question}

Student answer:
{student_answer}

Correct answer:
{correct_answer}

Was the answer correct?
{was_correct}

Rules:

1. If the answer is correct:
   - appreciate the learner briefly,
   - mention the correct reasoning when useful,
   - give a NEW question at the target difficulty.

2. If the answer is wrong:
   - do not shame the learner,
   - explain the mistake or likely gap simply,
   - provide a short hint or explanation,
   - give a NEW question at the target difficulty.

3. Only explicitly say the learner has mastered the skill if
   the action is "MASTERED / ADVANCE".

4. Return ONLY valid JSON with exactly these keys:
{{
  "feedback": "string",
  "next_question": "string",
  "next_answer": "string"
}}
"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": "Generate the tutoring response now."},
            ],
        )

        parsed = parse_json_output(response.choices[0].message.content)

        if parsed and all(
            k in parsed
            for k in ["feedback", "next_question", "next_answer"]
        ):
            return parsed, None

        return None, "INVALID_LLM_OUTPUT"

    except Exception as exc:
        return None, type(exc).__name__


def fallback_response(
    student_id: str,
    skill: str,
    current_question: str,
    student_answer: str,
    correct_answer: str,
    was_correct: bool,
    mastery_after: float,
    action: str,
    difficulty: str,
) -> dict:
    """
    Local fallback. It still behaves adaptively when the LLM API is unavailable.
    """
    if was_correct:
        if action == "MASTERED / ADVANCE":
            feedback = (
                f"Excellent work! You got {current_question} right. "
                f"Your estimated mastery of {skill} is {mastery_after:.0%}. "
                "You have demonstrated mastery of this skill. "
                "Let's move forward."
            )
        else:
            feedback = (
                f"Nice work! {current_question} is correct. "
                f"Your estimated mastery is now {mastery_after:.0%}. "
                f"Let's continue with a {difficulty} {skill} problem."
            )
    else:
        feedback = (
            f"Not quite. You answered {student_answer}, but the correct answer "
            f"is {correct_answer}. Let's review the idea and try another "
            f"{difficulty} {skill} problem. Your mistake gives the learner "
            "model useful evidence about what needs more practice."
        )

    q = local_question(student_id, skill, difficulty)

    return {
        "feedback": feedback,
        "next_question": q["question"],
        "next_answer": q["answer"],
    }


# ============================================================
# ROUTES
# ============================================================
@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/students")
def students():
    ids = sorted({
        row["student_id"]
        for row in load_interactions()
    })
    return jsonify(ids)


@app.get("/api/state")
def state():
    student_id = request.args.get("student_id", "S1")
    skill = request.args.get("skill", "addition")

    mastery = get_current_mastery(student_id, skill)
    recent = [
        item["correct"]
        for item in SESSION_HISTORY[(student_id, skill)]
    ]

    action, difficulty = choose_action(mastery, recent)
    question = get_current_question(
        student_id,
        skill,
        difficulty
    )

    return jsonify({
        "student_id": student_id,
        "skill": skill,
        "mastery": round(mastery, 4),
        "predicted_p_correct": round(
            predict_correct(mastery), 4
        ),
        "action": action,
        "difficulty": difficulty,
        "question": question["question"],
        "correct_answer": question["answer"],
        "history_length": len(recent),
        "llm_configured": client is not None,
    })


@app.post("/api/answer")
def answer():
    payload = request.get_json(silent=True) or {}

    student_id = payload.get("student_id", "S1")
    skill = payload.get("skill", "addition")
    current_question = str(
        payload.get("question", "")
    ).strip()
    student_answer = str(
        payload.get("answer", "")
    ).strip()
    correct_answer = str(
        payload.get("correct_answer", "")
    ).strip()

    if not student_answer:
        return jsonify({
            "error": "Please enter an answer."
        }), 400

    was_correct = int(
        student_answer.lower() == correct_answer.lower()
    )

    mastery_before, mastery_after = update_current_mastery(
        student_id,
        skill,
        was_correct
    )

    key = (student_id, skill)
    SESSION_HISTORY[key].append({
        "question": current_question,
        "student_answer": student_answer,
        "correct_answer": correct_answer,
        "correct": was_correct,
        "mastery_before": mastery_before,
        "mastery_after": mastery_after,
    })

    recent = [x["correct"] for x in SESSION_HISTORY[key]]

    action, difficulty = choose_action(
        mastery_after,
        recent
    )

    mastered = is_mastered(
        mastery_after,
        recent
    )

    llm_result, llm_error = ask_llm_for_feedback_and_question(
        student_id=student_id,
        skill=skill,
        current_question=current_question,
        student_answer=student_answer,
        correct_answer=correct_answer,
        was_correct=bool(was_correct),
        mastery_before=mastery_before,
        mastery_after=mastery_after,
        action=action,
        difficulty=difficulty,
    )

    llm_used = llm_result is not None

    if llm_result is None:
        llm_result = fallback_response(
            student_id=student_id,
            skill=skill,
            current_question=current_question,
            student_answer=student_answer,
            correct_answer=correct_answer,
            was_correct=bool(was_correct),
            mastery_after=mastery_after,
            action=action,
            difficulty=difficulty,
        )

    # IMPORTANT:
    # The next question returned here becomes the CURRENT question.
    CURRENT_QUESTION[key] = {
        "question": llm_result["next_question"],
        "answer": llm_result["next_answer"],
        "skill": skill,
        "difficulty": difficulty,
    }

    return jsonify({
        "correct": bool(was_correct),
        "mastery_before": round(mastery_before, 4),
        "mastery_after": round(mastery_after, 4),
        "predicted_p_correct_next": round(
            predict_correct(mastery_after), 4
        ),
        "action": action,
        "difficulty": difficulty,
        "feedback": llm_result["feedback"],
        "next_question": llm_result["next_question"],
        "next_answer": llm_result["next_answer"],
        "next_skill": (
            next_skill(skill)
            if mastered
            else None
        ),
        "mastered": mastered,
        "llm_used": llm_used,
        "llm_error": llm_error,
        "history_length": len(recent),
    })


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}

    student_id = payload.get("student_id", "S1")
    skill = payload.get("skill", "addition")
    message = str(
        payload.get("message", "")
    ).strip()

    if not message:
        return jsonify({
            "error": "message is required"
        }), 400

    mastery = get_current_mastery(student_id, skill)
    recent = [
        x["correct"]
        for x in SESSION_HISTORY[(student_id, skill)]
    ]
    action, difficulty = choose_action(
        mastery,
        recent
    )

    if client is None:
        return jsonify({
            "reply": (
                "The LLM is not configured. "
                f"Current estimated {skill} mastery is {mastery:.0%}. "
                f"The adaptive action is {action}."
            ),
            "mastery": round(mastery, 4),
            "action": action,
            "difficulty": difficulty,
            "llm_used": False,
            "llm_error": "LLM_NOT_CONFIGURED",
        })

    instructions = f"""
You are the conversational layer of an adaptive tutor.

Application-controlled learner state:
skill = {skill}
mastery = {mastery:.2f}
adaptive action = {action}
difficulty = {difficulty}

Answer the learner's message simply and supportively.
Do not invent or change the mastery value.
"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": message},
            ],
        )

        return jsonify({
            "reply": response.choices[0].message.content,
            "mastery": round(mastery, 4),
            "action": action,
            "difficulty": difficulty,
            "llm_used": True,
            "llm_error": None,
        })

    except Exception as exc:
        return jsonify({
            "reply": (
                "The LLM request failed, but the learner model is still "
                f"working. Current estimated {skill} mastery is {mastery:.0%} "
                f"and the adaptive action is {action}."
            ),
            "mastery": round(mastery, 4),
            "action": action,
            "difficulty": difficulty,
            "llm_used": False,
            "llm_error": type(exc).__name__,
        })


@app.post("/api/reset")
def reset():
    SESSION_STATE.clear()
    SESSION_HISTORY.clear()
    CURRENT_QUESTION.clear()
    QUESTION_INDEX.clear()

    return jsonify({"status": "reset"})


if __name__ == "__main__":
    app.run(debug=True)