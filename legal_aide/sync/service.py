"""
Sync service for checking eLibrary and downloading new decisions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

ELIBRARY_BASE_URL = "https://elibrary.judiciary.gov.ph"
ELIBRARY_INDEX_URL = f"{ELIBRARY_BASE_URL}/thebookshelf/1"
DOC_ID_PATTERN = re.compile(r"/(\d+)(?:\?|$)")


@dataclass(slots=True)
class PendingDecision:
    doc_id: str
    docket_no: str
    title: str
    decision_date: Optional[date]
    ponente: Optional[str]
    division: Optional[str]
    keywords: Optional[str]
    elibrary_url: str


class SyncService:
    def __init__(self, db_pool: ConnectionPool, download_dir: Path):
        self.db_pool = db_pool
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

    def check_for_new_decisions(
        self, 
        year_from: int = 2024, 
        year_to: int = 2025,
        max_per_month: int = 10
    ) -> int:
        """
        Check eLibrary for new decisions and stage them in pending_decisions table.
        Returns the sync_job_id.
        """
        with self.db_pool.connection() as conn:
            # Create sync job
            result = conn.execute(
                """
                INSERT INTO sync_jobs (status, year_from, year_to)
                VALUES ('running', %s, %s)
                RETURNING id
                """,
                (year_from, year_to)
            ).fetchone()
            sync_job_id = result[0] if result else 0
            conn.commit()

        total_checked = 0
        new_found = 0
        failed = 0

        try:
            # Get month links from eLibrary
            month_links = self._extract_year_month_links(year_from, year_to)
            
            for year, months in month_links.items():
                for month_name, month_url in months:
                    logger.info(f"Checking {month_name} {year}...")
                    
                    try:
                        decisions = self._scrape_month(
                            year, month_name, month_url, max_per_month
                        )
                        total_checked += len(decisions)
                        
                        # Filter out already ingested cases
                        new_decisions = self._filter_new_decisions(decisions)
                        new_found += len(new_decisions)
                        
                        # Stage in pending_decisions
                        self._stage_decisions(sync_job_id, new_decisions)
                        
                    except Exception as exc:
                        logger.error(f"Failed to check {month_name} {year}: {exc}")
                        failed += 1
                        continue

            # Mark job as completed
            with self.db_pool.connection() as conn:
                conn.execute(
                    """
                    UPDATE sync_jobs
                    SET status = 'completed',
                        completed_at = now(),
                        total_checked = %s,
                        new_found = %s,
                        failed = %s
                    WHERE id = %s
                    """,
                    (total_checked, new_found, failed, sync_job_id)
                )
                conn.commit()

            logger.info(
                f"Sync complete: checked={total_checked}, new={new_found}, failed={failed}"
            )
            return sync_job_id

        except Exception as exc:
            logger.error(f"Sync job failed: {exc}")
            with self.db_pool.connection() as conn:
                conn.execute(
                    """
                    UPDATE sync_jobs
                    SET status = 'failed',
                        completed_at = now(),
                        error_message = %s,
                        total_checked = %s,
                        new_found = %s,
                        failed = %s
                    WHERE id = %s
                    """,
                    (str(exc), total_checked, new_found, failed, sync_job_id)
                )
                conn.commit()
            raise

    def download_pending_pdfs(self, limit: Optional[int] = None) -> dict:
        """Download PDFs for pending decisions."""
        with self.db_pool.connection() as conn:
            if limit:
                pending = conn.execute(
                    """
                    SELECT id, doc_id, elibrary_url
                    FROM pending_decisions
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,)
                ).fetchall()
            else:
                pending = conn.execute(
                    """
                    SELECT id, doc_id, elibrary_url
                    FROM pending_decisions
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                    """
                ).fetchall()

        downloaded = 0
        failed_items = []

        for row in pending:
            decision_id, doc_id, url = row
            
            try:
                # Mark as downloading
                with self.db_pool.connection() as conn:
                    conn.execute(
                        "UPDATE pending_decisions SET status = 'downloading' WHERE id = %s",
                        (decision_id,)
                    )
                    conn.commit()

                # Download PDF
                pdf_path = self._download_pdf(doc_id, url)
                
                # Mark as downloaded
                with self.db_pool.connection() as conn:
                    conn.execute(
                        """
                        UPDATE pending_decisions
                        SET status = 'downloaded', pdf_path = %s
                        WHERE id = %s
                        """,
                        (str(pdf_path), decision_id)
                    )
                    conn.commit()
                
                downloaded += 1
                logger.info(f"Downloaded: {doc_id}")

            except Exception as exc:
                logger.error(f"Failed to download {doc_id}: {exc}")
                with self.db_pool.connection() as conn:
                    conn.execute(
                        """
                        UPDATE pending_decisions
                        SET status = 'failed', error_message = %s
                        WHERE id = %s
                        """,
                        (str(exc), decision_id)
                    )
                    conn.commit()
                failed_items.append({"doc_id": doc_id, "error": str(exc)})

        return {
            "downloaded": downloaded,
            "failed": len(failed_items),
            "errors": failed_items
        }

    def ingest_pending_decisions(self, pipeline, limit: Optional[int] = None) -> dict:
        """Ingest downloaded PDFs using the existing ingestion pipeline."""
        with self.db_pool.connection() as conn:
            if limit:
                ready = conn.execute(
                    """
                    SELECT id, doc_id, pdf_path
                    FROM pending_decisions
                    WHERE status = 'downloaded'
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,)
                ).fetchall()
            else:
                ready = conn.execute(
                    """
                    SELECT id, doc_id, pdf_path
                    FROM pending_decisions
                    WHERE status = 'downloaded'
                    ORDER BY created_at DESC
                    """
                ).fetchall()

        ingested = 0
        failed_items = []

        for row in ready:
            decision_id, doc_id, pdf_path = row
            
            try:
                # Mark as ingesting
                with self.db_pool.connection() as conn:
                    conn.execute(
                        "UPDATE pending_decisions SET status = 'ingesting' WHERE id = %s",
                        (decision_id,)
                    )
                    conn.commit()

                # Ingest using existing pipeline
                case_id, chunk_count = pipeline.ingest_file(pdf_path)
                
                # Mark as ingested
                with self.db_pool.connection() as conn:
                    conn.execute(
                        """
                        UPDATE pending_decisions
                        SET status = 'ingested'
                        WHERE id = %s
                        """,
                        (decision_id,)
                    )
                    conn.commit()
                
                ingested += 1
                logger.info(f"Ingested: {doc_id} -> case_id={case_id}, chunks={chunk_count}")

            except Exception as exc:
                logger.error(f"Failed to ingest {doc_id}: {exc}")
                with self.db_pool.connection() as conn:
                    conn.execute(
                        """
                        UPDATE pending_decisions
                        SET status = 'failed', error_message = %s
                        WHERE id = %s
                        """,
                        (str(exc), decision_id)
                    )
                    conn.commit()
                failed_items.append({"doc_id": doc_id, "error": str(exc)})

        return {
            "ingested": ingested,
            "failed": len(failed_items),
            "errors": failed_items
        }

    # --- Helper methods ---

    def _extract_year_month_links(self, year_from: int, year_to: int) -> dict:
        """Extract year/month links from eLibrary index."""
        response = self.session.get(ELIBRARY_INDEX_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        year_links = {}
        
        for header in soup.find_all(["h2", "H2"]):
            try:
                year = int(header.get_text(strip=True))
            except ValueError:
                continue
            
            if not (year_from <= year <= year_to):
                continue
            
            month_pairs = []
            for sibling in header.next_siblings:
                sibling_name = getattr(sibling, "name", None)
                if sibling_name and sibling_name.lower() == "h2":
                    break
                
                # Type guard for BeautifulSoup Tag
                if sibling_name == "a" and hasattr(sibling, 'get') and sibling.get("href"):
                    month_label = sibling.get_text(strip=True)
                    if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$", month_label, re.I):
                        href = sibling.get("href")
                        if isinstance(href, str):
                            month_pairs.append((month_label, href))
            
            if month_pairs:
                year_links[year] = month_pairs
        
        return year_links

    def _scrape_month(self, year: int, month: str, url: str, max_decisions: int) -> list[PendingDecision]:
        """Scrape decisions from a month page."""
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        decisions = []
        
        for li in soup.select("div#left ul li")[:max_decisions]:
            anchor = li.find("a", href=True)
            if not anchor:
                continue
            
            docket_el = anchor.find("strong")
            docket_no = docket_el.get_text(strip=True) if docket_el else ""
            
            small = anchor.find("small")
            title = small.get_text(" ", strip=True) if small else ""
            
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            decision_url: str = href
            doc_id_match = DOC_ID_PATTERN.search(decision_url)
            if not doc_id_match:
                continue
            doc_id = doc_id_match.group(1)
            
            decisions.append(PendingDecision(
                doc_id=doc_id,
                docket_no=docket_no,
                title=title,
                decision_date=None,  # Extract from detail page if needed
                ponente=None,
                division=None,
                keywords=None,
                elibrary_url=decision_url if decision_url.startswith("http") else ELIBRARY_BASE_URL + decision_url
            ))
        
        return decisions

    def _filter_new_decisions(self, decisions: list[PendingDecision]) -> list[PendingDecision]:
        """Filter out decisions that are already in the database."""
        if not decisions:
            return []
        
        doc_ids = [d.doc_id for d in decisions]
        
        with self.db_pool.connection() as conn:
            # Check against both cases (via source_file) and pending_decisions
            result = conn.execute(
                """
                SELECT DISTINCT unnest(%s::text[]) AS doc_id
                EXCEPT
                (
                    SELECT regexp_replace(source_file, '.*decision_(\\d+).*', '\\1')
                    FROM cases
                    WHERE source_file ~ 'decision_\\d+'
                    UNION
                    SELECT doc_id FROM pending_decisions
                )
                """,
                (doc_ids,)
            ).fetchall()
        
        existing_doc_ids = {row[0] for row in result}
        return [d for d in decisions if d.doc_id in existing_doc_ids]

    def _stage_decisions(self, sync_job_id: int, decisions: list[PendingDecision]) -> None:
        """Stage new decisions in pending_decisions table."""
        if not decisions:
            return
        
        with self.db_pool.connection() as conn:
            for decision in decisions:
                conn.execute(
                    """
                    INSERT INTO pending_decisions
                        (sync_job_id, doc_id, docket_no, title, decision_date, ponente,
                         division, keywords, elibrary_url, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT (doc_id) DO NOTHING
                    """,
                    (
                        sync_job_id, decision.doc_id, decision.docket_no,
                        decision.title, decision.decision_date, decision.ponente,
                        decision.division, decision.keywords, decision.elibrary_url
                    )
                )
            conn.commit()

    def _download_pdf(self, doc_id: str, url: str) -> Path:
        """Download PDF from eLibrary."""
        # For now, we'll download as text since the scraper extracts text
        # In production, you'd extract the actual PDF link from the detail page
        response = self.session.get(url, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.select_one("div#left")
        text = content.get_text("\n", strip=True) if content else soup.get_text("\n", strip=True)
        
        # Save as txt (matching scraper output format)
        file_path = self.download_dir / f"decision_{doc_id}.txt"
        file_path.write_text(text, encoding="utf-8")
        
        return file_path
