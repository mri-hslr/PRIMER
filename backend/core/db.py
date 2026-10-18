from __future__ import annotations

from contextlib import contextmanager

from psycopg_pool import ConnectionPool

from config import DATABASE_URL

_pool = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is missing. Check .env in the project root.")
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            timeout=30,
            check=ConnectionPool.check_connection,   # Neon closes idle connections; this replaces dead ones
            open=True,
        )
    return _pool


@contextmanager
def connection():
    """Commits on success, rolls back on error."""
    with get_pool().connection() as conn:
        yield conn