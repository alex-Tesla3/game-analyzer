"""Tests for disposable test account detection."""

from src.services.user_cleanup import is_disposable_test_account, list_disposable_accounts


def test_disposable_abuse_guard_username():
    assert is_disposable_test_account("u1_deadbeef", "a@b.com")
    assert not is_disposable_test_account("admin", "admin@example.com", role="admin")
    assert not is_disposable_test_account("demo", "demo@test.com")


def test_disposable_email_heuristic():
    assert is_disposable_test_account("someone", "user@example.com")


def test_list_disposable_accounts():
    users = [
        {"username": "admin", "email": "a@x.com", "role": "admin"},
        {"username": "u2_abc12345", "email": "t@example.com", "role": "user"},
        {"username": "demo", "email": "d@x.com", "role": "user"},
    ]
    disposable = list_disposable_accounts(users)
    assert len(disposable) == 1
    assert disposable[0]["username"] == "u2_abc12345"
