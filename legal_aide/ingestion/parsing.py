"""
Utilities for parsing legal decisions and chunking text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Sequence

CASE_NUMBER_RE = re.compile(r"G\.\s*R\.\s*No\.\s*[\w-]+", re.IGNORECASE)
DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
    re.IGNORECASE,
)
SECTION_HEADERS = [
    "FACTS",
    "FACT",
    "ISSUE",
    "ISSUES",
    "RULING",
    "DECISION",
    "DOCTRINE",
    "SYLLABUS",
    "DISPOSITION",
    "WHEREFORE",
    "BACKGROUND",
]
SECTION_PATTERN = re.compile(
    r"^\s*(?P<header>" + "|".join(SECTION_HEADERS) + r")\s*:?\s*$", re.IGNORECASE | re.MULTILINE
)
TOKEN_SPLIT_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Normalize whitespace and drop obvious page headers/footers."""
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if line.isdigit():
            continue  # skip isolated page numbers
        lines.append(line)
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def extract_case_metadata(text: str) -> dict:
    """Attempt to derive case metadata from text using regex heuristics."""
    case_number = None
    title = None
    promulgation_date = None

    if match := CASE_NUMBER_RE.search(text):
        case_number = match.group(0).replace("  ", " ").strip()

    non_empty_lines = [line for line in text.splitlines() if line.strip()]
    if non_empty_lines:
        title = non_empty_lines[0].strip()

    if match := DATE_RE.search(text):
        try:
            promulgation_date = datetime.strptime(match.group(0), "%B %d, %Y").date()
        except ValueError:
            promulgation_date = None

    return {
        "case_number": case_number,
        "title": title,
        "court": "PH Supreme Court",
        "promulgation_date": promulgation_date,
    }


def segment_by_headings(text: str) -> list[tuple[str | None, str]]:
    """
    Split the text into sections based on uppercase headings.

    Returns a list of tuples (section_type, section_text).
    """

    matches = list(SECTION_PATTERN.finditer(text))
    if not matches:
        return [(None, text)]

    segments: list[tuple[str | None, str]] = []
    prefix = text[: matches[0].start()].strip()
    if prefix:
        segments.append((None, prefix))

    for idx, match in enumerate(matches):
        header = match.group("header").lower()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunk_text = text[start:end].strip()
        if chunk_text:
            segments.append((header, chunk_text))

    return segments or [(None, text)]


def token_count(text: str) -> int:
    """Approximate token count by whitespace splitting."""
    return len([token for token in TOKEN_SPLIT_RE.split(text.strip()) if token])


def sliding_window_chunks(
    text: str,
    *,
    chunk_size_tokens: int = 800,
    overlap_ratio: float = 0.15,
) -> list[str]:
    """Fallback chunking using a sliding window over tokens."""
    tokens = [token for token in TOKEN_SPLIT_RE.split(text.strip()) if token]
    if not tokens:
        return []

    stride = max(1, int(chunk_size_tokens * (1 - overlap_ratio)))
    chunks: list[str] = []
    for start in range(0, len(tokens), stride):
        window = tokens[start : start + chunk_size_tokens]
        if not window:
            continue
        chunks.append(" ".join(window))
        if start + chunk_size_tokens >= len(tokens):
            break
    return chunks
