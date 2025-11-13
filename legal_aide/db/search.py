"""
Vector search helpers using pgvector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import inf
from typing import Iterable, Sequence

from psycopg import Connection


@dataclass(slots=True)
class SearchFilters:
    court: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    case_number: str | None = None


def search_chunks(
    conn: Connection,
    query_embedding: Sequence[float],
    *,
    filters: SearchFilters | None = None,
    limit: int = 20,
) -> list[dict]:
    """Run vector similarity search over case_chunks."""
    filters = filters or SearchFilters()
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH filtered AS (
                SELECT cc.*, c.case_number, c.title, c.promulgation_date, c.court
                FROM case_chunks cc
                JOIN cases c ON c.id = cc.case_id
                WHERE (%s::TEXT IS NULL OR c.court = %s)
                  AND (%s::DATE IS NULL OR c.promulgation_date >= %s)
                  AND (%s::DATE IS NULL OR c.promulgation_date <= %s)
                  AND (%s::TEXT IS NULL OR c.case_number = %s)
            )
            SELECT
                id,
                case_id,
                section_type,
                chunk_index,
                chunk_text,
                token_count,
                case_number,
                title,
                promulgation_date,
                court,
                embedding <-> %s::vector AS distance
            FROM filtered
            ORDER BY embedding <-> %s::vector
            LIMIT %s
            """,
            (
                filters.court,
                filters.court,
                filters.date_from,
                filters.date_from,
                filters.date_to,
                filters.date_to,
                filters.case_number,
                filters.case_number,
                list(query_embedding),
                list(query_embedding),
                limit,
            ),
        )
        rows = cur.fetchall()

    results = [
        {
            "chunk_id": row[0],
            "case_id": row[1],
            "section_type": row[2],
            "chunk_index": row[3],
            "chunk_text": row[4],
            "token_count": row[5],
            "case_number": row[6],
            "title": row[7],
            "promulgation_date": row[8],
            "court": row[9],
            "distance": float(row[10]),
        }
        for row in rows
    ]
    return results


def mmr_rerank(
    candidates: list[dict],
    lambda_mult: float = 0.6,
    limit: int | None = None,
) -> list[dict]:
    """
    Simple MMR re-ranking by chunk text distance.

    The implementation is placeholder yet avoids duplicates by chunk_id.
    """

    if not candidates:
        return []

    limit = limit or len(candidates)
    selected: list[dict] = []
    remaining = candidates.copy()
    seen_chunk_ids = set()

    while remaining and len(selected) < limit:
        best_idx = None
        best_score = -inf
        for idx, cand in enumerate(remaining):
            if cand["chunk_id"] in seen_chunk_ids:
                continue
            relevance = -cand["distance"]
            diversity = 0.0
            if selected:
                diversity = min(
                    cosine_similarity(cand["chunk_text"], chosen["chunk_text"]) for chosen in selected
                )
            score = lambda_mult * relevance - (1 - lambda_mult) * diversity
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            break
        chosen = remaining.pop(best_idx)
        seen_chunk_ids.add(chosen["chunk_id"])
        selected.append(chosen)

    return selected


def cosine_similarity(text_a: str, text_b: str) -> float:
    """
    Very light-weight proxy for cosine similarity using token overlap.

    This avoids adding another dependency; replace with cross-encoder later.
    """

    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return overlap / ((len(tokens_a) * len(tokens_b)) ** 0.5)
