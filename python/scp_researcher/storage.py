from __future__ import annotations

import json
import os
from pathlib import Path

from models import SCPEntry


APP_NAME = "SCP Researcher"
DB_NAME = "scps.json"


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def database_path() -> Path:
    return app_data_dir() / DB_NAME


def ensure_storage_dir() -> None:
    app_data_dir().mkdir(parents=True, exist_ok=True)


def load_scps() -> list[SCPEntry]:
    path = database_path()
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(payload, dict):
        rows = payload.get("entries", [])
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    entries: list[SCPEntry] = []
    for row in rows:
        if isinstance(row, dict):
            entry = SCPEntry.from_dict(row)
            if entry.scp_number and entry.url:
                entries.append(entry)
    return sort_entries(entries)


def save_scps(entries: list[SCPEntry]) -> None:
    ensure_storage_dir()
    path = database_path()
    temp_path = path.with_suffix(".tmp")
    payload = {
        "entries": [entry.to_dict() for entry in sort_entries(entries)],
    }

    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def sort_entries(entries: list[SCPEntry]) -> list[SCPEntry]:
    return sorted(entries, key=lambda entry: _scp_sort_key(entry.scp_number))


def _scp_sort_key(scp_number: str) -> tuple[int, str]:
    digits = "".join(ch for ch in scp_number if ch.isdigit())
    if digits:
        return int(digits), scp_number
    return 999999, scp_number
