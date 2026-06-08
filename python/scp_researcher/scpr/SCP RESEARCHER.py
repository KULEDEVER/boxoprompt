from __future__ import annotations

import html
import os
import re
import sqlite3
import sys
import time
import traceback
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from PyQt6.QtCore import QObject, QRunnable, QSize, QThreadPool, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QTabBar,
)

try:
    from bs4 import BeautifulSoup
except ImportError:  # The fallback parser keeps live loading optional and dependency-light.
    BeautifulSoup = None


APP_NAME = "SCP Research Terminal"
INDEX_VERSION = 3
BASE_URL = "https://scp-wiki.wikidot.com"
REQUEST_TIMEOUT_SECONDS = 14
SEARCH_LIMIT = 80
SEED_SCP_LIMIT = 7999
USER_AGENT = "SCP Research Terminal/1.0 (local desktop cache; respectful lazy fetch)"
GENERIC_QUERY_TERMS = {"scp", "site", "area", "doc", "document", "audio", "file", "files"}

CATEGORY_LABELS = {
    "all": "All",
    "scp": "SCPs",
    "site": "Sites",
    "document": "Documents",
    "audio": "Audio Files",
}

THEMES = {
    "Amber": {
        "accent": "#d69d45",
        "accent2": "#e7c079",
        "alert": "#b74747",
        "selection": "#314052",
    },
    "Red": {
        "accent": "#e05a5a",
        "accent2": "#ff9b86",
        "alert": "#d13f3f",
        "selection": "#492b32",
    },
    "Blue": {
        "accent": "#64a5ff",
        "accent2": "#9cc8ff",
        "alert": "#e06c75",
        "selection": "#263f5f",
    },
}


@dataclass(frozen=True, slots=True)
class IndexEntry:
    entry_id: str
    title: str
    entry_type: str
    tags: str
    url: str
    priority: int = 0


@dataclass(frozen=True, slots=True)
class SearchResult:
    entry_id: str
    title: str
    entry_type: str
    tags: str
    url: str
    score: float


@dataclass(frozen=True, slots=True)
class SearchDocument:
    entry_id: str
    title: str
    entry_type: str
    tags: str
    url: str
    priority: int
    id_norm: str
    id_compact: str
    id_digits: str
    id_number: int | None
    title_norm: str
    tag_norm: str
    words: frozenset[str]
    tag_words: frozenset[str]

    @classmethod
    def from_entry(cls, entry: IndexEntry) -> "SearchDocument":
        id_norm = normalize_text(entry.entry_id)
        title_norm = normalize_text(entry.title)
        tag_norm = normalize_text(entry.tags)
        id_digits = "".join(ch for ch in entry.entry_id if ch.isdigit())
        all_words = frozenset(f"{id_norm} {title_norm} {tag_norm}".split())
        return cls(
            entry_id=entry.entry_id,
            title=entry.title,
            entry_type=entry.entry_type,
            tags=entry.tags,
            url=entry.url,
            priority=entry.priority,
            id_norm=id_norm,
            id_compact=id_norm.replace(" ", ""),
            id_digits=id_digits,
            id_number=int(id_digits) if id_digits else None,
            title_norm=title_norm,
            tag_norm=tag_norm,
            words=all_words,
            tag_words=frozenset(tag_norm.split()),
        )


