"""
RAG answering utilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Sequence

import httpx

from legal_aide.config import Settings
from legal_aide.db import search
from legal_aide.embeddings import EmbeddingClient

logger = logging.getLogger(__name__)


@dataclass
class RagAnswer:
    question: str
    answer: str
    supporting_chunks: list[dict]
    case_ids: list[int]


class RagEngine:
    """Coordinates query embeddings, vector search, and answer synthesis."""

    def __init__(self, settings: Settings, embedding_client: EmbeddingClient, db_pool) -> None:
        self.settings = settings
        self.embedding_client = embedding_client
        self.db_pool = db_pool

    def search_chunks(
        self,
        question: str,
        *,
        filters: search.SearchFilters | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        query_embedding = self.embedding_client.embed_query(question)
        with self.db_pool.connection() as conn:
            results = search.search_chunks(conn, query_embedding, filters=filters, limit=top_k * 2)
        return search.mmr_rerank(results, limit=top_k)

    def answer_question(
        self,
        question: str,
        *,
        filters: search.SearchFilters | None = None,
        top_k: int = 10,
    ) -> RagAnswer:
        chunks = self.search_chunks(question, filters=filters, top_k=top_k)
        context_block = self._build_context_block(chunks)
        prompt = self._build_prompt(question, context_block)
        answer = self._call_llm(prompt)
        case_ids = sorted({chunk["case_id"] for chunk in chunks})
        return RagAnswer(
            question=question,
            answer=answer,
            supporting_chunks=chunks,
            case_ids=case_ids,
        )

    def _build_context_block(self, chunks: Sequence[dict]) -> str:
        blocks = []
        for chunk in chunks:
            header = f"{chunk.get('title') or 'Unknown Title'} (G.R. {chunk.get('case_number')})"
            snippet = chunk["chunk_text"].strip()
            blocks.append(f"{header}\n{snippet}")
        return "\n\n".join(blocks)

    def _build_prompt(self, question: str, context_block: str) -> str:
        return (
            "You are a legal assistant specializing in Philippine Supreme Court jurisprudence.\n"
            "Using ONLY the provided context, answer the question with citations to case titles "
            "and G.R. numbers when available. Avoid fabricating cases or facts.\n\n"
            f"Question: {question}\n\n"
            f"Context:\n{context_block}\n\nAnswer:"
        )

    def _call_llm(self, prompt: str) -> str:
        """
        Placeholder LLM call. If LLM_MODEL env variables are not configured, return the prompt tail.
        """

        if (
            not self.settings.llm_model
            or not self.settings.llm_api_url
            or not self.settings.llm_api_key
        ):
            logger.warning("LLM model not configured; returning context summary.")
            return prompt.split("Context:", 1)[-1].strip()

        logger.debug("LLM call using model %s", self.settings.llm_model)
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": "You are a legal assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        response = httpx.post(self.settings.llm_api_url, headers=headers, json=payload, timeout=40)
        response.raise_for_status()
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:  # pragma: no cover
            raise RuntimeError(f"Unexpected LLM response: {data}") from exc
