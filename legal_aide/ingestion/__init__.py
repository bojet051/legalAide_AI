"""
Ingestion pipeline for LegalAide.
"""

from .pipeline import CaseMetadata, Chunk, IngestionPipeline

__all__ = ["CaseMetadata", "Chunk", "IngestionPipeline"]
