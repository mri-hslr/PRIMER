from __future__ import annotations

from flask import Blueprint, jsonify, request

from config import P_G, P_S, GROQ_MODEL
from core.data import load_interactions
from core.bkt import predict_correct
from core.state import (
    get_current_mastery,
    update_current_mastery,
    record_answer,
    recent_responses,
    reset_state,
)
from core.policy import choose_action, is_mastered, next_skill
from core.questions import get_current_question, set_current_question, reset_questions
from core.llm import ask_llm_for_feedback_and_question, fallback_response, client

api_bp = Blueprint("api", __name__)


@api_bp.get("/api/students")
def students():
    ids = sorted({row["student_id"] for row in load_interactions()})
    return jsonify(ids)


@api_bp.get("/api/state")
def state():
    student_id = request.args.get("student_id", "S1")
    skill = request.args.get("skill", "addition")

    mastery = get_current_mastery(student_id, skill)
    recent = recent_responses(student_id, skill)

    action, difficulty = choose_action(mastery, recent)
    question = get_current_question(student_id, skill, difficulty)

    return jsonify({
        "student_id": student_id,
        "skill": skill,
        "mastery": round(mastery, 4),
        "predicted_p_correct": round(predict_correct(mastery, P_G, P_S), 4),
        "action": action,
        "difficulty": difficulty,
        "question": question["question"],
        "correct_answer": question["answer"],
        "history_length": len(recent),
        "llm_configured": client is not None,
    })


@api_bp.post("/api/answer")
def answer():
    payload = request.get_json(silent=True) or {}

    student_id = payload.get("student_id", "S1")
    skill = payload.get("skill", "addition")
    current_question = str(payload.get("question", "")).strip()
    student_answer = str(payload.get("answer", "")).strip()
    correct_answer = str(payload.get("correct_answer", "")).strip()

    if not student_answer:
        return jsonify({"error": "Please enter an answer."}), 400

    was_correct = int(student_answer.lower() == correct_answer.lower())

    mastery_before, mastery_after = update_current_mastery(student_id, skill, was_correct)

    record_answer(student_id, skill, {
        "question": current_question,
        "student_answer": student_answer,
        "correct_answer": correct_answer,
        "correct": was_correct,
        "mastery_before": mastery_before,
        "mastery_after": mastery_after,
    })

    recent = recent_responses(student_id, skill)
    action, difficulty = choose_action(mastery_after, recent)
    mastered = is_mastered(mastery_after, recent)

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

    set_current_question(student_id, skill, {
        "question": llm_result["next_question"],
        "answer": llm_result["next_answer"],
        "skill": skill,
        "difficulty": difficulty,
    })

    return jsonify({
        "correct": bool(was_correct),
        "mastery_before": round(mastery_before, 4),
        "mastery_after": round(mastery_after, 4),
        "predicted_p_correct_next": round(predict_correct(mastery_after, P_G, P_S), 4),
        "action": action,
        "difficulty": difficulty,
        "feedback": llm_result["feedback"],
        "next_question": llm_result["next_question"],
        "next_answer": llm_result["next_answer"],
        "next_skill": next_skill(skill) if mastered else None,
        "mastered": mastered,
        "llm_used": llm_used,
        "llm_error": llm_error,
        "history_length": len(recent),
    })


@api_bp.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}

    student_id = payload.get("student_id", "S1")
    skill = payload.get("skill", "addition")
    message = str(payload.get("message", "")).strip()

    if not message:
        return jsonify({"error": "message is required"}), 400

    mastery = get_current_mastery(student_id, skill)
    recent = recent_responses(student_id, skill)
    action, difficulty = choose_action(mastery, recent)

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


@api_bp.post("/api/reset")
def reset():
    reset_state()
    reset_questions()
    return jsonify({"status": "reset"})