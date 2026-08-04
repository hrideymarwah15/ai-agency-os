"""Compliance tests — CMP-01..04: robots deny-by-default + TTL cache, per-domain
token bucket with jitter, send gates (consent/suppression/cap/address), and the
public one-click unsubscribe endpoint with a signed 7-day token.

Robots/bucket tests run in-process with injected httpx.MockTransport — zero
network. Gate and unsubscribe tests run against the test Postgres DB.
"""

import asyncio
import time
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import AuditLog, ConsentRecord, OutreachSpend, SuppressionEntry
from backend.services.compliance import consent, suppression
from backend.services.compliance.rate_limit import DomainTokenBucket
from backend.services.compliance.robots import RobotsPolicy
from backend.services.compliance.send_gate import check_send
from backend.tools.http_client import CompliantHTTPClient, RobotsDeniedError

ROBOTS_ALLOW = "User-agent: *\nAllow: /\nDisallow: /private\n"


@pytest.fixture
async def compliance_db(test_session: AsyncSession) -> AsyncSession:
    """Clean the compliance tables the gate/unsubscribe tests write to."""
    await test_session.execute(delete(ConsentRecord))
    await test_session.execute(delete(SuppressionEntry))
    await test_session.execute(delete(OutreachSpend))
    await test_session.commit()
    yield test_session


