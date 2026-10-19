from __future__ import annotations
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

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
from core.questions import get_current_question, set_current_question, reset_questions, local_question
from core.llm import ask_llm_for_feedback_and_question, fallback_response, client
from core.db import get_pool
from core.auth import generate_token, require_auth
from psycopg.rows import dict_row

api_bp = Blueprint("api", __name__)

def is_math_equivalent(ans1, ans2):
    """Checks algebraic equivalence handling spacing, commutative properties, and unicode."""
    clean1 = str(ans1).replace("−", "-").replace(" ", "").lower()
    clean2 = str(ans2).replace("−", "-").replace(" ", "").lower()

    if clean1 == clean2:
        return True
        
    try:
        transformations = standard_transformations + (implicit_multiplication_application,)
        expr1 = parse_expr(clean1, transformations=transformations)
        expr2 = parse_expr(clean2, transformations=transformations)
        return sp.simplify(expr1 - expr2) == 0
    except Exception:
        return False

@api_bp.post("/api/register")
def register():
    data = request.get_json()
    # Frontend sends 'username', but our DB uses 'email'
    email = data.get("username") 
    password = data.get("password")
    role = data.get("role", "student")

    if not email or not password:
        return jsonify({"error": "Username/Email and password required"}), 400

    hashed_pw = generate_password_hash(password)
    # Generate a display_name since it is NOT NULL in your schema
    display_name = email.split('@')[0] if '@' in email else email
    
    try:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "INSERT INTO users (email, display_name, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
                    (email, display_name, hashed_pw, role)
                )
                new_user = cur.fetchone()
            conn.commit()
        return jsonify({"message": "User created successfully", "user_id": new_user["id"]}), 201
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({"error": "Account with this name/email might already exist"}), 400

@api_bp.post("/api/login")
def login():
    data = request.get_json()
    email = data.get("username")
    password = data.get("password")

    with get_pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Query against the 'email' column
            cur.execute("SELECT id, password_hash, role FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

    if user and check_password_hash(user["password_hash"], password):
        token = generate_token(user["id"], user["role"])
        return jsonify({"token": token, "user_id": user["id"], "role": user["role"]})
    
    return jsonify({"error": "Invalid credentials"}), 401
@api_bp.get("/api/students")
def students():
    ids = sorted({row["student_id"] for row in load_interactions()})
    return jsonify(ids)

@api_bp.get("/api/state")
@require_auth
def state(current_user_id):
    student_id = str(current_user_id)
    skill = request.args.get("skill", "poly.division.addition_subtraction")

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
@require_auth
def answer(current_user_id):
    payload = request.get_json(silent=True) or {}

    student_id = str(current_user_id)
    skill = payload.get("skill", "poly.division.addition_subtraction")
    current_question = str(payload.get("question", "")).strip()
    student_answer = str(payload.get("answer", "")).strip()
    correct_answer = str(payload.get("correct_answer", "")).strip()

    if not student_answer:
        return jsonify({"error": "Please enter an answer."}), 400

    was_correct = int(is_math_equivalent(student_answer, correct_answer))

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

    next_q = local_question(student_id, skill, difficulty)
    
    set_current_question(student_id, skill, {
        "question": next_q["question"],
        "answer": next_q["answer"],
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
        "next_question": next_q["question"],
        "next_answer": next_q["answer"],
        "next_skill": next_skill(skill) if mastered else None,
        "mastered": mastered,
        "llm_used": llm_used,
        "llm_error": llm_error,
        "history_length": len(recent),
    })

@api_bp.post("/api/chat")
@require_auth
def chat(current_user_id):
    payload = request.get_json(silent=True) or {}

    student_id = str(current_user_id)
    skill = payload.get("skill", "poly.division.addition_subtraction")
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
@require_auth
def reset(current_user_id):
    reset_state()
    reset_questions()
    return jsonify({"status": "reset"})