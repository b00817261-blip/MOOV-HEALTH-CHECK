"""Boss comments on a group's daily report.

The report assembles itself from the groups' updates; this is the other half
of the loop — the boss reads it at the end of the day and leaves a comment on
a group's card ("nice work", "chase the carrier tomorrow"), which the group
sees on their My day. Stored as one JSON file (``comments.json`` in the data
dir): ``{day: {group_id: [{by, text, at}, ...]}}``.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class CommentStore:
    """Load/save daily report comments (one JSON file, safe across threads)."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    def add(self, group_id: str, day: str, by: str, text: str) -> dict:
        text = (text or "").strip()[:500]
        if not text:
            raise ValueError("Write a comment first.")
        comment = {"by": (by or "").strip(), "text": text, "at": _now()}
        with self._lock:
            data = self._load()
            data.setdefault(day, {}).setdefault(group_id, []).append(comment)
            self._save(data)
        return comment

    def for_day(self, day: str) -> dict:
        """``{group_id: [comments]}`` for one day."""
        got = self._load().get(day, {})
        return got if isinstance(got, dict) else {}
