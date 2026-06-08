from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class SCPEntry:
    scp_number: str
    title: str
    object_class: str
    description: str
    url: str
    last_updated: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SCPEntry":
        return cls(
            scp_number=str(data.get("scp_number", "")).strip(),
            title=str(data.get("title", "")).strip(),
            object_class=str(data.get("object_class", "Unknown")).strip() or "Unknown",
            description=str(data.get("description", "")).strip(),
            url=str(data.get("url", "")).strip(),
            last_updated=str(data.get("last_updated", "")).strip(),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def content_fingerprint(self) -> tuple[str, str, str]:
        return (
            self.title.strip(),
            self.object_class.strip(),
            self.description.strip(),
        )
