"""
Embedding client abstraction with pluggable backend.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmbeddingConfig:
    model: str
    dimension: int
    api_url: str | None = None
    api_key: str | None = None


class EmbeddingClient:
    """Simple embedding client that can call a remote API or fall back to a deterministic stub."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config

    def embed_document(self, text: str) -> List[float]:
        return self._embed(text, usage="document")

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text, usage="query")

    def _embed(self, text: str, usage: str) -> List[float]:
        if not text.strip():
            return [0.0] * self.config.dimension

        if self.config.api_key and self.config.api_url:
            return self._call_remote_embedding(text, usage=usage)
        return self._fallback_embedding(text)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _call_remote_embedding(self, text: str, usage: str) -> List[float]:
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.config.model,
            "input": text,
            "usage": usage,
        }
        logger.debug("Requesting embeddings from %s", self.config.api_url)
        with httpx.Client(timeout=30) as client:
            response = client.post(self.config.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            vector = data["data"][0]["embedding"]
        except (KeyError, IndexError) as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Unexpected embedding response: {json.dumps(data)[:200]}") from exc
        return vector

    def _fallback_embedding(self, text: str) -> List[float]:
        """Offline-friendly deterministic embedding using hashing."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        rng = random.Random(digest)
        return [rng.uniform(-1, 1) for _ in range(self.config.dimension)]
