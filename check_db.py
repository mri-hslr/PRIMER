import os
import sys

from dotenv import load_dotenv
import psycopg
from psycopg import sql

load_dotenv()
url = os.getenv("DATABASE_URL")
if not url:
    sys.exit("ERROR: DATABASE_URL is missing. Is .env in the project root, with no spaces around '='?")

try:
    with psycopg.connect(url, connect_timeout=30) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = [r[0] for r in cur.fetchall()]
        print("Connected. Tables found:", ", ".join(tables))
        for t in tables:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(t)))
            print(f"  {t}: {cur.fetchone()[0]} rows")
except Exception as e:
    # Never print the URL or password
    print(f"Connection failed ({type(e).__name__}): {str(e).splitlines()[0]}")
    sys.exit(1)