from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import HistoryItem


class AppStorage:
    def __init__(self, app_name: str = "SCP Researcher") -> None:
        base = Path.home() / "AppData" / "Local" / app_name
        self.path = base / "profile.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"favorites": [], "history": [], "redirect": True, "theme": "amber"}

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"favorites": [], "history": [], "redirect": True, "theme": "amber"}

        return {
            "favorites": list({int(item) for item in data.get("favorites", []) if str(item).isdigit()}),
            "history": data.get("history", []),
            "redirect": bool(data.get("redirect", True)),
            "theme": str(data.get("theme", "amber")),
        }

    def save(self, *, favorites: set[int], history: list[HistoryItem], redirect: bool, theme: str) -> None:
        payload = {
            "favorites": sorted(favorites),
            "history": [
                {
                    "number": item.number,
                    "opened_at": item.opened_at.isoformat(timespec="seconds"),
                    "title": item.title,
                }
                for item in history[:50]
            ],
            "redirect": redirect,
            "theme": theme,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def parse_history(items: list[dict[str, Any]]) -> list[HistoryItem]:
        parsed: list[HistoryItem] = []
        for item in items:
            try:
                opened_at = datetime.fromisoformat(str(item.get("opened_at")))
                number = int(item.get("number"))
            except (TypeError, ValueError):
                continue
            parsed.append(HistoryItem(number=number, opened_at=opened_at, title=str(item.get("title", "Uncatalogued file"))))
        return parsed