def _robots_handler(calls: list[str]):
    """MockTransport handler serving a canned robots.txt and counting requests."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS_ALLOW)
        return httpx.Response(200, text="page-ok")

    return handler


def _client():
    """TestClient with the app imported AFTER fixtures set the test env."""
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app, follow_redirects=False)


# ── Robots: deny-by-default + TTL cache (CMP-01) ───────────────────────────


async def test_robots_disallowed_path_denied():
    calls: list[str] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_handler(calls))) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=60)
        assert await policy.can_fetch("https://example.com/private/x") is False
        assert await policy.can_fetch("https://example.com/public/page") is True


async def test_robots_deny_by_default_on_http_error():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500, text="boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=60)
        assert await policy.can_fetch("https://example.com/anything") is False


async def test_robots_deny_by_default_on_connection_error():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        raise httpx.ConnectError("no route to host")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=60)
        assert await policy.can_fetch("https://example.com/anything") is False


async def test_robots_ttl_cache_fetches_once_per_domain():
    calls: list[str] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_handler(calls))) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=60)
        assert await policy.can_fetch("https://example.com/public/1") is True
        assert await policy.can_fetch("https://example.com/public/2") is True
        assert calls == ["/robots.txt"]  # second call served from cache


async def test_robots_refetches_after_ttl_expiry():
    calls: list[str] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_handler(calls))) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=0)
        assert await policy.can_fetch("https://example.com/public/1") is True
        assert await policy.can_fetch("https://example.com/public/2") is True
        assert calls == ["/robots.txt", "/robots.txt"]  # expired on second call


async def test_robots_deny_by_default_writes_audit(migrated_db, compliance_db):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500, text="boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=60)
        assert await policy.can_fetch("https://example.com/anything") is False
    rows = (
        await compliance_db.execute(select(AuditLog).where(AuditLog.action == "robots_denied_by_default"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].actor == "system"


# ── Token bucket: per-domain isolation + jitter (CMP-02) ───────────────────


async def test_bucket_initial_capacity_passes_instantly():
    bucket = DomainTokenBucket(capacity=2, refill_per_sec=0)
    start = time.monotonic()
    await bucket.acquire("a.example")
    await bucket.acquire("a.example")
    assert time.monotonic() - start < 0.2


async def test_bucket_empty_waits():
    bucket = DomainTokenBucket(capacity=2, refill_per_sec=0)
    await bucket.acquire("a.example")
    await bucket.acquire("a.example")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bucket.acquire("a.example"), timeout=0.2)


async def test_bucket_domains_are_isolated():
    bucket = DomainTokenBucket(capacity=1, refill_per_sec=0)
    await bucket.acquire("a.example")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bucket.acquire("a.example"), timeout=0.2)
    await bucket.acquire("b.example")  # domain B untouched — passes instantly


async def test_bucket_jitter_within_loose_bounds():
    bucket = DomainTokenBucket(capacity=1, refill_per_sec=1.0)
    await bucket.acquire("j.example")  # instant — consumes the token
    start = time.monotonic()
    await bucket.acquire("j.example")  # waits 1s + uniform(0, 1s] jitter
    elapsed = time.monotonic() - start
    assert 1.0 <= elapsed < 2.5


# ── Suppression + consent records (CMP-04) ─────────────────────────────────


async def test_suppression_add_and_lookup(compliance_db):
    await suppression.add(compliance_db, email=" Lead@Example.COM ", reason="bounced")
    assert await suppression.is_suppressed(compliance_db, "lead@example.com") is True
    assert await suppression.is_suppressed(compliance_db, "LEAD@EXAMPLE.COM") is True
    assert await suppression.is_suppressed(compliance_db, "other@example.com") is False


async def test_consent_record_and_lookup(compliance_db):
    await consent.record_consent(
        compliance_db,
        email="Lead@Example.COM",
        lawful_basis="explicit",
        source="signup",
        ip="127.0.0.1",
        user_agent="pytest",
    )
    assert await consent.has_consent(compliance_db, "lead@example.com") is True
    assert await consent.has_consent(compliance_db, "nobody@example.com") is False


# ── The compliant fetch door (D-15 #1) ─────────────────────────────────────


async def test_fetch_denied_url_raises_and_issues_no_page_request():
    calls: list[str] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_handler(calls))) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=60)
        bucket = DomainTokenBucket(capacity=10, refill_per_sec=10)
        http_client = CompliantHTTPClient(client, bucket=bucket, policy=policy)
        with pytest.raises(RobotsDeniedError):
            await http_client.fetch("https://example.com/private/x")
        assert calls == ["/robots.txt"]  # only the robots.txt fetch was issued


async def test_fetch_allowed_url_returns_response():
    calls: list[str] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_handler(calls))) as client:
        policy = RobotsPolicy(client, user_agent="AIAgencyOS/1.0", ttl_seconds=60)
        bucket = DomainTokenBucket(capacity=10, refill_per_sec=10)
        http_client = CompliantHTTPClient(client, bucket=bucket, policy=policy)
        response = await http_client.fetch("https://example.com/public/page")
    assert response.status_code == 200
    assert response.text == "page-ok"
    assert calls == ["/robots.txt", "/public/page"]


# ── Send gate: consent → suppression → cap → address (CMP-03/04, D-15 #2) ──


async def test_send_gate_requires_consent(compliance_db):
    email = f"no-consent-{uuid4().hex[:8]}@example.com"
    result = await check_send(compliance_db, email=email, channel="EMAIL")
    assert result == {"allowed": False, "reason": "consent_required"}


async def test_send_gate_blocks_suppressed(compliance_db):
    email = f"suppressed-{uuid4().hex[:8]}@example.com"
    await consent.record_consent(
        compliance_db, email=email, lawful_basis="explicit", source="signup"
    )
    await suppression.add(compliance_db, email=email, reason="one-click-unsubscribe")
    result = await check_send(compliance_db, email=email, channel="EMAIL")
    assert result == {"allowed": False, "reason": "suppressed"}


async def test_send_gate_allows_compliant_path_and_increments_outreach(compliance_db):
    email = f"ok-{uuid4().hex[:8]}@example.com"
    channel = f"EMAIL-{uuid4().hex[:8]}"
    await consent.record_consent(
        compliance_db, email=email, lawful_basis="explicit", source="signup"
    )
    result = await check_send(compliance_db, email=email, channel=channel)
    assert result == {"allowed": True}
    row = (
        await compliance_db.execute(select(OutreachSpend).where(OutreachSpend.channel == channel))
    ).scalar_one()
    assert row.sent_count == 1


async def test_send_gate_daily_cap_exceeded(compliance_db, monkeypatch):
    monkeypatch.setattr(settings, "daily_outreach_limit", 1)
    email = f"cap-{uuid4().hex[:8]}@example.com"
    channel = f"CAP-{uuid4().hex[:8]}"
    await consent.record_consent(
        compliance_db, email=email, lawful_basis="explicit", source="signup"
    )
    assert await check_send(compliance_db, email=email, channel=channel) == {"allowed": True}
    result = await check_send(compliance_db, email=email, channel=channel)
    assert result == {"allowed": False, "reason": "daily_cap_exceeded"}


async def test_send_gate_requires_address(compliance_db, monkeypatch):
    monkeypatch.setattr(settings, "agency_address", "")
    email = f"addr-{uuid4().hex[:8]}@example.com"
    channel = f"ADDR-{uuid4().hex[:8]}"
    await consent.record_consent(
        compliance_db, email=email, lawful_basis="explicit", source="signup"
    )
    result = await check_send(compliance_db, email=email, channel=channel)
    assert result == {"allowed": False, "reason": "address_required"}
    # The blocked send must not consume a cap slot.
    row = await compliance_db.execute(
        select(OutreachSpend).where(OutreachSpend.channel == channel)
    )
    assert row.scalar_one_or_none() is None


async def test_send_gate_audits_blocked_with_reason(compliance_db):
    email = f"audit-{uuid4().hex[:8]}@example.com"
    await check_send(compliance_db, email=email, channel="EMAIL")
    rows = (
        await compliance_db.execute(
            select(AuditLog).where(
                AuditLog.action == "send_blocked", AuditLog.entity_id == email
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].actor == "system"
    assert rows[0].payload["reason"] == "consent_required"


# ── One-click unsubscribe (CMP-04, signed 7-day token, public route) ───────


async def test_unsubscribe_valid_token_confirms_and_blocks_next_send(migrated_db, compliance_db):
    serializer = URLSafeTimedSerializer(settings.session_secret, salt="unsubscribe")
    email = f"sub-{uuid4().hex[:8]}@example.com"
    token = serializer.dumps(email)
    await consent.record_consent(
        compliance_db, email=email, lawful_basis="explicit", source="signup"
    )

    with _client() as client:  # no login — public route
        response = client.get(f"/unsubscribe?t={token}")

    assert response.status_code == 200
    assert "You have been unsubscribed" in response.text
    assert "You won't receive further messages from" in response.text
    assert settings.agency_name in response.text

    assert await suppression.is_suppressed(compliance_db, email) is True
    rows = (
        await compliance_db.execute(
            select(AuditLog).where(AuditLog.action == "unsubscribed", AuditLog.entity_id == email)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].actor == "system"
    assert rows[0].entity_type == "email"
    assert rows[0].payload["reason"] == "one-click-unsubscribe"

    # The next send to that recipient is blocked.
    result = await check_send(compliance_db, email=email, channel="EMAIL")
    assert result == {"allowed": False, "reason": "suppressed"}


async def test_unsubscribe_invalid_token_shows_invalid_state(migrated_db, compliance_db):
    serializer = URLSafeTimedSerializer(settings.session_secret, salt="unsubscribe")
    email = f"bad-{uuid4().hex[:8]}@example.com"
    token = serializer.dumps(email) + "tampered"

    with _client() as client:
        response = client.get(f"/unsubscribe?t={token}")

    assert response.status_code == 200
    assert "Invalid or expired link" in response.text
    assert "This unsubscribe link is invalid or has expired" in response.text
    assert await suppression.is_suppressed(compliance_db, email) is False


async def test_unsubscribe_expired_token_shows_invalid_state(migrated_db, compliance_db):
    serializer = URLSafeTimedSerializer(settings.session_secret, salt="unsubscribe")
    email = f"exp-{uuid4().hex[:8]}@example.com"
    old_ts = int(time.time()) - 8 * 24 * 60 * 60  # 8 days ago — beyond the 7-day TTL
    with patch("time.time", lambda: old_ts):
        token = serializer.dumps(email)

    with _client() as client:
        response = client.get(f"/unsubscribe?t={token}")

    assert response.status_code == 200
    assert "Invalid or expired link" in response.text
    assert await suppression.is_suppressed(compliance_db, email) is False
