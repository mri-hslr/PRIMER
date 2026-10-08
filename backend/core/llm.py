from __future__ import annotations

import json
from typing import Optional, Tuple

try:
    from groq import Groq
except ImportError:
    Groq = None

from config import GROQ_API_KEY, GROQ_MODEL
from core.questions import local_question

client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq) else None


def parse_json_output(text: str) -> Optional[dict]:
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None

    return value if isinstance(value, dict) else None


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
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Returns (result, error_type). result is None when the real API
    call failed, produced invalid JSON, or the client isn't configured.
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

        if parsed and all(k in parsed for k in ["feedback", "next_question", "next_answer"]):
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
    """Local, rule-based fallback so the loop still works without the LLM."""
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