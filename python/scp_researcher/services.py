from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from models import SCPEntry
from storage import save_scps, sort_entries


BASE_URL = "https://scp-wiki.wikidot.com"
REQUEST_TIMEOUT = 20
MAX_WORKERS = 5
MIN_REQUEST_INTERVAL = 0.35
RETRIES = 3
USER_AGENT = "SCP Researcher local desktop app/1.0 (respectful cached sync)"

ProgressCallback = Callable[[str, int, int], None]


@dataclass(frozen=True, slots=True)
class PageTarget:
    scp_number: str
    title_hint: str
    url: str


class RateLimiter:
    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_request = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self.min_interval - (now - self._last_request)
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()


class SCPWikiClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.rate_limiter = RateLimiter(MIN_REQUEST_INTERVAL)

    def get(self, url: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(RETRIES):
            try:
                self.rate_limiter.wait()
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code == 404:
                    response.raise_for_status()
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"retryable status {response.status_code}", response=response)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(min(2**attempt, 8))
        if last_error:
            raise last_error
        raise RuntimeError(f"Failed to fetch {url}")

    def discover_targets(self, progress: ProgressCallback | None = None) -> list[PageTarget]:
        targets: dict[str, PageTarget] = {}
        series_pages = ["scp-series"] + [f"scp-series-{index}" for index in range(2, 26)]
        empty_or_failed_pages = 0

        for index, slug in enumerate(series_pages, start=1):
            url = f"{BASE_URL}/{slug}"
            try:
                response = self.get(url)
            except requests.RequestException:
                empty_or_failed_pages += 1
                if empty_or_failed_pages >= 3 and index > 5:
                    break
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            content = soup.select_one("#page-content") or soup
            found_on_page = 0
            for link in content.find_all("a", href=True):
                href = str(link.get("href", "")).strip()
                parsed_path = urlparse(href).path.strip("/")
                match = re.fullmatch(r"scp-(\d{3,5})(?:-[a-z0-9-]+)?", parsed_path, re.IGNORECASE)
                if not match:
                    continue

                scp_id = f"SCP-{match.group(1)}"
                full_url = urljoin(BASE_URL, "/" + parsed_path)
                title_hint = link.get_text(" ", strip=True)
                if scp_id not in targets:
                    targets[scp_id] = PageTarget(scp_id, title_hint, full_url)
                    found_on_page += 1

            if found_on_page:
                empty_or_failed_pages = 0
            else:
                empty_or_failed_pages += 1

            if progress:
                progress("Discovering SCP index", index, len(series_pages))

            if empty_or_failed_pages >= 3 and index > 5:
                break

        return sorted(targets.values(), key=lambda target: _scp_sort_key(target.scp_number))

    def fetch_entry(self, target: PageTarget) -> SCPEntry | None:
        try:
            response = self.get(target.url)
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.select_one("#page-content")
        if content is None:
            return None

        for element in content.select("script, style, iframe, .footer-wikiwalk-nav, .licensebox, .page-tags"):
            element.decompose()

        raw_title = _page_title(soup, target)
        object_class = _object_class(content)
        description = _clean_description(content)
        if not description:
            return None

        return SCPEntry(
            scp_number=target.scp_number,
            title=raw_title,
            object_class=object_class,
            description=description,
            url=target.url,
            last_updated=_utc_now(),
        )


def sync_database(
    existing_entries: list[SCPEntry],
    progress: ProgressCallback | None = None,
) -> list[SCPEntry]:
    client = SCPWikiClient()
    existing_by_number = {entry.scp_number: entry for entry in existing_entries}

    try:
        targets = client.discover_targets(progress)
    except Exception:
        return sort_entries(existing_entries)

    if not targets:
        return sort_entries(existing_entries)

    changed_count = 0
    completed = 0
    total = len(targets)
    merged = dict(existing_by_number)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(client.fetch_entry, target): target for target in targets}
        for future in as_completed(futures):
            completed += 1
            target = futures[future]
            try:
                entry = future.result()
            except Exception:
                entry = None

            if entry is not None:
                old_entry = existing_by_number.get(entry.scp_number)
                if old_entry is None or old_entry.content_fingerprint() != entry.content_fingerprint():
                    merged[entry.scp_number] = entry
                    changed_count += 1
                elif old_entry.url != entry.url:
                    merged[entry.scp_number] = SCPEntry(
                        scp_number=old_entry.scp_number,
                        title=old_entry.title,
                        object_class=old_entry.object_class,
                        description=old_entry.description,
                        url=entry.url,
                        last_updated=old_entry.last_updated,
                    )

            if progress:
                progress(f"Synced {target.scp_number} ({changed_count} changed)", completed, total)

            if completed % 25 == 0:
                save_scps(list(merged.values()))

    result = sort_entries(list(merged.values()))
    save_scps(result)
    return result


def _page_title(soup: BeautifulSoup, target: PageTarget) -> str:
    title_node = soup.select_one("#page-title")
    if title_node:
        title = title_node.get_text(" ", strip=True)
    else:
        title = target.title_hint

    title = re.sub(r"\s+", " ", title).strip()
    if not title or title.lower() == target.scp_number.lower():
        return target.title_hint or target.scp_number
    return title


def _object_class(content: BeautifulSoup) -> str:
    text = content.get_text("\n", strip=True)
    patterns = [
        r"Object\s+Class\s*:\s*([^\n\r.]+)",
        r"Class\s*:\s*([^\n\r.]+)",
        r"Object\s+Class\s+([^\n\r.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" :-")
            if value:
                return value[:80]
    return "Unknown"


def _clean_description(content: BeautifulSoup) -> str:
    blocks: list[str] = []
    for node in content.find_all(["p", "blockquote", "li", "h1", "h2", "h3"]):
        text = node.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if text.startswith("+") or text.lower() in {"rating:", "page tags"}:
            continue
        blocks.append(text)

    description = "\n\n".join(blocks)
    description = re.sub(r"\n{3,}", "\n\n", description)
    return description.strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _scp_sort_key(scp_number: str) -> tuple[int, str]:
    digits = "".join(ch for ch in scp_number if ch.isdigit())
    if digits:
        return int(digits), scp_number
    return 999999, scp_number
