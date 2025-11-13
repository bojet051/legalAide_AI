"""
OCR helpers using pdf2image + pytesseract.
"""

from __future__ import annotations

import logging
from typing import Iterable, List

from pdf2image import convert_from_path
import pytesseract

logger = logging.getLogger(__name__)


def ocr_pdf(path: str, tesseract_cmd: str | None = None) -> str:
    """Convert a PDF into text by running OCR on each page."""
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    pages = convert_from_path(path)
    text_pages: List[str] = []
    for idx, page in enumerate(pages, start=1):
        logger.info("Running OCR on %s page %d", path, idx)
        page_text = pytesseract.image_to_string(page)
        text_pages.append(f"[Page {idx}]\n{page_text}")
    return "\n\n".join(text_pages)
