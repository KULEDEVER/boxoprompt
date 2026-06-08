from __future__ import annotations

import html
import json
import os
import re
import ssl
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .data import MAX_SCP_NUMBER
from .models import ScpEntry

SCP_URL_TEMPLATE = "https://scp-wiki.wikidot.com/scp-{number}"
UNAVAILABLE_TEXT = "SCP file unavailable or redacted"


class ScpInputError(ValueError):
    pass


class PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.capture_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.capture_title = True
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "blockquote"}:
            self.body_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.capture_title = False
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "li", "h1", "h2", "h3", "blockquote"}:
            self.body_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self.capture_title:
            self.title_parts.append(text)
        self.body_parts.append(text)

    @property
    def title(self) -> str:
        return clean_text(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return clean_text("\n".join(self.body_parts))


@dataclass
class ScpService:
    cache_dir: Path

    @classmethod
    def create(cls) -> "ScpService":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        cache_dir = base / "SCP Researcher" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cls(cache_dir=cache_dir)

    def normalize_number(self, value: str | int) -> int:
        text = str(value).strip().lower()
        match = re.fullmatch(r"(?:scp[-_\s]*)?0*(\d{1,4})", text)
        if not match:
            raise ScpInputError("Enter an SCP number, for example 173 or SCP-049.")

        number = int(match.group(1))
        if number < 1 or number > MAX_SCP_NUMBER:
            raise ScpInputError(f"Choose a number from 001 to {MAX_SCP_NUMBER}.")
        return number

    def url_for(self, number: int) -> str:
        return SCP_URL_TEMPLATE.format(number=f"{number:03d}")

    def cache_path(self, number: int) -> Path:
        return self.cache_dir / f"scp-{number:03d}.json"

    def cached_entry(self, number: int) -> ScpEntry | None:
        path = self.cache_path(number)
        if not path.exists():
            return None
        try:
            return entry_from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def cached_entries(self) -> list[ScpEntry]:
        entries: list[ScpEntry] = []
        for path in sorted(self.cache_dir.glob("scp-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                entries.append(entry_from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return entries

    def search_cached(
        self,
        query: str,
        favorites: set[int] | None = None,
        only_favorites: bool = False,
        object_classes: set[str] | None = None,
    ) -> list[ScpEntry]:
        favorites = favorites or set()
        object_classes = object_classes or set()
        words = [part for part in re.split(r"\s+", query.strip().lower()) if part]
        results: list[ScpEntry] = []

        for entry in self.cached_entries():
            if only_favorites and entry.number not in favorites:
                continue
            if object_classes and entry.object_class not in object_classes:
                continue
            haystack = " ".join(
                (
                    entry.code.lower(),
                    str(entry.number),
                    entry.title.lower(),
                    entry.description.lower(),
                    entry.object_class.lower(),
                    " ".join(entry.tags).lower(),
                )
            )
            if all(word in haystack for word in words):
                results.append(entry)
        return results

    def fetch_entry(self, number: int, use_cache: bool = True) -> ScpEntry:
        if use_cache:
            cached = self.cached_entry(number)
            if cached is not None:
                return cached

        url = self.url_for(number)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "SCP-Researcher/3.1 (+local desktop research utility)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )

        try:
            context = ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=15, context=context) as response:
                status = getattr(response, "status", 200)
                html_bytes = response.read()
            if status >= 400:
                entry = unavailable_entry(number)
                if status == 404:
                    self.save_cache(entry)
                return entry
            page_html = html_bytes.decode("utf-8", errors="replace")
            entry = parse_scp_page(number, page_html)
            self.save_cache(entry)
            return entry
        except urllib.error.HTTPError as exc:
            entry = unavailable_entry(number)
            if exc.code == 404:
                self.save_cache(entry)
            return entry
        except (urllib.error.URLError, TimeoutError, OSError):
            return unavailable_entry(number)

    def save_cache(self, entry: ScpEntry) -> None:
        payload = asdict(entry)
        payload["tags"] = list(entry.tags)
        self.cache_path(entry.number).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def open_in_browser(self, number: int) -> str:
        url = self.url_for(number)
        webbrowser.open(url)
        return url


def parse_scp_page(number: int, page_html: str) -> ScpEntry:
    parser = PageTextParser()
    parser.feed(page_html)
    page_text = parser.text

    if page_missing(page_text, parser.title):
        return unavailable_entry(number)

    title = extract_title(number, parser.title, page_text)
    object_class = extract_object_class(page_text)
    description = extract_description(page_text)
    tags = tuple(sorted({tag for tag in (object_class.lower(), "live-cache") if tag and tag != "pending"}))

    return ScpEntry(
        number=number,
        title=title,
        description=description or UNAVAILABLE_TEXT,
        object_class=object_class,
        tags=tags,
        available=bool(description),
        fetched_at=datetime.now().isoformat(timespec="seconds"),
    )


def page_missing(page_text: str, title: str) -> bool:
    lowered = f"{title}\n{page_text}".lower()
    missing_markers = (
        "the page you were looking for doesn't exist",
        "this page doesn't exist",
        "create page",
        "404",
    )
    return any(marker in lowered for marker in missing_markers)


def extract_title(number: int, title_text: str, page_text: str) -> str:
    title_text = html.unescape(title_text)
    title_text = re.sub(r"\s*-\s*SCP Foundation\s*$", "", title_text, flags=re.IGNORECASE).strip()
    title_text = re.sub(rf"^SCP-{number:03d}\s*[-:]\s*", "", title_text, flags=re.IGNORECASE).strip()
    if title_text and "wikidot" not in title_text.lower():
        return title_text

    match = re.search(rf"SCP-{number:03d}\s*[-:]\s*(.+)", page_text, flags=re.IGNORECASE)
    if match:
        candidate = clean_line(match.group(1))
        if candidate:
            return candidate[:120]
    return f"SCP-{number:03d}"


def extract_object_class(page_text: str) -> str:
    patterns = (
        r"Object\s+Class\s*:\s*([A-Za-z -]+)",
        r"Object\s+Class\s+([A-Za-z -]+)",
        r"Class\s*:\s*([A-Za-z -]+)",
    )
    known = ("Safe", "Euclid", "Keter", "Thaumiel", "Neutralized", "Explained", "Apollyon", "Archon", "Ticonderoga")
    for pattern in patterns:
        match = re.search(pattern, page_text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = clean_line(match.group(1))
        for item in known:
            if re.search(rf"\b{re.escape(item)}\b", candidate, flags=re.IGNORECASE):
                return item
    for item in known:
        if re.search(rf"\bObject Class\b[\s\S]{{0,80}}\b{re.escape(item)}\b", page_text, flags=re.IGNORECASE):
            return item
    return "Pending"


def extract_description(page_text: str) -> str:
    text = normalize_page_text(page_text)
    description_match = re.search(r"\bDescription\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
    if not description_match:
        return first_useful_block(text)

    description = description_match.group(1)
    stop = re.search(
        r"\n\s*(?:Addendum|Appendix|Interview|Incident|Experiment|Exploration|Discovery|References|Footnotes|"
        r"Special Containment Procedures|Document|Note)\b",
        description,
        flags=re.IGNORECASE,
    )
    if stop:
        description = description[: stop.start()]
    return trim_description(description)


def first_useful_block(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 80]
    for line in lines:
        lowered = line.lower()
        if not any(skip in lowered for skip in ("rating:", "page tags", "scp foundation", "creative commons")):
            return trim_description(line)
    return ""


def normalize_page_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def trim_description(text: str, limit: int = 1400) -> str:
    text = clean_text(text)
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cutoff = text.rfind(". ", 0, limit)
    if cutoff < 400:
        cutoff = limit
    return text[:cutoff].strip() + "..."


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\xa0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip(" -:\n\t")


def unavailable_entry(number: int) -> ScpEntry:
    return ScpEntry(
        number=number,
        title=UNAVAILABLE_TEXT,
        description=UNAVAILABLE_TEXT,
        object_class="Unavailable",
        tags=("redacted",),
        available=False,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
    )


def entry_from_dict(data: dict[str, Any]) -> ScpEntry:
    return ScpEntry(
        number=int(data["number"]),
        title=str(data.get("title") or UNAVAILABLE_TEXT),
        description=str(data.get("description") or UNAVAILABLE_TEXT),
        object_class=str(data.get("object_class") or "Pending"),
        tags=tuple(str(item) for item in data.get("tags", [])),
        available=bool(data.get("available", True)),
        fetched_at=str(data.get("fetched_at", "")),
    )