@dataclass(frozen=True, slots=True)
class SearchCorpus:
    documents: tuple[SearchDocument, ...]
    token_map: dict[str, frozenset[int]]
    sorted_indexes: dict[str, tuple[int, ...]]
    popular_indexes: dict[str, tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class DetailPayload:
    entry_id: str
    title: str
    entry_type: str
    tags: str
    url: str
    content: str
    source: str
    fetched_at: str
    error: str = ""


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def index_path() -> Path:
    return app_data_dir() / "scp_research_index.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def tokenize(value: str) -> list[str]:
    return [part for part in normalize_text(value).split() if part]


def wiki_slug_for_scp(entry_id: str) -> str:
    number = entry_id.split("-", 1)[1]
    return f"scp-{number.lower()}"


def wiki_url_for_scp(entry_id: str) -> str:
    return f"{BASE_URL}/{wiki_slug_for_scp(entry_id)}"


def scp_id(number: int) -> str:
    return f"SCP-{number:03d}" if number < 1000 else f"SCP-{number:04d}"


def seed_catalog() -> list[IndexEntry]:
    curated_scps = [
        ("SCP-001", "Awaiting De-classification", "proposal classified gate guardian factory database", 95),
        ("SCP-002", "The Living Room", "organic room furniture containment euclid classic", 78),
        ("SCP-003", "Biological Motherboard", "computer motherboard biological temperature", 72),
        ("SCP-004", "The 12 Rusty Keys and the Door", "keys door dimension unsafe exploration", 70),
        ("SCP-005", "Skeleton Key", "key access lock safe utility", 68),
        ("SCP-006", "Fountain of Youth", "water immortality safe", 66),
        ("SCP-007", "Abdominal Planet", "planet human body astronomy", 63),
        ("SCP-008", "Zombie Plague", "virus plague biohazard infection", 88),
        ("SCP-009", "Red Ice", "ice red thermal water", 74),
        ("SCP-010", "Collars of Control", "collar control device mind", 61),
        ("SCP-011", "Sentient Civil War Memorial Statue", "statue memorial sentient", 50),
        ("SCP-012", "A Bad Composition", "music composition blood compulsion", 57),
        ("SCP-013", "Blue Lady Cigarettes", "cigarettes hallucination identity", 56),
        ("SCP-014", "The Concrete Man", "human concrete perception", 52),
        ("SCP-015", "Pipe Nightmare", "pipes structure maze", 56),
        ("SCP-016", "Sentient Micro-Organism", "organism infection mutation", 58),
        ("SCP-017", "Shadow Person", "shadow humanoid light", 77),
        ("SCP-018", "Super Ball", "ball kinetic toy", 62),
        ("SCP-019", "The Monster Pot", "pot ceramic extradimensional", 58),
        ("SCP-020", "Unseen Mold", "mold infection airborne", 58),
        ("SCP-035", "Possessive Mask", "mask possession mind corrosive", 90),
        ("SCP-049", "Plague Doctor", "doctor plague humanoid cure euclid", 98),
        ("SCP-055", "[unknown]", "antimemetic unknown memory information", 96),
        ("SCP-073", "Cain", "humanoid cain reflection", 84),
        ("SCP-076", "Able", "humanoid able warrior resurrection", 86),
        ("SCP-079", "Old AI", "artificial intelligence computer classic", 93),
        ("SCP-087", "The Stairwell", "stairwell exploration audio dark", 92),
        ("SCP-093", "Red Sea Object", "mirror red sea exploration dimension", 87),
        ("SCP-096", "The Shy Guy", "humanoid face pursuit euclid", 99),
        ("SCP-106", "The Old Man", "pocket dimension corrosion keter", 97),
        ("SCP-131", "The Eye Pods", "safe mobile friendly", 74),
        ("SCP-173", "The Sculpture", "statue blink concrete classic", 100),
        ("SCP-184", "The Architect", "building space expansion", 82),
        ("SCP-231", "Special Personnel Requirements", "classified procedure containment", 80),
        ("SCP-239", "The Witch Child", "reality bending child humanoid", 82),
        ("SCP-261", "Pan-dimensional Vending", "vending machine food dimension", 75),
        ("SCP-294", "The Coffee Machine", "coffee machine liquid request", 94),
        ("SCP-343", "God", "humanoid deity safe", 83),
        ("SCP-354", "The Red Pool", "pool portal red containment", 78),
        ("SCP-426", "I am a Toaster", "toaster memetic identity", 89),
        ("SCP-500", "Panacea", "pills medicine cure safe", 96),
        ("SCP-507", "Reluctant Dimension Hopper", "dimension travel humanoid safe", 78),
        ("SCP-610", "The Flesh that Hates", "infection flesh disease", 88),
        ("SCP-682", "Hard-to-Destroy Reptile", "keter adaptive hostile containment", 100),
        ("SCP-701", "The Hanged King's Tragedy", "play theater memetic king", 82),
        ("SCP-914", "The Clockworks", "machine refinement clockwork safe", 98),
        ("SCP-939", "With Many Voices", "voices mimic predator keter", 85),
        ("SCP-963", "Immortality", "amulet bright consciousness", 88),
        ("SCP-999", "The Tickle Monster", "safe friendly orange", 95),
        ("SCP-1048", "Builder Bear", "builder toy replication", 84),
        ("SCP-1471", "MalO ver1.0.0", "app phone image humanoid", 88),
        ("SCP-1609", "The Remains of a Chair", "chair teleport mulch", 78),
        ("SCP-1762", "Where The Dragons Went", "box fantasy paper", 92),
        ("SCP-2000", "Deus Ex Machina", "civilization reset facility", 95),
        ("SCP-2316", "Field Trip", "lake memory bodies antimemetic", 93),
        ("SCP-2521", "●●|●●●●●|●●|●", "symbol information hazard", 84),
        ("SCP-2718", "What Happens After", "death afterlife cognitohazard", 88),
        ("SCP-3000", "Anantashesha", "ocean memory amnestic", 94),
        ("SCP-3008", "A Perfectly Normal Regular Old IKEA", "ikea infinite store survival", 99),
        ("SCP-3125", "The Escapee", "antimemetic fifthist concept", 90),
        ("SCP-3999", "I Am At The Center of Everything That Happens To Me", "reality bending narrative", 86),
        ("SCP-4000", "Taboo", "names forest fae", 89),
        ("SCP-4205", "In The Eyes of the Beholder", "pattern perception anomalous art", 76),
        ("SCP-4999", "Someone To Watch Over Us", "death comfort cigarette", 90),
        ("SCP-5000", "Why?", "suit mystery foundation hostile", 99),
        ("SCP-5031", "Yet Another Murder Monster", "music cooking rehabilitation", 88),
    ]

    special = {
        entry_id: IndexEntry(entry_id, title, "scp", f"scp anomaly containment {tags}", wiki_url_for_scp(entry_id), priority)
        for entry_id, title, tags, priority in curated_scps
    }

    catalog: list[IndexEntry] = []
    for number in range(1, SEED_SCP_LIMIT + 1):
        entry_id = scp_id(number)
        if entry_id in special:
            catalog.append(special[entry_id])
            continue
        series = ((number - 1) // 1000) + 1
        catalog.append(
            IndexEntry(
                entry_id=entry_id,
                title=entry_id,
                entry_type="scp",
                tags=f"scp anomaly containment series-{series} item article",
                url=wiki_url_for_scp(entry_id),
                priority=max(0, 18 - series),
            )
        )

    catalog.extend(
        [
            IndexEntry(
                "Site-01",
                "Secure Administration Site-01",
                "site",
                "site administration overseer council secure facility command",
                f"{BASE_URL}/secure-facilities-locations",
                82,
            ),
            IndexEntry(
                "Site-06-3",
                "Humanoid Containment Site-06-3",
                "site",
                "site humanoid containment training security",
                f"{BASE_URL}/secure-facilities-locations",
                70,
            ),
            IndexEntry(
                "Site-17",
                "Personnel Training and Humanoid Containment Site-17",
                "site",
                "site personnel training humanoid containment",
                f"{BASE_URL}/secure-facilities-locations",
                78,
            ),
            IndexEntry(
                "Site-19",
                "Primary Containment Site-19",
                "site",
                "site primary containment research storage largest",
                f"{BASE_URL}/secure-facilities-locations",
                95,
            ),
            IndexEntry(
                "Site-64",
                "Research, Storage, and Containment Site-64",
                "site",
                "site research storage containment north america",
                f"{BASE_URL}/secure-facilities-locations",
                68,
            ),
            IndexEntry(
                "Area-12",
                "Biological Research Area-12",
                "site",
                "area biological research biohazard containment",
                f"{BASE_URL}/secure-facilities-locations",
                65,
            ),
            IndexEntry(
                "Area-14",
                "Armed Biological Containment Area-14",
                "site",
                "area armed biological containment remote",
                f"{BASE_URL}/secure-facilities-locations",
                64,
            ),
            IndexEntry(
                "DOC-ABOUT",
                "About The SCP Foundation",
                "document",
                "orientation foundation overview document introduction",
                f"{BASE_URL}/about-the-scp-foundation",
                90,
            ),
            IndexEntry(
                "DOC-CLASSES",
                "Object Classes",
                "document",
                "object class safe euclid keter thaumiel apollyon explained",
                f"{BASE_URL}/object-classes",
                96,
            ),
            IndexEntry(
                "DOC-CLEARANCE",
                "Security Clearance Levels",
                "document",
                "security clearance level personnel document",
                f"{BASE_URL}/security-clearance-levels",
                88,
            ),
            IndexEntry(
                "DOC-FACILITIES",
                "Secure Facilities Locations",
                "document",
                "facility site area location document",
                f"{BASE_URL}/secure-facilities-locations",
                86,
            ),
            IndexEntry(
                "DOC-GOI",
                "Groups of Interest",
                "document",
                "groups of interest goi organization document",
                f"{BASE_URL}/groups-of-interest",
                84,
            ),
            IndexEntry(
                "DOC-ANOMALOUS-ITEMS",
                "Log Of Anomalous Items",
                "document",
                "log anomalous items document archive",
                f"{BASE_URL}/log-of-anomalous-items",
                80,
            ),
            IndexEntry(
                "DOC-EXTRANORMAL-EVENTS",
                "Log Of Extranormal Events",
                "document",
                "log extranormal events incident document",
                f"{BASE_URL}/log-of-extranormal-events",
                77,
            ),
            IndexEntry(
                "DOC-PERSONNEL",
                "Personnel And Character Dossier",
                "document",
                "personnel dossier character staff researcher document",
                f"{BASE_URL}/personnel-and-character-dossier",
                76,
            ),
            IndexEntry(
                "AUDIO-HUB",
                "Audio Adaptations",
                "audio",
                "audio adaptation file recording spoken archive",
                f"{BASE_URL}/audio-adaptations",
                92,
            ),
            IndexEntry(
                "AUDIO-FOUNDATION-AFTER-MIDNIGHT",
                "Foundation After Midnight Radio",
                "audio",
                "audio radio broadcast file foundation after midnight",
                f"{BASE_URL}/foundation-after-midnight-radio-hub",
                82,
            ),
            IndexEntry(
                "AUDIO-SCP-087",
                "SCP-087 Exploration Audio",
                "audio",
                "audio exploration recording stairwell scp-087",
                f"{BASE_URL}/scp-087",
                79,
            ),
            IndexEntry(
                "AUDIO-SCP-093",
                "SCP-093 Exploration Recordings",
                "audio",
                "audio exploration recording red sea object scp-093",
                f"{BASE_URL}/scp-093",
                76,
            ),
        ]
    )
    return catalog


class SearchDatabase:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or index_path()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def connection(self) -> Iterable[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    url TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS content_cache (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entries_type_priority
                    ON entries(type, priority DESC, id);
                """
            )
            self._ensure_fts(connection)

    def _ensure_fts(self, connection: sqlite3.Connection) -> bool:
        try:
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS entry_fts USING fts5(
                    id UNINDEXED,
                    title,
                    tags,
                    type,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('fts5_enabled', '1')"
            )
            return True
        except sqlite3.OperationalError:
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('fts5_enabled', '0')"
            )
            return False

    def fts_enabled(self, connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'fts5_enabled'"
        ).fetchone()
        return row is not None and row["value"] == "1"

    def count_entries(self) -> int:
        with self.connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM entries").fetchone()
            return int(row["total"] if row else 0)

    def index_version(self) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'index_version'"
            ).fetchone()
            if row is None:
                return 0
            try:
                return int(row["value"])
            except ValueError:
                return 0

    def needs_seed(self) -> bool:
        return self.count_entries() < 1000 or self.index_version() < INDEX_VERSION

    def seed(self, progress_callback=None) -> int:
        entries = seed_catalog()
        total = len(entries)
        batch_size = 500
        now = utc_now()
        inserted = 0

        with self.connection() as connection:
            fts_enabled = self._ensure_fts(connection)
            for start in range(0, total, batch_size):
                batch = entries[start : start + batch_size]
                with connection:
                    connection.executemany(
                        """
                        INSERT OR REPLACE INTO entries
                            (id, title, type, tags, url, priority, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                entry.entry_id,
                                entry.title,
                                entry.entry_type,
                                entry.tags,
                                entry.url,
                                entry.priority,
                                now,
                            )
                            for entry in batch
                        ],
                    )
                inserted += len(batch)
                if progress_callback:
                    progress_callback("Indexing metadata", inserted, total)

            with connection:
                if fts_enabled:
                    if progress_callback:
                        progress_callback("Building search vectors", total, total)
                    connection.execute("DELETE FROM entry_fts")
                    connection.execute(
                        """
                        INSERT INTO entry_fts(id, title, tags, type)
                        SELECT id, title, tags, type
                        FROM entries
                        """
                    )
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES('index_version', ?)",
                    (str(INDEX_VERSION),),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES('seeded_at', ?)",
                    (now,),
                )
                connection.execute("PRAGMA optimize")
        return total

    def search(self, query: str, category: str, limit: int = SEARCH_LIMIT) -> list[SearchResult]:
        query = query.strip()
        tokens = tokenize(query)
        with self.connection() as connection:
            if not tokens:
                return self._default_results(connection, category, limit)

            fts_bonus: dict[str, float] = {}
            if self.fts_enabled(connection):
                fts_terms = [token for token in tokens if token not in GENERIC_QUERY_TERMS] or tokens
                fts_query = " OR ".join(f"{token}*" for token in fts_terms[:8])
                try:
                    sql = """
                        SELECT e.*, bm25(entry_fts, 1.8, 2.4, 0.6) AS rank
                        FROM entry_fts
                        JOIN entries e ON e.id = entry_fts.id
                        WHERE entry_fts MATCH ?
                    """
                    params: list[object] = [fts_query]
                    if category != "all":
                        sql += " AND e.type = ?"
                        params.append(category)
                    sql += " ORDER BY rank LIMIT 500"
                    for row in connection.execute(sql, params):
                        fts_bonus[row["id"]] = max(12.0, min(90.0, 70.0 + (-float(row["rank"]) * 12.0)))
                except sqlite3.OperationalError:
                    fts_bonus = {}

            candidates = self._candidate_rows(connection, category, fts_bonus, tokens)
            results: list[SearchResult] = []
            for row in candidates:
                score = self._score_row(row, query, tokens, fts_bonus.get(row["id"], 0.0))
                if score <= 0:
                    continue
                results.append(
                    SearchResult(
                        entry_id=row["id"],
                        title=row["title"],
                        entry_type=row["type"],
                        tags=row["tags"],
                        url=row["url"],
                        score=score,
                    )
                )

            results.sort(key=lambda item: (-item.score, _type_sort(item.entry_type), item.entry_id))
            return results[:limit]

    def _default_results(
        self, connection: sqlite3.Connection, category: str, limit: int
    ) -> list[SearchResult]:
        sql = "SELECT * FROM entries"
        params: list[object] = []
        if category != "all":
            sql += " WHERE type = ?"
            params.append(category)
        sql += " ORDER BY priority DESC, id ASC LIMIT ?"
        params.append(limit)
        rows = connection.execute(sql, params).fetchall()
        return [
            SearchResult(
                entry_id=row["id"],
                title=row["title"],
                entry_type=row["type"],
                tags=row["tags"],
                url=row["url"],
                score=float(row["priority"]),
            )
            for row in rows
        ]

    def _candidate_rows(
        self,
        connection: sqlite3.Connection,
        category: str,
        fts_bonus: dict[str, float],
        tokens: list[str],
    ) -> list[sqlite3.Row]:
        rows_by_id: dict[str, sqlite3.Row] = {}
        if fts_bonus:
            placeholders = ",".join("?" for _ in fts_bonus)
            sql = f"SELECT * FROM entries WHERE id IN ({placeholders})"
            for row in connection.execute(sql, list(fts_bonus)):
                rows_by_id[row["id"]] = row

        useful_tokens = [token for token in tokens if token not in GENERIC_QUERY_TERMS] or tokens
        like_clauses: list[str] = []
        like_params: list[object] = []
        for token in useful_tokens[:5]:
            like_clauses.append("(id LIKE ? OR title LIKE ? OR tags LIKE ?)")
            like_value = f"%{token}%"
            like_params.extend([like_value, like_value, like_value])

        if like_clauses:
            sql = "SELECT * FROM entries WHERE "
            params: list[object] = []
            if category != "all":
                sql += "type = ? AND "
                params.append(category)
            sql += "(" + " OR ".join(like_clauses) + ")"
            sql += " ORDER BY priority DESC, id ASC LIMIT 1200"
            for row in connection.execute(sql, params + like_params):
                rows_by_id.setdefault(row["id"], row)

        sql = "SELECT * FROM entries"
        params: list[object] = []
        if category != "all":
            sql += " WHERE type = ?"
            params.append(category)
        sql += " ORDER BY priority DESC, id ASC LIMIT 350"
        for row in connection.execute(sql, params):
            rows_by_id.setdefault(row["id"], row)
        return list(rows_by_id.values())

    def _score_row(
        self, row: sqlite3.Row, raw_query: str, tokens: list[str], fts_bonus: float
    ) -> float:
        entry_id = row["id"]
        title = row["title"]
        tags = row["tags"]
        priority = int(row["priority"])

        id_norm = normalize_text(entry_id)
        id_compact = id_norm.replace(" ", "")
        id_digits = "".join(ch for ch in entry_id if ch.isdigit())
        id_number = int(id_digits) if id_digits else None
        title_norm = normalize_text(title)
        tag_norm = normalize_text(tags)
        all_text = f"{id_norm} {title_norm} {tag_norm}"
        words = set(all_text.split())
        tag_words = set(tag_norm.split())
        query_norm = normalize_text(raw_query)
        query_compact = query_norm.replace(" ", "")

        score = fts_bonus + min(priority, 100) * 0.18

        if query_compact and query_compact == id_compact:
            score += 260
        elif query_compact and id_compact.startswith(query_compact):
            score += 145
        elif query_norm and query_norm in title_norm:
            score += 95
        elif query_norm and query_norm in tag_norm:
            score += 60

        missed = 0
        for token in tokens:
            token_score = 0.0
            if token.isdigit() and id_number is not None:
                token_number = int(token)
                if token_number == id_number:
                    token_score = max(token_score, 260)
                elif id_digits.startswith(token):
                    token_score = max(token_score, 72)
            if token == id_norm or token == id_compact:
                token_score = max(token_score, 150)
            if token and id_compact.startswith(token) and token not in GENERIC_QUERY_TERMS:
                token_score = max(token_score, 115)
            if token in id_norm.split():
                token_score = max(token_score, 115)
            if token in title_norm.split():
                token_score = max(token_score, 90)
            if token in tag_words:
                token_score = max(token_score, 78)
            if token in title_norm:
                token_score = max(token_score, 52)
            if token in tag_norm:
                token_score = max(token_score, 44)
            if any(tag.startswith(token) for tag in tag_words):
                token_score = max(token_score, 38)

            if token_score == 0 and len(token) >= 3:
                best_ratio = 0.0
                for word in words:
                    if abs(len(word) - len(token)) > max(3, len(token) // 2):
                        continue
                    ratio = SequenceMatcher(None, token, word).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                if best_ratio >= 0.86:
                    token_score = 42 * best_ratio
                elif best_ratio >= 0.74:
                    token_score = 24 * best_ratio

            if token_score == 0:
                missed += 1
            score += token_score

        if missed == len(tokens):
            return 0.0
        if missed:
            score -= missed * 22
        if row["type"] == "scp" and any(token.isdigit() for token in tokens):
            score += 18
        return round(score, 2)

    def get_entry(self, entry_id: str) -> IndexEntry | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
            if row is None:
                return None
            return IndexEntry(row["id"], row["title"], row["type"], row["tags"], row["url"], row["priority"])

    def all_entries(self) -> list[IndexEntry]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM entries ORDER BY priority DESC, id ASC"
            ).fetchall()
            return [
                IndexEntry(row["id"], row["title"], row["type"], row["tags"], row["url"], row["priority"])
                for row in rows
            ]

    def get_cached_content(self, entry_id: str) -> tuple[str, str, str] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT title, content, fetched_at FROM content_cache WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if row is None:
                return None
            return row["title"], row["content"], row["fetched_at"]

    def save_content(self, entry: IndexEntry, title: str, content: str, source: str) -> None:
        title = title.strip() or entry.title
        fetched_at = utc_now()
        tags = entry.tags
        with self.connection() as connection:
            fts_enabled = self.fts_enabled(connection)
            with connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO content_cache(id, title, content, source, fetched_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (entry.entry_id, title, content, source, fetched_at),
                )
                if title != entry.title:
                    connection.execute(
                        """
                        UPDATE entries
                        SET title = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (title, fetched_at, entry.entry_id),
                    )
                    if fts_enabled:
                        connection.execute("DELETE FROM entry_fts WHERE id = ?", (entry.entry_id,))
                        connection.execute(
                            "INSERT INTO entry_fts(id, title, tags, type) VALUES (?, ?, ?, ?)",
                            (entry.entry_id, title, tags, entry.entry_type),
                        )


def _type_sort(entry_type: str) -> int:
    return {"scp": 0, "site": 1, "document": 2, "audio": 3}.get(entry_type, 9)


def prepare_search_documents(entries: Iterable[IndexEntry]) -> SearchCorpus:
    documents = tuple(SearchDocument.from_entry(entry) for entry in entries)
    mutable_token_map: dict[str, set[int]] = {}
    for index, document in enumerate(documents):
        for term in _document_index_terms(document):
            mutable_token_map.setdefault(term, set()).add(index)

    token_map = {term: frozenset(indexes) for term, indexes in mutable_token_map.items()}
    sorted_indexes: dict[str, tuple[int, ...]] = {}
    popular_indexes: dict[str, tuple[int, ...]] = {}
    for category in CATEGORY_LABELS:
        if category == "all":
            indexes = range(len(documents))
        else:
            indexes = (index for index, document in enumerate(documents) if document.entry_type == category)
        ordered = tuple(
            sorted(
                indexes,
                key=lambda item: (
                    -documents[item].priority,
                    _type_sort(documents[item].entry_type),
                    documents[item].entry_id,
                ),
            )
        )
        sorted_indexes[category] = ordered
        popular_indexes[category] = tuple(
            index for index in ordered if documents[index].priority >= 74
        )[:140]
    return SearchCorpus(documents, token_map, sorted_indexes, popular_indexes)


def search_documents(
    corpus: SearchCorpus,
    query: str,
    category: str,
    limit: int = SEARCH_LIMIT,
) -> list[SearchResult]:
    query = query.strip()
    tokens = tokenize(query)
    documents = corpus.documents
    sorted_indexes = corpus.sorted_indexes.get(category, corpus.sorted_indexes["all"])
    if not tokens:
        return [
            SearchResult(
                entry_id=document.entry_id,
                title=document.title,
                entry_type=document.entry_type,
                tags=document.tags,
                url=document.url,
                score=float(document.priority),
            )
            for document in (documents[index] for index in sorted_indexes[:limit])
        ]

    useful_tokens = [token for token in tokens if token not in GENERIC_QUERY_TERMS] or tokens
    allowed = set(sorted_indexes) if category != "all" else None
    candidate_indexes: set[int] = set(corpus.popular_indexes.get(category, ()))
    for token in useful_tokens:
        candidate_indexes.update(corpus.token_map.get(token, ()))
        if token.isdigit():
            candidate_indexes.update(corpus.token_map.get(str(int(token)), ()))
    if allowed is not None:
        candidate_indexes.intersection_update(allowed)

    results: list[SearchResult] = []
    for index in candidate_indexes:
        document = documents[index]
        score = _score_document(document, query, tokens)
        if score <= 0:
            continue
        results.append(
            SearchResult(
                entry_id=document.entry_id,
                title=document.title,
                entry_type=document.entry_type,
                tags=document.tags,
                url=document.url,
                score=score,
            )
        )

    results.sort(key=lambda item: (-item.score, _type_sort(item.entry_type), item.entry_id))
    return results[:limit]


def _document_index_terms(document: SearchDocument) -> set[str]:
    terms = set(document.words)
    if document.id_digits:
        terms.add(document.id_digits)
        terms.add(str(int(document.id_digits)))
    terms.add(document.id_compact)

    expanded: set[str] = set()
    for term in terms:
        if not term or term in GENERIC_QUERY_TERMS:
            continue
        expanded.add(term)
        if term.isdigit():
            for length in range(2, min(len(term), 8) + 1):
                expanded.add(term[:length])
        elif len(term) >= 3:
            for length in range(3, min(len(term), 10) + 1):
                expanded.add(term[:length])
    return expanded


def _score_document(document: SearchDocument, raw_query: str, tokens: list[str]) -> float:
    query_norm = normalize_text(raw_query)
    query_compact = query_norm.replace(" ", "")
    score = min(document.priority, 100) * 0.22

    if query_compact and query_compact == document.id_compact:
        score += 280
    elif query_norm and query_norm in document.title_norm:
        score += 105
    elif query_norm and query_norm in document.tag_norm:
        score += 68

    missed = 0
    for token in tokens:
        token_score = 0.0
        if token.isdigit() and document.id_number is not None:
            token_number = int(token)
            if token_number == document.id_number:
                token_score = max(token_score, 275)
            elif document.id_digits.startswith(token):
                token_score = max(token_score, 76)

        if token == document.id_norm or token == document.id_compact:
            token_score = max(token_score, 155)
        if token and document.id_compact.startswith(token) and token not in GENERIC_QUERY_TERMS:
            token_score = max(token_score, 112)
        if token in document.id_norm.split():
            token_score = max(token_score, 110)
        if token in document.title_norm.split():
            token_score = max(token_score, 94)
        if token in document.tag_words:
            token_score = max(token_score, 82)
        if token in document.title_norm:
            token_score = max(token_score, 55)
        if token in document.tag_norm:
            token_score = max(token_score, 47)
        if any(tag.startswith(token) for tag in document.tag_words):
            token_score = max(token_score, 40)

        if token_score == 0 and len(token) >= 3 and document.priority >= 70:
            best_ratio = 0.0
            for word in document.words:
                if not word or word[0] != token[0]:
                    continue
                if abs(len(word) - len(token)) > max(3, len(token) // 2):
                    continue
                ratio = SequenceMatcher(None, token, word).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
            if best_ratio >= 0.86:
                token_score = 44 * best_ratio
            elif best_ratio >= 0.74:
                token_score = 26 * best_ratio

        if token_score == 0:
            missed += 1
        score += token_score

    if missed == len(tokens):
        return 0.0
    if missed:
        score -= missed * 24
    if document.entry_type == "scp" and any(token.isdigit() for token in tokens):
        score += 18
    return round(score, 2)


class WikiTextFallbackParser(HTMLParser):
    block_tags = {"p", "blockquote", "li", "h1", "h2", "h3", "h4", "pre", "br"}
    skip_tags = {"script", "style", "noscript", "iframe"}
    skip_classes = {"footer-wikiwalk-nav", "licensebox", "page-tags", "rate-box-with-credit-button"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.content_parts: list[str] = []
        self._capture_title = False
        self._title_depth = 0
        self._capture_content = False
        self._content_depth = 0
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        classes = set(attr_map.get("class", "").split())
        element_id = attr_map.get("id", "")

        if tag in self.skip_tags or classes.intersection(self.skip_classes):
            self._skip_depth += 1
            return

        if element_id == "page-title":
            self._capture_title = True
            self._title_depth = 1
            return
        if self._capture_title:
            self._title_depth += 1

        if element_id == "page-content":
            self._capture_content = True
            self._content_depth = 1
            return
        if self._capture_content:
            self._content_depth += 1
            if tag in self.block_tags:
                self.content_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            self._skip_depth -= 1
            return

        if self._capture_title:
            self._title_depth -= 1
            if self._title_depth <= 0:
                self._capture_title = False

        if self._capture_content:
            if tag in self.block_tags:
                self.content_parts.append("\n")
            self._content_depth -= 1
            if self._content_depth <= 0:
                self._capture_content = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._capture_title:
            self.title_parts.append(text)
        if self._capture_content:
            self.content_parts.append(text + " ")

    def result(self) -> tuple[str, str]:
        title = _clean_inline(" ".join(self.title_parts))
        content = _clean_content("".join(self.content_parts))
        return title, content


def fetch_wiki_page(entry: IndexEntry) -> tuple[str, str, str]:
    request = Request(entry.url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        raw_html = response.read().decode(charset, errors="replace")
        final_url = response.url
    title, content = parse_wiki_html(raw_html, entry)
    if not content:
        raise RuntimeError("No readable page content was found.")
    return title or entry.title, content, final_url


def parse_wiki_html(raw_html: str, entry: IndexEntry) -> tuple[str, str]:
    if BeautifulSoup is not None:
        soup = BeautifulSoup(raw_html, "html.parser")
        title_node = soup.select_one("#page-title")
        title = title_node.get_text(" ", strip=True) if title_node else entry.title
        content_node = soup.select_one("#page-content") or soup.body or soup
        for node in content_node.select(
            "script, style, iframe, .footer-wikiwalk-nav, .licensebox, .page-tags, .rate-box-with-credit-button"
        ):
            node.decompose()
        blocks: list[str] = []
        for node in content_node.find_all(["p", "blockquote", "li", "h1", "h2", "h3", "h4", "pre"]):
            text = _clean_inline(node.get_text(" ", strip=True))
            if _is_useful_content_line(text):
                blocks.append(text)
        return _clean_inline(title), _clean_content("\n\n".join(blocks))

    parser = WikiTextFallbackParser()
    parser.feed(raw_html)
    return parser.result()


def _clean_inline(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _clean_content(value: str) -> str:
    lines = []
    for raw_line in value.splitlines():
        line = _clean_inline(raw_line)
        if _is_useful_content_line(line):
            lines.append(line)
    content = "\n\n".join(lines)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _is_useful_content_line(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    blocked_prefixes = ("rating:", "+", "page tags", "credit", "license")
    if lowered.startswith(blocked_prefixes):
        return False
    return True


class SearchSignals(QObject):
    finished = pyqtSignal(int, object, str, float)


class SearchTask(QRunnable):
    def __init__(
        self,
        corpus: SearchCorpus | None,
        token: int,
        query: str,
        category: str,
    ) -> None:
        super().__init__()
        self.corpus = corpus
        self.token = token
        self.query = query
        self.category = category
        self.signals = SearchSignals()

    def run(self) -> None:
        started = time.perf_counter()
        try:
            if self.corpus is None:
                results = []
                message = "Index warming"
            else:
                results = search_documents(self.corpus, self.query, self.category)
                message = f"{len(results)} ranked results"
        except Exception as exc:
            results = []
            message = f"Search failed: {exc}"
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.signals.finished.emit(self.token, results, message, elapsed_ms)


class LoadIndexSignals(QObject):
    finished = pyqtSignal(object, int)
    failed = pyqtSignal(str)


class LoadIndexTask(QRunnable):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.signals = LoadIndexSignals()

    def run(self) -> None:
        try:
            database = SearchDatabase(self.db_path)
            entries = database.all_entries()
            corpus = prepare_search_documents(entries)
            self.signals.finished.emit(corpus, len(corpus.documents))
        except Exception:
            self.signals.failed.emit(traceback.format_exc(limit=4))


class SeedSignals(QObject):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(int)
    failed = pyqtSignal(str)


class SeedTask(QRunnable):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.signals = SeedSignals()

    def run(self) -> None:
        try:
            database = SearchDatabase(self.db_path)
            database.initialize()
            count = database.seed(self.signals.progress.emit)
            self.signals.finished.emit(count)
        except Exception:
            self.signals.failed.emit(traceback.format_exc(limit=4))


class DetailSignals(QObject):
    finished = pyqtSignal(int, object)


class DetailTask(QRunnable):
    def __init__(self, db_path: Path, token: int, entry_id: str, force_refresh: bool = False) -> None:
        super().__init__()
        self.db_path = db_path
        self.token = token
        self.entry_id = entry_id
        self.force_refresh = force_refresh
        self.signals = DetailSignals()

    def run(self) -> None:
        database = SearchDatabase(self.db_path)
        entry = database.get_entry(self.entry_id)
        if entry is None:
            self.signals.finished.emit(
                self.token,
                DetailPayload(
                    self.entry_id,
                    self.entry_id,
                    "unknown",
                    "",
                    "",
                    "The selected record no longer exists in the local index.",
                    "missing",
                    utc_now(),
                    "Record missing",
                ),
            )
            return

        if not self.force_refresh:
            cached = database.get_cached_content(entry.entry_id)
            if cached is not None:
                title, content, fetched_at = cached
                self.signals.finished.emit(
                    self.token,
                    DetailPayload(
                        entry.entry_id,
                        title,
                        entry.entry_type,
                        entry.tags,
                        entry.url,
                        content,
                        "cache",
                        fetched_at,
                    ),
                )
                return

        try:
            title, content, source = fetch_wiki_page(entry)
            database.save_content(entry, title, content, source)
            self.signals.finished.emit(
                self.token,
                DetailPayload(
                    entry.entry_id,
                    title,
                    entry.entry_type,
                    entry.tags,
                    source,
                    content,
                    "live",
                    utc_now(),
                ),
            )
        except (HTTPError, URLError, TimeoutError, RuntimeError, OSError) as exc:
            fallback = (
                f"No cached dossier is available for {entry.entry_id}.\n\n"
                f"Live retrieval did not complete: {exc}\n\n"
                f"Known metadata:\n"
                f"Title: {entry.title}\n"
                f"Type: {CATEGORY_LABELS.get(entry.entry_type, entry.entry_type)}\n"
                f"Tags: {entry.tags}\n"
                f"Source: {entry.url}"
            )
            self.signals.finished.emit(
                self.token,
                DetailPayload(
                    entry.entry_id,
                    entry.title,
                    entry.entry_type,
                    entry.tags,
                    entry.url,
                    fallback,
                    "offline",
                    utc_now(),
                    str(exc),
                ),
            )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.db_path = index_path()
        self.database = SearchDatabase(self.db_path)
        self.database.initialize()
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(max(4, self.thread_pool.maxThreadCount()))
        self.search_token = 0
        self.detail_token = 0
        self.current_entry_id = ""
        self.search_corpus: SearchCorpus | None = None

        self.setWindowTitle(APP_NAME)
        self.resize(1380, 840)
        self.setMinimumSize(1040, 660)

        self.search_timer = QTimer(self)
        self.search_timer.setInterval(75)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.start_search)

        self._build_ui()
        self._apply_theme("Amber")
        self._setup_shortcuts()
        self._maybe_seed_index()
        self.schedule_search()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._search_panel())
        splitter.addWidget(self._detail_panel())
        splitter.setSizes([460, 900])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(root)

    def _header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("header")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)

        title_box = QVBoxLayout()
        self.app_title = QLabel("SCP FOUNDATION // RESEARCH TERMINAL")
        self.app_title.setObjectName("appTitle")
        self.app_subtitle = QLabel("LOCAL METADATA INDEX + LAZY DOSSIER CACHE")
        self.app_subtitle.setObjectName("appSubtitle")
        title_box.addWidget(self.app_title)
        title_box.addWidget(self.app_subtitle)

        self.status_label = QLabel("Initializing local index")
        self.status_label.setObjectName("statusPill")
        self.status_label.setMinimumWidth(240)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.currentTextChanged.connect(self._apply_theme)

        layout.addLayout(title_box, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Theme"))
        layout.addWidget(self.theme_combo)
        return frame

    def _search_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        heading = QLabel("INDEX QUERY")
        heading.setObjectName("sectionHeading")

        self.category_tabs = QTabBar()
        self.category_tabs.setExpanding(False)
        for key, label in CATEGORY_LABELS.items():
            self.category_tabs.addTab(label)
            self.category_tabs.setTabData(self.category_tabs.count() - 1, key)
        self.category_tabs.currentChanged.connect(lambda _: self.schedule_search())

        self.search_input = QLineEdit()
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText("Search SCP number, title, tag, object class, or document...")
        self.search_input.textChanged.connect(lambda _: self.schedule_search())

        self.results_list = QListWidget()
        self.results_list.setObjectName("resultsList")
        self.results_list.setUniformItemSizes(False)
        self.results_list.currentItemChanged.connect(self._result_selected)

        footer = QHBoxLayout()
        self.result_count_label = QLabel("0 results")
        self.result_count_label.setObjectName("muted")
        self.search_latency_label = QLabel("search idle")
        self.search_latency_label.setObjectName("muted")
        footer.addWidget(self.result_count_label)
        footer.addStretch(1)
        footer.addWidget(self.search_latency_label)

        layout.addWidget(heading)
        layout.addWidget(self.category_tabs)
        layout.addWidget(self.search_input)
        layout.addWidget(self.results_list, 1)
        layout.addLayout(footer)
        return panel

    def _detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("viewerPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        self.detail_title = QLabel("Select a record")
        self.detail_title.setObjectName("detailTitle")
        self.detail_title.setWordWrap(True)
        self.detail_meta = QLabel("Full content is loaded only after selection.")
        self.detail_meta.setObjectName("detailMeta")
        self.detail_meta.setWordWrap(True)
        title_box.addWidget(self.detail_title)
        title_box.addWidget(self.detail_meta)

        self.refresh_detail_button = QPushButton("Refresh Detail")
        self.refresh_detail_button.setEnabled(False)
        self.refresh_detail_button.clicked.connect(lambda: self.load_detail(force_refresh=True))
        self.open_wiki_button = QPushButton("Open Wiki")
        self.open_wiki_button.setEnabled(False)
        self.open_wiki_button.clicked.connect(self.open_current_in_browser)

        button_box = QVBoxLayout()
        button_box.addWidget(self.refresh_detail_button)
        button_box.addWidget(self.open_wiki_button)

        title_row.addLayout(title_box, 1)
        title_row.addLayout(button_box)

        self.content_view = QTextBrowser()
        self.content_view.setObjectName("contentView")
        self.content_view.setOpenExternalLinks(True)
        self.content_view.setPlainText(
            "Search the local metadata index on the left. Selecting a result opens the dossier loader in "
            "a background thread and caches the page for future offline use."
        )

        bottom_row = QHBoxLayout()
        self.cache_label = QLabel(f"Index: {self.db_path}")
        self.cache_label.setObjectName("muted")
        self.cache_label.setWordWrap(True)
        self.index_progress = QProgressBar()
        self.index_progress.setRange(0, 100)
        self.index_progress.setValue(0)
        self.index_progress.setMaximumWidth(260)
        bottom_row.addWidget(self.cache_label, 1)
        bottom_row.addWidget(self.index_progress)

        layout.addLayout(title_row)
        layout.addWidget(self.content_view, 1)
        layout.addLayout(bottom_row)
        return panel

    def _setup_shortcuts(self) -> None:
        focus_search = QAction(self)
        focus_search.setShortcut(QKeySequence.StandardKey.Find)
        focus_search.triggered.connect(lambda: self.search_input.setFocus())
        self.addAction(focus_search)

        refresh = QAction(self)
        refresh.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh.triggered.connect(lambda: self.load_detail(force_refresh=True))
        self.addAction(refresh)

    def _apply_theme(self, name: str) -> None:
        theme = THEMES.get(name, THEMES["Amber"])
        accent = theme["accent"]
        accent2 = theme["accent2"]
        alert = theme["alert"]
        selection = theme["selection"]
        QApplication.instance().setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background: #080c10;
                color: #d9e1ea;
            }}
            QFrame#header, QFrame#panel, QFrame#viewerPanel {{
                background: #101720;
                border: 1px solid #263442;
                border-radius: 6px;
            }}
            QLabel#appTitle {{
                color: #f3f6f8;
                font-size: 18px;
                font-weight: 800;
                letter-spacing: 0px;
            }}
            QLabel#appSubtitle, QLabel#muted {{
                color: #7f8b98;
                font-size: 11px;
                letter-spacing: 0px;
            }}
            QLabel#statusPill {{
                background: #0b1118;
                border: 1px solid {accent};
                border-radius: 4px;
                color: {accent2};
                padding: 7px 10px;
                font-weight: 700;
            }}
            QLabel#sectionHeading {{
                color: {accent};
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0px;
            }}
            QLabel#detailTitle {{
                color: #f6f8fb;
                font-size: 24px;
                font-weight: 800;
                letter-spacing: 0px;
            }}
            QLabel#detailMeta {{
                color: {accent2};
                font-size: 13px;
                font-weight: 600;
            }}
            QLineEdit, QComboBox {{
                background: #0b1118;
                border: 1px solid #304156;
                border-radius: 5px;
                color: #e6edf3;
                padding: 9px;
                selection-background-color: {selection};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QListWidget, QTextBrowser {{
                background: #0b1118;
                border: 1px solid #263442;
                border-radius: 5px;
                color: #d9e1ea;
                padding: 6px;
            }}
            QListWidget#resultsList::item {{
                border-bottom: 1px solid #172331;
                padding: 8px;
            }}
            QListWidget#resultsList::item:selected {{
                background: {selection};
                color: #ffffff;
            }}
            QTabBar::tab {{
                background: #0b1118;
                border: 1px solid #263442;
                color: #aab6c2;
                padding: 8px 12px;
                margin-right: 4px;
                border-radius: 4px;
            }}
            QTabBar::tab:selected {{
                color: #ffffff;
                background: #182331;
                border-color: {accent};
            }}
            QPushButton {{
                background: #182331;
                border: 1px solid #3a4d63;
                border-radius: 5px;
                color: #e6edf3;
                padding: 10px 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: #223145;
                border-color: {accent};
            }}
            QPushButton:disabled {{
                color: #65717f;
                background: #101720;
                border-color: #263442;
            }}
            QProgressBar {{
                background: #0b1118;
                border: 1px solid #263442;
                border-radius: 5px;
                color: #d9e1ea;
                height: 18px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {alert};
                border-radius: 4px;
            }}
            QScrollBar:vertical {{
                background: #0b1118;
                width: 12px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #263442;
                border-radius: 5px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            """
        )

    def _maybe_seed_index(self) -> None:
        if not self.database.needs_seed():
            count = self.database.count_entries()
            self.index_progress.setValue(65)
            self.status_label.setText(f"Loading {count:,} metadata records")
            self._load_index_async()
            return

        self.status_label.setText("Warming metadata index")
        task = SeedTask(self.db_path)
        task.signals.progress.connect(self._seed_progress)
        task.signals.finished.connect(self._seed_finished)
        task.signals.failed.connect(self._seed_failed)
        self.thread_pool.start(task)

    def _seed_progress(self, message: str, current: int, total: int) -> None:
        self.status_label.setText(f"{message}: {current:,}/{total:,}")
        if total:
            self.index_progress.setValue(int((current / total) * 100))

    def _seed_finished(self, count: int) -> None:
        self.index_progress.setValue(75)
        self.status_label.setText(f"Preparing {count:,} searchable records")
        self._load_index_async()

    def _load_index_async(self) -> None:
        task = LoadIndexTask(self.db_path)
        task.signals.finished.connect(self._index_loaded)
        task.signals.failed.connect(self._index_load_failed)
        self.thread_pool.start(task)

    def _index_loaded(self, corpus: SearchCorpus, count: int) -> None:
        self.search_corpus = corpus
        self.index_progress.setValue(100)
        self.status_label.setText(f"Index ready: {count:,} records")
        self.schedule_search()

    def _index_load_failed(self, message: str) -> None:
        self.status_label.setText("Index load failed")
        QMessageBox.warning(self, APP_NAME, f"Unable to load the local index:\n\n{message}")

    def _seed_failed(self, message: str) -> None:
        self.status_label.setText("Index seed failed")
        QMessageBox.warning(self, APP_NAME, f"Unable to build the local index:\n\n{message}")

    def current_category(self) -> str:
        index = self.category_tabs.currentIndex()
        value = self.category_tabs.tabData(index)
        return str(value or "all")

    def schedule_search(self) -> None:
        self.search_timer.start()

    def start_search(self) -> None:
        self.search_token += 1
        token = self.search_token
        query = self.search_input.text()
        category = self.current_category()
        self.search_latency_label.setText("searching...")
        task = SearchTask(self.search_corpus, token, query, category)
        task.signals.finished.connect(self._search_finished)
        self.thread_pool.start(task)

    def _search_finished(
        self, token: int, results: list[SearchResult], message: str, elapsed_ms: float
    ) -> None:
        if token != self.search_token:
            return

        previous_id = self.current_entry_id
        self.results_list.blockSignals(True)
        self.results_list.clear()
        restore_row = -1
        for row_index, result in enumerate(results):
            item = QListWidgetItem(self._format_result(result))
            item.setData(Qt.ItemDataRole.UserRole, result.entry_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, result.url)
            item.setToolTip(f"{result.entry_id} | {result.tags}")
            item.setSizeHint(QSize(0, 58))
            self.results_list.addItem(item)
            if result.entry_id == previous_id:
                restore_row = row_index
        if restore_row >= 0:
            self.results_list.setCurrentRow(restore_row)
        self.results_list.blockSignals(False)

        self.result_count_label.setText(message)
        self.search_latency_label.setText(f"{elapsed_ms:.1f} ms")
        if elapsed_ms <= 50:
            self.status_label.setText("Search nominal")
        elif elapsed_ms <= 120:
            self.status_label.setText("Search responsive")
        else:
            self.status_label.setText("Search completed")

    def _format_result(self, result: SearchResult) -> str:
        score = max(0, min(999, int(round(result.score))))
        tags = ", ".join(result.tags.split()[:8])
        label = CATEGORY_LABELS.get(result.entry_type, result.entry_type).upper()
        return f"{result.entry_id}  {result.title}\n{label} | RANK {score:03d} | {tags}"

    def _result_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        entry_id = str(current.data(Qt.ItemDataRole.UserRole))
        if not entry_id or entry_id == self.current_entry_id:
            return
        self.current_entry_id = entry_id
        self.load_detail(force_refresh=False)

    def load_detail(self, force_refresh: bool = False) -> None:
        if not self.current_entry_id:
            return
        self.detail_token += 1
        token = self.detail_token
        self.refresh_detail_button.setEnabled(False)
        self.open_wiki_button.setEnabled(False)
        self.detail_title.setText(self.current_entry_id)
        self.detail_meta.setText("Loading dossier in background...")
        self.content_view.setPlainText("Retrieving cached content or fetching the live wiki page.")
        self.status_label.setText("Loading detail")
        task = DetailTask(self.db_path, token, self.current_entry_id, force_refresh)
        task.signals.finished.connect(self._detail_finished)
        self.thread_pool.start(task)

    def _detail_finished(self, token: int, payload: DetailPayload) -> None:
        if token != self.detail_token:
            return
        self.detail_title.setText(f"{payload.entry_id}  {payload.title}")
        category = CATEGORY_LABELS.get(payload.entry_type, payload.entry_type)
        source = payload.source.upper()
        self.detail_meta.setText(
            f"{category} | {source} | {payload.fetched_at} | {payload.tags}"
        )
        self.content_view.setPlainText(payload.content)
        self.refresh_detail_button.setEnabled(True)
        self.open_wiki_button.setEnabled(bool(payload.url))
        self.status_label.setText("Detail loaded" if not payload.error else "Detail fallback loaded")

    def open_current_in_browser(self) -> None:
        if not self.current_entry_id:
            return
        entry = self.database.get_entry(self.current_entry_id)
        if entry is not None:
            webbrowser.open(entry.url)


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Local")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
