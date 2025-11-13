"""
Database query helpers for cases and chunks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from psycopg import Connection


@dataclass(slots=True)
class ChunkInsert:
    section_type: Optional[str]
    chunk_index: int
    chunk_text: str
    token_count: int
    embedding: Sequence[float]


def insert_case(
    conn: Connection,
    *,
    case_number: Optional[str],
    title: Optional[str],
    court: Optional[str],
    promulgation_date,
    full_text: str,
    source_file: Optional[str],
) -> int:
    """Insert a single case row and return its ID."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cases (case_number, title, court, promulgation_date, full_text, source_file)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (case_number, title, court, promulgation_date, full_text, source_file),
        )
        case_id = cur.fetchone()[0]
    return int(case_id)


def insert_case_chunks(conn: Connection, case_id: int, chunks: Iterable[ChunkInsert]) -> int:
    """Insert chunk rows linked to a case. Returns number of inserted chunks."""
    rows = [
        (
            case_id,
            chunk.section_type,
            chunk.chunk_index,
            chunk.chunk_text,
            chunk.token_count,
            list(chunk.embedding),
        )
        for chunk in chunks
    ]
    if not rows:
        return 0

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO case_chunks (case_id, section_type, chunk_index, chunk_text, token_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
    return len(rows)


def save_case_with_chunks(
    conn: Connection,
    *,
    metadata: dict,
    full_text: str,
    source_file: Optional[str],
    chunks: Iterable[ChunkInsert],
) -> int:
    """Persist a case and all of its chunks inside a single transaction."""
    case_id = insert_case(
        conn,
        case_number=metadata.get("case_number"),
        title=metadata.get("title"),
        court=metadata.get("court"),
        promulgation_date=metadata.get("promulgation_date"),
        full_text=full_text,
        source_file=source_file,
    )
    insert_case_chunks(conn, case_id, chunks)
    conn.execute("ANALYZE case_chunks;")
    conn.commit()
    return case_id


def delete_all_cases(conn: Connection) -> None:
    """Remove all cases and chunks."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE case_chunks CASCADE;")
        cur.execute("TRUNCATE cases CASCADE;")
    conn.commit()


def fetch_case(conn: Connection, case_id: int) -> Optional[dict]:
    """Fetch a single case row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, case_number, title, court, promulgation_date, full_text, source_file, created_at
            FROM cases
            WHERE id = %s
            """,
            (case_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None

    return {
        "id": row[0],
        "case_number": row[1],
        "title": row[2],
        "court": row[3],
        "promulgation_date": row[4],
        "full_text": row[5],
        "source_file": row[6],
        "created_at": row[7],
    }


def fetch_case_chunks(conn: Connection, case_id: int) -> list[dict]:
    """Return all chunks for a case ordered by chunk_index."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, section_type, chunk_index, chunk_text, token_count, created_at
            FROM case_chunks
            WHERE case_id = %s
            ORDER BY chunk_index ASC
            """,
            (case_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "section_type": r[1],
            "chunk_index": r[2],
            "chunk_text": r[3],
            "token_count": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]
