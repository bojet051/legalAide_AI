"""
FastAPI entrypoint for LegalAide.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from legal_aide.api import router
from legal_aide.config import get_settings
from legal_aide.db.session import get_connection_pool
from legal_aide.embeddings import EmbeddingClient, EmbeddingConfig
from legal_aide.ingestion.pipeline import IngestionPipeline
from legal_aide.rag.qa import RagEngine


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    embedding_client = EmbeddingClient(
        EmbeddingConfig(
            model=settings.embedding_model,
            dimension=settings.embedding_dim,
            api_url=settings.embedding_api_url,
            api_key=settings.embedding_api_key,
        )
    )
    db_pool = get_connection_pool(settings)
    pipeline = IngestionPipeline(settings, embedding_client, db_pool)
    rag_engine = RagEngine(settings, embedding_client, db_pool)

    app = FastAPI(title="LegalAide", version="0.1.0")
    app.include_router(router)
    app.state.settings = settings
    app.state.embedding_client = embedding_client
    app.state.db_pool = db_pool
    app.state.pipeline = pipeline
    app.state.rag_engine = rag_engine
    return app


app = create_app()
