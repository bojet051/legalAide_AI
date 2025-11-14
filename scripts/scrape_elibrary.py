#!/usr/bin/env python3
"""
Scrape Supreme Court E-Library decisions (category 1) for 1996-2025.

The script walks year/month listings on https://elibrary.judiciary.gov.ph/thebookshelf/1,
harvests metadata for every decision, downloads the full decision text, and stores
results as CSV/JSON plus individual text files.

Usage:
    python scripts/scrape_elibrary.py --output-dir data

Optional flags let you change the year range, throttle delays, and enable a Selenium
fallback (requires chromedriver/geckodriver on your PATH).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:  # Optional Selenium fallback when static HTML is empty.
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
except ImportError:  # pragma: no cover - Selenium is optional.
    webdriver = None
    ChromeOptions = None


BASE_URL = "https://elibrary.judiciary.gov.ph"
INDEX_URL = f"{BASE_URL}/thebookshelf/1"
MONTH_PATTERN = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$", re.IGNORECASE)
DOC_ID_PATTERN = re.compile(r"/(\d+)(?:\?|$)")


@dataclass(slots=True)
class DecisionMetadata:
    year: int
    month: str
    docket_no: str
    title: str
    date: str
    ponente: Optional[str]
    division: Optional[str]
    keywords: Optional[str]
    doc_id: str
    full_url: str
    text_path: str


class RobotsChecker:
    """Minimal robots.txt parser that only tracks Disallow rules for User-agent: *."""

    def __init__(self, session: requests.Session):
        self.disallow: list[str] = []
        self._fetch_rules(session)

    def _fetch_rules(self, session: requests.Session) -> None:
        try:
            resp = session.get(urljoin(BASE_URL, "/robots.txt"), timeout=20)
            if resp.status_code != 200:
                logging.warning("robots.txt returned %s; continuing cautiously.", resp.status_code)
                return
        except requests.RequestException as exc:  # pragma: no cover - network failure.
            logging.warning("Unable to fetch robots.txt: %s", exc)
            return

        active = False
        for line in resp.text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent"):
                agent = line.split(":", 1)[1].strip()
                active = agent in ("*",)
            elif active and line.lower().startswith("disallow"):
                path = line.split(":", 1)[1].strip() or "/"
                self.disallow.append(path)

    def is_allowed(self, url: str) -> bool:
        path = urlparse(url).path or "/"
        for rule in self.disallow:
            if rule == "/":
                return False
            if path.startswith(rule):
                return False
        return True


class ElibraryScraper:
    def __init__(
        self,
        *,
        session: requests.Session,
        output_dir: Path,
        start_year: int,
        end_year: int,
        min_delay: float,
        max_delay: float,
        use_selenium: bool,
        max_decisions: Optional[int],
    ) -> None:
        self.session = session
        self.output_dir = output_dir
        self.text_dir = output_dir / "full_texts"
        self.start_year = start_year
        self.end_year = end_year
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.use_selenium = use_selenium and webdriver is not None
        self.max_decisions = max_decisions
        self.metadata: list[DecisionMetadata] = []
        self.robots = RobotsChecker(session)

    # ------------------------------------------------------------------ public API
    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.text_dir.mkdir(parents=True, exist_ok=True)

        index_html = self._fetch_html(INDEX_URL)
        month_links = self._extract_year_month_links(index_html)
        total_months = sum(len(months) for months in month_links.values())
        logging.info("Found %d year buckets with %d month links.", len(month_links), total_months)

        for year in sorted(month_links.keys()):
            for month_name, month_url in month_links[year]:
                logging.info("Processing %s %s ...", month_name, year)
                for record in self._scrape_month(year, month_name, month_url):
                    self.metadata.append(record)
                    if self.max_decisions and len(self.metadata) >= self.max_decisions:
                        logging.warning("Stopping early after hitting max_decisions=%s.", self.max_decisions)
                        self._persist_metadata()
                        return

        self._persist_metadata()

    # ------------------------------------------------------------------ scraping helpers
    def _scrape_month(self, year: int, month_name: str, month_url: str) -> Iterator[DecisionMetadata]:
        page = 1
        while True:
            paged_url = re.sub(r"/\d+$", f"/{page}", month_url)
            html = self._fetch_html(paged_url, require_selector="div#left li a")
            entries = self._parse_month_entries(html)
            if not entries:
                if page == 1:
                    logging.debug("No entries for %s %s (page %s).", month_name, year, page)
                break

            logging.info("  Page %d: %d decisions", page, len(entries))
            for entry in entries:
                detail = self._scrape_decision_detail(entry["url"])
                metadata = DecisionMetadata(
                    year=year,
                    month=month_name,
                    docket_no=entry["docket_no"],
                    title=entry["title"],
                    date=entry["date"],
                    ponente=detail.get("ponente"),
                    division=detail.get("division"),
                    keywords=detail.get("keywords"),
                    doc_id=entry["doc_id"],
                    full_url=entry["url"],
                    text_path=self._save_text(entry["doc_id"], detail.get("full_text", "")),
                )
                yield metadata

            page += 1

    def _parse_month_entries(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        entries: list[dict] = []
        for li in soup.select("div#left ul li"):
            anchor = li.find("a", href=True)
            if not anchor:
                continue
            docket_el = anchor.find("strong")
            docket_no = docket_el.get_text(strip=True) if docket_el else anchor.get_text(strip=True)
            small = anchor.find("small")
            title = small.get_text(" ", strip=True) if small else ""
            date_text = self._extract_date_from_anchor(anchor, fallback=soup.title.string if soup.title else "")
            url = anchor["href"]
            doc_id = self._extract_doc_id(url)
            entries.append(
                {
                    "docket_no": docket_no,
                    "title": title,
                    "date": date_text,
                    "url": url,
                    "doc_id": doc_id,
                }
            )
        return entries

    def _scrape_decision_detail(self, url: str) -> dict:
        html = self._fetch_html(url, require_selector="div#left")
        soup = BeautifulSoup(html, "html.parser")
        content = soup.select_one("div#left")
        text = content.get_text("\n", strip=True) if content else soup.get_text("\n", strip=True)

        ponente = self._extract_ponente(content)
        division = self._extract_division(content)
        keywords = self._extract_keywords(content)

        return {
            "ponente": ponente,
            "division": division,
            "keywords": keywords,
            "full_text": text,
        }

    # ------------------------------------------------------------------ extraction helpers
    def _extract_year_month_links(self, html: str) -> dict[int, list[tuple[str, str]]]:
        soup = BeautifulSoup(html, "html.parser")
        year_links: dict[int, list[tuple[str, str]]] = {}
        for header in soup.find_all(["h2", "H2"]):
            try:
                year = int(header.get_text(strip=True))
            except ValueError:
                continue
            if not (self.start_year <= year <= self.end_year):
                continue
            month_pairs: list[tuple[str, str]] = []
            for sibling in header.next_siblings:
                sibling_name = getattr(sibling, "name", None)
                if sibling_name and sibling_name.lower() == "h2":
                    break
                # Check if this sibling itself is an anchor
                if sibling_name == "a" and sibling.get("href"):
                    month_label = sibling.get_text(strip=True)
                    if MONTH_PATTERN.match(month_label):
                        month_pairs.append((month_label, sibling["href"]))
                # Also check for anchors nested inside this sibling
                elif hasattr(sibling, "find_all"):
                    for anchor in sibling.find_all("a", href=True):
                        month_label = anchor.get_text(strip=True)
                        if MONTH_PATTERN.match(month_label):
                            month_pairs.append((month_label, anchor["href"]))
            if month_pairs:
                year_links[year] = month_pairs
        return year_links

    def _extract_date_from_anchor(self, anchor, fallback: str = "") -> str:
        texts = list(anchor.stripped_strings)
        if texts:
            last = texts[-1]
            if re.search(r"\d{4}", last):
                return last
        return fallback

    def _extract_doc_id(self, url: str) -> str:
        match = DOC_ID_PATTERN.search(url)
        if not match:
            raise ValueError(f"Unable to parse doc_id from {url}")
        return match.group(1)

    def _extract_ponente(self, content) -> Optional[str]:
        if not content:
            return None
        for strong in content.select("p > strong"):
            text = strong.get_text(strip=True)
            if "J." in text.upper():
                return text.rstrip(":")
        return None

    def _extract_division(self, content) -> Optional[str]:
        if not content:
            return None
        for header in content.find_all(["h2", "H2"]):
            text = header.get_text(strip=True)
            if "DIVISION" in text.upper():
                return text
        return None

    def _extract_keywords(self, content) -> Optional[str]:
        if not content:
            return None
        keywords_label = content.find(string=re.compile(r"Keywords", re.IGNORECASE))
        if keywords_label:
            parent_text = keywords_label.parent.get_text(" ", strip=True)
            return parent_text
        return None

    # ------------------------------------------------------------------ persistence
    def _save_text(self, doc_id: str, text: str) -> str:
        safe_name = f"decision_{doc_id}.txt"
        path = self.text_dir / safe_name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def _persist_metadata(self) -> None:
        if not self.metadata:
            logging.warning("No metadata to write.")
            return

        csv_path = self.output_dir / "metadata.csv"
        json_path = self.output_dir / "metadata.json"
        fieldnames = list(asdict(self.metadata[0]).keys())

        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for record in self.metadata:
                writer.writerow(asdict(record))
        json_path.write_text(json.dumps([asdict(rec) for rec in self.metadata], ensure_ascii=False, indent=2), encoding="utf-8")
        logging.info("Wrote %d records to %s and %s.", len(self.metadata), csv_path, json_path)

    # ------------------------------------------------------------------ network helpers
    def _fetch_html(self, url: str, *, require_selector: str | None = None) -> str:
        if not self.robots.is_allowed(url):
            raise RuntimeError(f"robots.txt disallows fetching {url}")

        self._polite_delay()
        try:
            resp = self.session.get(url, timeout=40)
            resp.raise_for_status()
            html = resp.text
        except requests.RequestException as exc:
            logging.error("Request failed for %s: %s", url, exc)
            raise

        if self._looks_blocked(html):
            raise RuntimeError(f"Potential block detected when fetching {url}")

        if require_selector and not self._selector_exists(html, require_selector):
            if self.use_selenium:
                logging.info("Falling back to Selenium for %s", url)
                html = self._fetch_with_selenium(url)
            else:
                logging.debug("Selector %s not found for %s", require_selector, url)
        if require_selector and not self._selector_exists(html, require_selector):
            logging.warning("Selector %s still missing for %s", require_selector, url)

        return html

    def _selector_exists(self, html: str, selector: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        return bool(soup.select_one(selector))

    def _fetch_with_selenium(self, url: str) -> str:
        if not self.use_selenium or webdriver is None:
            return ""
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=options)
        try:
            driver.set_page_load_timeout(60)
            driver.get(url)
            time.sleep(3)
            return driver.page_source
        finally:
            driver.quit()

    def _looks_blocked(self, html: str) -> bool:
        lowered = html.lower()
        return "captcha" in lowered or "access denied" in lowered

    def _polite_delay(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)


def build_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Philippine Supreme Court decisions from the E-Library.")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Directory where metadata and texts will be stored.")
    parser.add_argument("--start-year", type=int, default=1996, help="First year to scrape (inclusive).")
    parser.add_argument("--end-year", type=int, default=2025, help="Last year to scrape (inclusive).")
    parser.add_argument("--min-delay", type=float, default=2.0, help="Minimum delay between HTTP requests (seconds).")
    parser.add_argument("--max-delay", type=float, default=5.0, help="Maximum delay between HTTP requests (seconds).")
    parser.add_argument("--use-selenium", action="store_true", help="Enable Selenium fallback if static fetches are empty.")
    parser.add_argument("--max-decisions", type=int, default=None, help="Optional cap to stop after N decisions (for testing).")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")

    if args.start_year < 1996 or args.end_year > 2025:
        raise SystemExit("Year range must stay within 1996-2025 for this scraper.")

    session = build_session("Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36")
    scraper = ElibraryScraper(
        session=session,
        output_dir=args.output_dir,
        start_year=args.start_year,
        end_year=args.end_year,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        use_selenium=args.use_selenium,
        max_decisions=args.max_decisions,
    )
    scraper.run()
    logging.info("Finished. Total decisions scraped: %d", len(scraper.metadata))


if __name__ == "__main__":
    main()
