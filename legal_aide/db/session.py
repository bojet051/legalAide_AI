"""
PostgreSQL connection utilities.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from legal_aide.config import Settings

_POOL: ConnectionPool | None = None


def get_connection_pool(settings: Settings) -> ConnectionPool:
    """Return a global ConnectionPool instance."""
    global _POOL
    if _POOL is None:
        def configure_connection(conn):
            """Register pgvector on each connection checked out from the pool."""
            register_vector(conn)
        
        _POOL = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            open=True,
            configure=configure_connection,
        )
    return _POOL


@contextmanager
def get_connection(settings: Settings):
    """Context manager that yields a psycopg connection."""
    pool = get_connection_pool(settings)
    with pool.connection() as conn:
        yield conn
