import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")  # a DATABASE_URL already set in the shell takes priority

url = os.getenv("DATABASE_URL")
if not url:
    sys.exit("ERROR: DATABASE_URL is missing.")

files = sorted((ROOT / "db" / "migrations").glob("*.sql"))

with psycopg.connect(url, connect_timeout=30) as conn:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "filename TEXT PRIMARY KEY, "
        "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    conn.commit()
    done = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
    for f in files:
        if f.name in done:
            print(f"skip     {f.name}")
            continue
        try:
            conn.execute(f.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (f.name,))
            conn.commit()
            print(f"applied  {f.name}")
        except Exception as e:
            conn.rollback()
            sys.exit(f"FAILED   {f.name}: {str(e).splitlines()[0]}")
print("Done.")