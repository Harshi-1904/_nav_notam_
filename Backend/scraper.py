"""
Web scraper for Pakistan NAVAREA IX warnings
Collects both historical backfill and live updates from Pakistan Navy
"""

import asyncio
import hashlib
from urllib.parse import urljoin
from typing import List, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger
import re

from config import (
    COASTAL_WARNINGS_URL,
    PAKISTAN_NAVAREA_URL,
    SCRAPER_TIMEOUT,
    SCRAPER_RETRIES,
    SCRAPER_BACKOFF,
    USER_AGENT,
)


class NavAreaScraper:
    """
    Scraper for Pakistan NAVAREA IX warnings.
    Uses requests with retries and a lightweight async wrapper.
    """

    def __init__(self):
        self.session = self._create_session()
        self.base_url = PAKISTAN_NAVAREA_URL
        self.coastal_url = COASTAL_WARNINGS_URL
        self.headers = {"User-Agent": USER_AGENT}
        logger.info(
            f"NavAreaScraper initialized with base URL: {self.base_url} and coastal URL: {self.coastal_url}"
        )

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=SCRAPER_RETRIES,
            backoff_factor=SCRAPER_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a single page with error handling.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None if failed
        """
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=SCRAPER_TIMEOUT,
            )
            response.raise_for_status()
            logger.debug(f"Fetched {url} - Status: {response.status_code}")
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return None

    async def fetch_page_async(self, url: str) -> Optional[str]:
        """
        Fetch page asynchronously using a worker thread.
        """
        try:
            return await asyncio.to_thread(self.fetch_page, url)
        except Exception as e:
            logger.error(f"Async error: {url} - {str(e)}")
            return None

    def parse_warnings_from_html(self, html: str, source_url: Optional[str] = None, source_type: str = "navarea") -> List[dict]:
        """
        Parse warnings from HTML content.
        """
        warnings = []
        seen_signatures = set()

        try:
            soup = BeautifulSoup(html, "html.parser")
            warning_selectors = [
                "div.warning",
                "div.notice",
                "article",
                "div.alert",
                "div[class*='warning']",
                "tr",
            ]

            for selector in warning_selectors:
                elements = soup.select(selector)
                if elements:
                    logger.debug(f"Found {len(elements)} elements with selector: {selector}")
                    for element in elements:
                        warning = self._extract_warning_from_element(
                            element,
                            source_url=source_url,
                            source_type=source_type,
                        )
                        if warning and warning.get("message"):
                            signature = self._warning_signature(
                                warning.get("message", ""),
                                source_url=source_url,
                                source_type=source_type,
                            )
                            if signature in seen_signatures:
                                continue
                            seen_signatures.add(signature)
                            warnings.append(warning)

            logger.info(f"Parsed {len(warnings)} warnings from HTML")
            return warnings
        except Exception as e:
            logger.error(f"Error parsing HTML: {str(e)}")
            return []

    def _extract_warning_from_element(self, element, source_url: Optional[str] = None, source_type: str = "navarea") -> Optional[dict]:
        """
        Extract warning information from a DOM element.
        """
        try:
            text = element.get_text(strip=True)
            if not text or len(text) < 10:
                return None

            header_markers = ["S.NO", "REGION/AREA", "DTG", "WARNING #", "DESCRIPTION", "ATTACHMENT"]
            upper_text = text.upper()
            if all(marker in upper_text for marker in header_markers[:4]):
                return None

            warning_id = self._extract_warning_id(text) or f"NAVAREA_{int(datetime.utcnow().timestamp())}"
            date = self._extract_date(text)
            area = self._extract_area(text)

            return {
                "warning_id": warning_id,
                "message": text[:1000],
                "date": date,
                "area": area,
                "source_url": source_url,
                "source_html": str(element)[:5000],
                "source_type": source_type,
            }
        except Exception as e:
            logger.debug(f"Error extracting warning from element: {str(e)}")
            return None

    def _warning_signature(self, text: str, source_url: Optional[str] = None, source_type: str = "navarea") -> str:
        """Build a stable signature for duplicate suppression."""
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        key = f"{source_type or ''}|{source_url or ''}|{normalized}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    def _extract_warning_id(self, text: str) -> Optional[str]:
        """Extract warning ID from text."""
        warning_number = self._extract_warning_number(text)
        if warning_number:
            return f"NAVAREA_{warning_number.replace('/', '_')}"

        patterns = [
            r"(?:WARNING|NOTICE)\s+(?:NO|#)?\.?\s*(\d+)",
            r"NAVAREA\s+([A-Z0-9]+)",
            r"(?:HAZARD|ALERT)\s+ID\s*:\s*([A-Z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"NAVAREA_{match.group(1)}"
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        return f"NAVAREA_{digest}"

    def _extract_date(self, text: str) -> datetime:
        """Extract date from text."""
        date_patterns = [
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
            r"(\d{4})-(\d{1,2})-(\d{1,2})",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    from dateutil import parser

                    return parser.parse(match.group(0))
                except Exception:
                    pass

        return datetime.utcnow()

    def _extract_area(self, text: str) -> Optional[str]:
        """Extract area/zone information from text."""
        patterns = [
            r"AREA?\s*[:\-]?\s*([A-Z0-9]+)",
            r"ZONE?\s*[:\-]?\s*([A-Z0-9]+)",
            r"(?:NAVAREA|AREA)\s+([A-Z]{2}\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_warning_number(self, text: str) -> Optional[str]:
        """Extract a warning number like 201/26 from NAVAREA rows."""
        match = re.search(r"\b(\d{1,3}/\d{2})\b", text)
        return match.group(1) if match else None

    def scrape_latest_warnings(self) -> List[dict]:
        """
        Scrape latest warnings from both NAVAREA and coastal sources.
        """
        warnings = []
        warnings.extend(self.scrape_navarea_warnings())
        warnings.extend(self.scrape_coastal_warnings())

        deduped = self._dedupe_warnings(warnings)
        logger.info(f"Found {len(deduped)} latest warnings across both sources")
        return deduped

    def scrape_navarea_warnings(self) -> List[dict]:
        """Scrape the NAVAREA warnings listing."""
        logger.info(f"Scraping latest warnings from {self.base_url}")
        html = self.fetch_page(self.base_url)
        if not html:
            logger.error("Failed to fetch NAVAREA page")
            return []

        warnings = self.parse_warnings_from_html(html, source_url=self.base_url, source_type="navarea")
        logger.info(f"Found {len(warnings)} NAVAREA warnings")
        return warnings

    def scrape_coastal_warnings(self) -> List[dict]:
        """Scrape the coastal warnings listing and fetch attachment text when available."""
        logger.info(f"Scraping coastal warnings from {self.coastal_url}")
        html = self.fetch_page(self.coastal_url)
        if not html:
            logger.error("Failed to fetch coastal warnings page")
            return []

        warnings = self.parse_coastal_warnings_from_html(html, self.coastal_url)
        logger.info(f"Found {len(warnings)} coastal warnings")
        return warnings

    async def scrape_multiple_urls(self, urls: List[str]) -> List[dict]:
        """
        Scrape multiple URLs asynchronously.
        """
        all_warnings = []
        results = await asyncio.gather(*[self.fetch_page_async(url) for url in urls])

        for html in results:
            if html:
                warnings = self.parse_warnings_from_html(html)
                all_warnings.extend(warnings)

        logger.info(f"Scraped {len(all_warnings)} warnings from {len(urls)} URLs")
        return all_warnings

    def parse_coastal_warnings_from_html(self, html: str, page_url: str) -> List[dict]:
        """Parse the coastal warnings table and fetch attachment text for each row."""
        warnings = []

        try:
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("table tr")
            if not rows:
                rows = soup.select("tr")

            for row in rows:
                cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
                if len(cells) < 6:
                    continue

                text = " ".join(cells)
                if "S.NO" in text.upper() or "REGION/AREA" in text.upper():
                    continue

                attachment = row.find("a", href=True)
                attachment_text = None
                attachment_url = None
                if attachment:
                    attachment_url = urljoin(page_url, attachment["href"])
                    attachment_text = self.fetch_page(attachment_url)

                warning = self._build_coastal_warning_from_row(
                    cells=cells,
                    row_html=str(row),
                    page_url=page_url,
                    attachment_url=attachment_url,
                    attachment_text=attachment_text,
                )
                if warning and warning.get("message"):
                    warnings.append(warning)

            logger.info(f"Parsed {len(warnings)} coastal warnings from HTML")
            return warnings
        except Exception as e:
            logger.error(f"Error parsing coastal HTML: {str(e)}")
            return []

    def _build_coastal_warning_from_row(
        self,
        cells: List[str],
        row_html: str,
        page_url: str,
        attachment_url: Optional[str] = None,
        attachment_text: Optional[str] = None,
    ) -> Optional[dict]:
        """Build a warning dict from a coastal table row."""
        try:
            row_text = " ".join(cells)
            warning_no = self._extract_warning_number(row_text)
            warning_id = f"NAVAREA_{warning_no.replace('/', '_')}" if warning_no else None
            region = cells[1] if len(cells) > 1 else None
            dtg = cells[2] if len(cells) > 2 else None
            group = cells[4] if len(cells) > 4 else None
            description = cells[5] if len(cells) > 5 else None

            combined_message_parts = [part for part in [region, dtg, warning_no, group, description, attachment_text] if part]
            combined_message = "\n".join(combined_message_parts).strip()
            if len(combined_message) < 10:
                return None

            return {
                "warning_id": warning_id or f"NAVAREA_{int(datetime.utcnow().timestamp())}",
                "message": combined_message,
                "date": self._extract_date(dtg or combined_message),
                "area": group or region,
                "source_url": attachment_url or page_url,
                "source_html": row_html[:5000],
                "source_type": "coastal",
            }
        except Exception as e:
            logger.debug(f"Error building coastal warning: {str(e)}")
            return None

    def _extract_warning_number(self, text: str) -> Optional[str]:
        """Extract the warning number like 075/26."""
        match = re.search(r"\b(\d{1,3}/\d{2})\b", text)
        return match.group(1) if match else None

    def _dedupe_warnings(self, warnings: List[dict]) -> List[dict]:
        """Deduplicate warnings by warning_id, keeping the most detailed record."""
        deduped = {}
        for warning in warnings:
            warning_id = warning.get("warning_id")
            if not warning_id:
                continue

            existing = deduped.get(warning_id)
            if not existing:
                deduped[warning_id] = warning
                continue

            existing_len = len(existing.get("message", ""))
            incoming_len = len(warning.get("message", ""))
            if incoming_len > existing_len:
                deduped[warning_id] = warning

        return list(deduped.values())

    def close(self):
        """Close session."""
        self.session.close()
        logger.info("Scraper session closed")


class HistoricalBackfiller:
    """
    Handles historical backfill of NAVAREA warnings.
    Uses only real, discoverable listing URLs.

    The Pakistan Navy warning pages currently expose the live NAVAREA and
    coastal lists directly, but do not expose the guessed /archive/ URLs that
    older code attempted to crawl. Keeping the backfill constrained to actual
    pages avoids noisy 404s while still collecting the available warning data.
    """

    def __init__(self, scraper: NavAreaScraper):
        self.scraper = scraper
        logger.info("HistoricalBackfiller initialized")

    def generate_archive_urls(self) -> List[str]:
        """
        Generate warning listing URLs that are actually published.
        """
        urls = [self.scraper.base_url]

        if self.scraper.coastal_url and self.scraper.coastal_url not in urls:
            urls.append(self.scraper.coastal_url)

        return urls

    async def backfill_warnings(self) -> List[dict]:
        """
        Perform historical backfill.
        """
        logger.info("Starting historical backfill")
        urls = self.generate_archive_urls()
        warnings = await self.scraper.scrape_multiple_urls(urls)
        warnings.extend(self.scraper.scrape_coastal_warnings())

        unique_warnings = {w["warning_id"]: w for w in warnings}.values()
        logger.info(f"Historical backfill complete: {len(unique_warnings)} unique warnings")
        return list(unique_warnings)


def scrape_pakistan_navarea() -> List[dict]:
    """
    Main function to scrape Pakistan NAVAREA warnings.
    """
    scraper = NavAreaScraper()
    try:
        return scraper.scrape_latest_warnings()
    finally:
        scraper.close()


async def backfill_pakistan_navarea() -> List[dict]:
    """
    Main function to backfill Pakistan NAVAREA warnings.
    """
    scraper = NavAreaScraper()
    backfiller = HistoricalBackfiller(scraper)
    try:
        return await backfiller.backfill_warnings()
    finally:
        scraper.close()
