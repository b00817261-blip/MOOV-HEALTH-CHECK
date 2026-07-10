"""Email accounts with a verification code — so people keep their identity.

The org (groups, invites, roles) is unchanged; this adds a durable record of
*who a person is* keyed by their email address. When someone signs in with
their email and confirms the six-digit code we send, we look up their account
and restore their name, group and leader status — so a returning user, even on
a new device, lands back exactly where they were.

Storage is a single JSON file (``accounts.json`` in the data dir), in keeping
with the zero-dependency, no-database design. Point the data dir at a
persistent disk (or a shared drive) and the accounts travel with it.

Verification codes are generated with :mod:`secrets`; whether they reach the
person by email or are shown on screen is decided in the web layer.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_TTL_MINUTES = 15


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AccountStore:
    """Load/save email accounts (one JSON file, safe across threads)."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()

    # -- reading ------------------------------------------------------------
    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, email: str) -> dict | None:
        return self._load().get(normalize_email(email))

    def head_email(self) -> str | None:
        """The email of the registered head of the desk, if any."""
        for email, acct in self._load().items():
            if acct.get("verified") and acct.get("is_root"):
                return email
        return None

    # -- writing ------------------------------------------------------------
    def _save(self, accounts: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(accounts, indent=2, ensure_ascii=False) + "\n"
        self.path.write_text(payload, encoding="utf-8")

    def start_verification(self, email: str, pending: dict | None = None) -> str:
        """Issue a fresh six-digit code for ``email`` and return it.

        ``pending`` is the identity (name / group_id / is_leader / is_root) to
        apply once the code is confirmed — used when creating or updating an
        account. Pass ``None`` for a returning sign-in (identity unchanged).
        """
        email = normalize_email(email)
        code = f"{secrets.randbelow(10 ** 6):06d}"
        expires = (_now() + timedelta(minutes=CODE_TTL_MINUTES)).isoformat()
        with self._lock:
            accounts = self._load()
            acct = accounts.get(email) or {
                "email": email, "name": "", "group_id": "",
                "is_leader": False, "is_root": False, "verified": False,
                "created_at": _now().isoformat(),
            }
            acct["code"] = code
            acct["code_expires"] = expires
            acct["pending"] = pending
            accounts[email] = acct
            self._save(accounts)
        return code

    def verify(self, email: str, code: str) -> dict | None:
        """Confirm a code. On success apply any pending identity, mark the
        account verified, and return it. Returns None on a bad/expired code."""
        email = normalize_email(email)
        code = (code or "").strip()
        with self._lock:
            accounts = self._load()
            acct = accounts.get(email)
            if not acct or not acct.get("code"):
                return None
            if not secrets.compare_digest(str(acct["code"]), code):
                return None
            try:
                expired = _now() > datetime.fromisoformat(acct["code_expires"])
            except (ValueError, KeyError):
                expired = True
            if expired:
                return None
            pending = acct.get("pending")
            if pending:
                acct["name"] = pending.get("name", acct.get("name", ""))
                acct["group_id"] = pending.get("group_id", acct.get("group_id", ""))
                acct["is_leader"] = bool(pending.get("is_leader", acct.get("is_leader")))
                acct["is_root"] = bool(pending.get("is_root", acct.get("is_root")))
            acct["verified"] = True
            acct["verified_at"] = _now().isoformat()
            acct["code"] = ""
            acct["code_expires"] = ""
            acct["pending"] = None
            accounts[email] = acct
            self._save(accounts)
        return acct
