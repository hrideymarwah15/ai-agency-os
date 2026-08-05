"""D-31 api_hosts robots exemption tests — documented API hosts bypass robots.txt
(governed by API terms, not robots), audited once per host per policy instance,
while deny-by-default is preserved everywhere else (Phase 1 behavior intact).

Zero network: every test uses injected httpx.MockTransport handlers.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from backend.database import AuditLog
from backend.services.compliance.robots import RobotsPolicy
from backend.tools.http_client import RobotsDeniedError, build_compliant_client


def _robots_404_handler(calls: list[str]):
    """Handler whose robots.txt always 404s (deny-by-default) and counts requests."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="no robots")
        return httpx.Response(200, text="page-ok")

    return handler


async def test_exempt_host_bypasses_robots_without_request():
    """An api_hosts-listed host is fetchable with ZERO robots.txt requests."""
    calls: list[str] = []

    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_404_handler(calls))) as c:
        policy = RobotsPolicy(
            c, user_agent="AIAgencyOS/1.0", ttl_seconds=60, api_hosts=frozenset({"hn.algolia.com"})
        )
        assert await policy.can_fetch("https://hn.algolia.com/api/v1/items/1") is True
        assert await policy.can_fetch("https://hn.algolia.com/api/v1/search?query=x") is True

    assert calls == []  # robots.txt was never consulted for the exempt host


async def test_exempt_host_audits_once_per_host(migrated_db, test_session):
    """Exactly one api_source_exempt row per exempt host per policy instance."""
    host = f"exempt-audit-{uuid4().hex[:8]}.example"

    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_404_handler([]))) as c:
        policy = RobotsPolicy(
            c,
            user_agent="AIAgencyOS/1.0",
            ttl_seconds=60,
            session=test_session,
            api_hosts=frozenset({host}),
        )
        assert await policy.can_fetch(f"https://{host}/api/v1/x") is True
        assert await policy.can_fetch(f"https://{host}/api/v1/y") is True

    rows = (
        (
            await test_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "api_source_exempt", AuditLog.entity_id == host
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].actor == "system"
    assert rows[0].entity_type == "domain"


async def test_non_exempt_host_keeps_deny_by_default():
    """Hosts outside api_hosts keep Phase 1 behavior — robots 404 denies the fetch."""
    calls: list[str] = []

    async with httpx.AsyncClient(transport=httpx.MockTransport(_robots_404_handler(calls))) as c:
        policy = RobotsPolicy(
            c, user_agent="AIAgencyOS/1.0", ttl_seconds=60, api_hosts=frozenset({"hn.algolia.com"})
        )
        assert await policy.can_fetch("https://blocked.example/page") is False

    assert calls == ["/robots.txt"]  # robots.txt WAS consulted for the non-exempt host


async def test_build_compliant_client_api_hosts_fetch_succeeds(mock_transport):
    """The factory threads api_hosts through: exempt fetch works end-to-end."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"hits": []})

    client = build_compliant_client(
        mock_transport(handler), api_hosts=frozenset({"hn.algolia.com"})
    )
    response = await client.fetch("https://hn.algolia.com/api/v1/search_by_date?tags=story")
    assert response.status_code == 200
    assert calls == ["/search_by_date"]  # robots.txt never requested for the exempt host


async def test_build_compliant_client_default_empty_still_denies(mock_transport):
    """Default api_hosts=∅ preserves Phase 1 deny-by-default end-to-end."""
    calls: list[str] = []
    client = build_compliant_client(mock_transport(_robots_404_handler(calls)))
    with pytest.raises(RobotsDeniedError):
        await client.fetch("https://blocked.example/page")
    assert calls == ["/robots.txt"]
