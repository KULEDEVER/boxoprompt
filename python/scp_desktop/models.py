from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ScpEntry:
    number: int
    title: str
    description: str
    object_class: str = "Pending"
    tags: tuple[str, ...] = ()
    available: bool = True
    fetched_at: str = ""

    @property
    def code(self) -> str:
        return f"SCP-{self.number:03d}"


@dataclass(frozen=True)
class HistoryItem:
    number: int
    opened_at: datetime
    title: str = "Uncatalogued file"

    @property
    def code(self) -> str:
        return f"SCP-{self.number:03d}"
