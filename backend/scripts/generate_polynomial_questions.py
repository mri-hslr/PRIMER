import argparse
import os
import random
import sys
from pathlib import Path

import sympy as sp
from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

x = sp.Symbol("x")


def fmt(expr):
    """2*x - 3  ->  '2x - 3'"""
    return sp.sstr(sp.expand(expr)).replace("*", "")


def generate_factor_theorem_question():
    root1, root2 = random.sample(range(-5, 6), 2)   # distinct roots
    c = random.randint(1, 3)
    a_val = random.randint(1, 5)
    b_val = random.randint(-5, 5)

    divisor = sp.expand((x - root1) * (x - root2))
    remainder = a_val * x + b_val
    p = sp.expand(divisor * (x + c) + remainder)

    v1 = int(p.subs(x, root1))
    v2 = int(p.subs(x, root2))

    question_text = (
        f"What linear expression must be subtracted from ${sp.latex(p)}$ "
        f"so that it is exactly divisible by ${sp.latex(divisor)}$?"
    )

    solution_steps = [
        f"Let p(x) = {sp.latex(p)}.",
        "If we subtract the remainder r(x) = ax + b, the new polynomial is divisible by the divisor.",
        f"The divisor has roots x = {root1} and x = {root2}, so r(x) must equal p(x) at both roots.",
        f"p({root1}) = {v1} and p({root2}) = {v2}.",
        f"So a({root1}) + b = {v1} and a({root2}) + b = {v2}.",
        f"Solving the two equations gives a = {a_val} and b = {b_val}, so r(x) = {fmt(remainder)}.",
    ]

    return {
        "concept_id": "poly.division.addition_subtraction",
        "prerequisites": ["poly.division.remainder_theorem", "alg.simultaneous_equations"],
        "difficulty": 85,
        "question_type": "algebraic",
        "cognitive_level": "analyse",
        "question_text": question_text,
        "answer": fmt(remainder),
        "answer_format": "algebraic_expr",
        "solution_steps": Jsonb(solution_steps),
        "common_mistakes": Jsonb(
            {"ax-b": "Incorrect sign handling when setting up the remainder equation."}
        ),
        "source_type": "script_generated",
    }


INSERT_SQL = """
    INSERT INTO polynomial_questions (
        concept_id, prerequisites, difficulty, question_type,
        cognitive_level, question_text, answer, answer_format,
        solution_steps, common_mistakes, source_type
    ) VALUES (
        %(concept_id)s, %(prerequisites)s::text[], %(difficulty)s, %(question_type)s,
        %(cognitive_level)s, %(question_text)s, %(answer)s, %(answer_format)s,
        %(solution_steps)s, %(common_mistakes)s, %(source_type)s
    )
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1, help="how many questions to generate")
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("ERROR: DATABASE_URL is missing. Check your .env file.")

    inserted = skipped = 0
    try:
        with psycopg.connect(url, connect_timeout=30) as conn:   # commits on success, rolls back on error
            for _ in range(args.count):
                q = generate_factor_theorem_question()
                exists = conn.execute(
                    "SELECT 1 FROM polynomial_questions WHERE question_text = %s",
                    (q["question_text"],),
                ).fetchone()
                if exists:
                    skipped += 1
                    continue
                conn.execute(INSERT_SQL, q)
                inserted += 1
    except Exception as e:
        sys.exit(f"Database error ({type(e).__name__}): {str(e).splitlines()[0]}")

    print(f"Inserted: {inserted}   Skipped (duplicates): {skipped}")


if __name__ == "__main__":
    main()