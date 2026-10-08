from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# PATHS
# ============================================================
APP_DIR = Path(__file__).resolve().parent            # backend/
PROJECT_ROOT = APP_DIR.parent                         # project root
DATA_FILE = PROJECT_ROOT / "data" / "student_interactions.csv"
QUESTIONS_FILE = PROJECT_ROOT / "data" / "questions.json"
FRONTEND_STATIC_DIR = PROJECT_ROOT / "frontend" 
# ============================================================
# BKT PARAMETERS
# ============================================================
P_L0 = 0.30
P_T = 0.20
P_G = 0.20
P_S = 0.10

# ============================================================
# SKILL PROGRESSION
# ============================================================
SKILL_ORDER = ["addition", "subtraction"]

# ============================================================
# GROQ / LLM CONFIG
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")