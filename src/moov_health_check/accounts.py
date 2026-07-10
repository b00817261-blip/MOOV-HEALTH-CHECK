"""Email accounts with a permanent sign-in code — so people keep their account.

The org (groups, invites, roles) is unchanged; this adds a durable record of
*who a person is* keyed by their email address, plus a **fixed six-digit code**
issued once when they register. Signing in is simply email + that code — the
same code every time — and their name, group and leader status come right back,
even on a new device. Signing out never changes the code.

Storage is a single JSON file (``accounts.json`` in the data dir), in keeping
with the zero-dependency, no-database design. Point the data dir at a
persistent disk (or a shared drive) and the accounts travel with it.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_code() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


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
            if acct.get("is_root"):
                return email
        return None

    # -- writing ------------------------------------------------------------
    def _save(self, accounts: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(accounts, indent=2, ensure_ascii=False) + "\n"
        self.path.write_text(payload, encoding="utf-8")

    def register(self, email: str, identity: dict) -> dict:
        """Create or update an account and return it (with its permanent code).

        ``identity`` sets name / group_id / is_leader / is_root. The six-digit
        sign-in code is generated once, on first registration, and kept forever
        after — re-registering the same email never changes it.
        """
        email = normalize_email(email)
        with self._lock:
            accounts = self._load()
            acct = accounts.get(email) or {
                "email": email, "created_at": _now().isoformat(),
                "code": _new_code(),
            }
            if not acct.get("code"):
                acct["code"] = _new_code()
            acct["name"] = identity.get("name", acct.get("name", ""))
            acct["group_id"] = identity.get("group_id", acct.get("group_id", ""))
            acct["is_leader"] = bool(identity.get("is_leader", acct.get("is_leader")))
            acct["is_root"] = bool(identity.get("is_root", acct.get("is_root")))
            accounts[email] = acct
            self._save(accounts)
        return acct

    def check(self, email: str, code: str) -> dict | None:
        """Return the account if ``email`` + ``code`` match, else None.

        The code is permanent — the one issued at registration works every time,
        with no expiry, so people sign back in with the code they kept."""
        acct = self.get(email)
        code = (code or "").strip()
        if acct and acct.get("code") and \
                secrets.compare_digest(str(acct["code"]), code):
            return acct
        return None
