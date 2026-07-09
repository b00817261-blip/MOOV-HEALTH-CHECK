"""The organisation: a *tree* of groups, invite links, and shared settings.

The model is recursive — there are no fixed "manager" and "employee" tiers.
Every person belongs to one group node and is either its **leader** or a
**member**:

* A leader sees their group's whole **subtree** (their group + every group
  nested under it), can create sub-groups, invite people, and change the
  group's settings — so any leader is "the boss" of their own branch.
* A member just updates their own group's tasks.

The **head of the desk** is simply the leader of the root group, so the same
code powers one person overseeing everything and a group lead overseeing three
people. Anyone a leader invites as a leader of a new sub-group becomes the boss
of that branch — "each person can start their own team".

Storage is two small JSON files next to the task data (stdlib only, no
database): ``groups.json`` (the tree) and ``settings.json`` (the desk-wide
"Where's it at?" channels the boss edits).
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path

ROOT_ID = "__root__"

# Sensible defaults for a fresh desk; the boss edits these on /settings.
DEFAULT_CHANNELS = [
    {"key": "email", "label": "Email"},
    {"key": "teams", "label": "Teams"},
    {"key": "note", "label": "Note"},
]


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "group"


def _token() -> str:
    return uuid.uuid4().hex


class Org:
    """Read/write the group tree and desk settings (thread-safe)."""

    def __init__(self, groups_path: str, settings_path: str,
                 desk_name: str = "the desk"):
        self.groups_path = Path(groups_path)
        self.settings_path = Path(settings_path)
        self.desk_name = desk_name
        self._lock = threading.Lock()

    # -- low-level load/save ------------------------------------------------
    def _load_raw(self) -> dict:
        try:
            data = json.loads(self.groups_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        groups = data.get("groups") if isinstance(data, dict) else data
        out = {}
        for g in groups or []:
            if isinstance(g, dict) and g.get("team_id"):
                out[str(g["team_id"])] = g
        return out

    def _save_raw(self, groups: dict) -> None:
        self.groups_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"groups": list(groups.values())}
        self.groups_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")

    def _ensure_root(self, groups: dict) -> dict:
        if ROOT_ID not in groups:
            groups[ROOT_ID] = {
                "team_id": ROOT_ID,
                "team_name": self.desk_name,
                "parent": None,
                "leader": "",
                "region": "",
                "allow_link": True,
                "tokens": {"leader": _token(), "member": _token()},
            }
        return groups

    # -- public reads -------------------------------------------------------
    def groups(self) -> dict:
        """All groups incl. the synthetic root, keyed by id."""
        with self._lock:
            groups = self._ensure_root(self._load_raw())
        return groups

    def real_groups(self) -> dict:
        """Every group except the synthetic root — the roster teams see."""
        return {gid: g for gid, g in self.groups().items() if gid != ROOT_ID}

    def get(self, gid: str) -> dict | None:
        return self.groups().get(gid)

    def children(self, gid: str, groups: dict | None = None) -> list:
        groups = groups if groups is not None else self.groups()
        return sorted(
            (g for g in groups.values() if g.get("parent") == gid),
            key=lambda g: g.get("team_name", "").lower(),
        )

    def subtree_ids(self, gid: str, groups: dict | None = None) -> list:
        """``gid`` and every group nested under it (depth-first)."""
        groups = groups if groups is not None else self.groups()
        out, stack = [], [gid]
        while stack:
            cur = stack.pop()
            if cur in groups and cur not in out:
                out.append(cur)
                stack.extend(c["team_id"] for c in self.children(cur, groups))
        return out

    def depth(self, gid: str, groups: dict | None = None) -> int:
        groups = groups if groups is not None else self.groups()
        d, cur = 0, groups.get(gid, {}).get("parent")
        while cur:
            d += 1
            cur = groups.get(cur, {}).get("parent")
        return d

    def resolve_token(self, token: str) -> tuple[str, str] | None:
        """An invite token -> ``(group_id, role)`` with role in leader/member."""
        if not token:
            return None
        for gid, g in self.groups().items():
            for role, tok in (g.get("tokens") or {}).items():
                if tok == token:
                    return gid, role
        return None

    # -- public writes ------------------------------------------------------
    def add_group(self, name: str, parent: str, leader: str = "",
                  region: str = "") -> dict:
        name = name.strip()
        if not name:
            raise ValueError("A group needs a name.")
        with self._lock:
            groups = self._ensure_root(self._load_raw())
            if parent not in groups:
                raise ValueError("That parent group no longer exists.")
            slug = base = _slug(name)
            n = 2
            while slug in groups:
                slug = f"{base}-{n}"
                n += 1
            node = {
                "team_id": slug,
                "team_name": name,
                "parent": parent,
                "leader": leader.strip(),
                "region": region.strip(),
                "allow_link": True,
                "tokens": {"leader": _token(), "member": _token()},
            }
            groups[slug] = node
            self._save_raw(groups)
        return node

    def update_group(self, gid: str, **fields) -> dict | None:
        allowed = {"team_name", "leader", "region", "allow_link"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"Cannot set: {', '.join(sorted(bad))}")
        with self._lock:
            groups = self._ensure_root(self._load_raw())
            g = groups.get(gid)
            if g is None:
                return None
            for k, v in fields.items():
                g[k] = v.strip() if isinstance(v, str) else v
            if not g.get("team_name"):
                raise ValueError("A group needs a name.")
            self._save_raw(groups)
            return g

    def rotate_token(self, gid: str, role: str) -> str | None:
        with self._lock:
            groups = self._ensure_root(self._load_raw())
            g = groups.get(gid)
            if g is None or role not in ("leader", "member"):
                return None
            g.setdefault("tokens", {})[role] = _token()
            self._save_raw(groups)
            return g["tokens"][role]

    def delete_group(self, gid: str) -> bool:
        """Remove a group and everything nested under it."""
        if gid == ROOT_ID:
            return False
        with self._lock:
            groups = self._ensure_root(self._load_raw())
            victims = set(self.subtree_ids(gid, groups))
            if gid not in groups:
                return False
            for v in victims:
                groups.pop(v, None)
            self._save_raw(groups)
        return True

    # -- settings -----------------------------------------------------------
    def settings(self) -> dict:
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        channels = data.get("channels")
        if not isinstance(channels, list) or not channels:
            channels = list(DEFAULT_CHANNELS)
        return {"channels": channels}

    def channels(self) -> list:
        return self.settings()["channels"]

    def save_channels(self, labels: list) -> list:
        clean = []
        seen = set()
        for label in labels:
            label = (label or "").strip()
            if not label:
                continue
            key = _slug(label)
            base, n = key, 2
            while key in seen:
                key = f"{base}-{n}"
                n += 1
            seen.add(key)
            clean.append({"key": key, "label": label})
        if not clean:
            clean = list(DEFAULT_CHANNELS)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps({"channels": clean}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        return clean
