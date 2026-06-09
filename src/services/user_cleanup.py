"""Identify disposable test accounts for admin bulk cleanup."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

PROTECTED_USERNAMES: Set[str] = frozenset({"admin", "demo"})

# pytest / abuse-guard style: u1_a1b2c3, u2_deadbeef
_ABUSE_REGISTER_USERNAME = re.compile(r"^u\d+_[a-f0-9]{4,12}$", re.I)
_TEST_PREFIX = re.compile(r"^(test|pytest|tmp|fake|spam|bot)_", re.I)
_GENERIC_TEST = re.compile(r"^(test|pytest)\d*$", re.I)


def is_disposable_test_account(username: str, email: str = "", *, role: str = "") -> bool:
    """True if row looks like automated test registration, not a real user."""
    user = (username or "").strip()
    mail = (email or "").strip().lower()
    if not user or user in PROTECTED_USERNAMES:
        return False
    if (role or "").strip() == "admin":
        return False
    if _ABUSE_REGISTER_USERNAME.match(user):
        return True
    if _TEST_PREFIX.match(user) or _GENERIC_TEST.match(user):
        return True
    if mail.endswith("@example.com") or "@test." in mail or mail.endswith("@local.test"):
        return True
    if mail.startswith("test+") or mail.startswith("pytest+"):
        return True
    return False


def list_disposable_accounts(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in users:
        username = str(row.get("username") or "")
        if is_disposable_test_account(
            username,
            str(row.get("email") or ""),
            role=str(row.get("role") or ""),
        ):
            out.append(row)
    return out
