"""
Dataclasses mirroring database tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(slots=True)
class CaseRecord:
    id: int
    case_number: Optional[str]
    title: Optional[str]
    court: Optional[str]
    promulgation_date: Optional[date]
    full_text: Optional[str]
    source_file: Optional[str]
    created_at: datetime


@dataclass(slots=True)
class CaseChunkRecord:
    id: int
    case_id: int
    section_type: Optional[str]
    chunk_index: int
    chunk_text: str
    token_count: int
    created_at: datetime
