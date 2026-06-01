"""Tests for medium-tier anti-abuse (IP/device registration limits)."""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio

from src.web_app import app


def _device() -> str:
    return f"dev_test_{uuid.uuid4().hex[:16]}"


def _abuse_headers(device_id: str, *, ip_seq: int | None = None) -> dict:
    """Use TEST-NET-3 (203.0.113.0/24) with optional stable sequence per device test."""
    if ip_seq is None:
        octet = int(uuid.uuid4().hex[:2], 16) % 200 + 10
    else:
        base = int(device_id.rsplit("_", 1)[-1][:4], 16) % 150
        octet = 10 + base + ip_seq
    return {
        "X-Device-Id": device_id,
        "X-Forwarded-For": f"203.0.113.{octet % 254 + 1}",
    }


async def _register(
    client,
    *,
    username: str,
    email: str,
    device_id: str,
    ip_seq: int | None = None,
):
    return await client.post(
        "/register",
        data={"username": username, "email": email, "password": "test-pass-123"},
        headers=_abuse_headers(device_id, ip_seq=ip_seq),
    )


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_register_requires_device_id(api_client):
    response = await api_client.post(
        "/register",
        data={
            "username": f"u_{uuid.uuid4().hex[:8]}",
            "email": f"{uuid.uuid4().hex[:8]}@example.com",
            "password": "x",
        },
    )
    assert response.status_code == 429
    assert "设备标识" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email_blocked(api_client):
    device = _device()
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    first = await _register(api_client, username=f"u1_{uuid.uuid4().hex[:6]}", email=email, device_id=device)
    assert first.status_code == 200, first.text
    second = await _register(
        api_client,
        username=f"u2_{uuid.uuid4().hex[:6]}",
        email=email.upper(),
        device_id=_device(),
    )
    assert second.status_code == 429
    assert "邮箱" in second.json()["detail"]


@pytest.mark.asyncio
async def test_trial_only_once_per_device(api_client):
    device = _device()
    first = await _register(
        api_client,
        username=f"trial1_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        device_id=device,
    )
    assert first.status_code == 200, first.text
    assert first.json()["trial_granted"] is True

    second = await _register(
        api_client,
        username=f"trial2_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        device_id=device,
    )
    assert second.status_code == 200, second.text
    assert second.json()["trial_granted"] is False


@pytest.mark.asyncio
async def test_device_registration_limit(api_client):
    device = _device()
    for i in range(2):
        response = await _register(
            api_client,
            username=f"lim_{i}_{uuid.uuid4().hex[:6]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            device_id=device,
            ip_seq=i,
        )
        assert response.status_code == 200, response.text

    blocked = await _register(
        api_client,
        username=f"lim_x_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        device_id=device,
        ip_seq=2,
    )
    assert blocked.status_code == 429
    assert "设备" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_login_records_device_header(api_client):
    device = _device()
    username = f"login_{uuid.uuid4().hex[:6]}"
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    reg = await _register(api_client, username=username, email=email, device_id=device)
    assert reg.status_code == 200, reg.text

    login = await api_client.post(
        "/token",
        data={"username": username, "password": "test-pass-123"},
        headers=_abuse_headers(device),
    )
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_admin_linked_accounts(api_client):
    admin = await api_client.post("/token", data={"username": "admin", "password": "admin123"})
    token = admin.json()["access_token"]
    device = _device()
    username = f"link_{uuid.uuid4().hex[:6]}"
    await _register(
        api_client,
        username=username,
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        device_id=device,
    )
    response = await api_client.get(
        "/api/admin/abuse/linked",
        params={"token": token, "device_id": device},
    )
    assert response.status_code == 200, response.text
    linked = response.json()["linked"]
    assert any(row.get("username") == username for row in linked)
