"""HN "Who is hiring" adapter tests — zero network via MockTransport
(RESEARCH §Code Examples): the handler branches /items/ vs search paths, the
fixture holds thread hits + children, and candidates are sanitized (CMP-06),
normalized, and idempotency-keyed as hn:{child_id}.
"""

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from backend.services.discovery.base import (
    RejectReason,
    RunContext,
    SourceStatCollector,
)
from backend.services.discovery.sources.hn import HNAlgoliaSource
from backend.tools.http_client import build_compliant_client

_FIXTURE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "hn_whoishiring_sample.json").read_text()
)


def _hn_handler(data: dict):
    """Branch /items/ (children) vs search (hits) per RESEARCH §Code Examples."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/items/" in request.url.path:
            return httpx.Response(200, json={"children": data["children"]})
        return httpx.Response(200, json={"hits": data["hits"]})

    return handler


def _ctx(stat: SourceStatCollector, mock_transport, session) -> RunContext:
    client = build_compliant_client(
        mock_transport(_hn_handler(_FIXTURE)), api_hosts=frozenset({"hn.algolia.com"})
    )
    return RunContext(
        run_id=uuid4(), correlation_id="corr", client=client, session=session, stat=stat
    )


async def test_hn_adapter_yields_sanitized_normalized_candidates(
    mock_transport, test_session
) -> None:
    """Candidates carry hn:{id} keys, inert sanitized text, and normalized fields."""
    stat = SourceStatCollector("hn")
    ctx = _ctx(stat, mock_transport, test_session)

    items = [candidate async for candidate in HNAlgoliaSource().fetch_candidates(ctx)]

    assert len(items) == 2
    assert [c.source_item_id for c in items] == ["hn:111", "hn:222"]
    assert all(c.source_id == "hn" for c in items)

    first = items[0]
    assert "<p>" not in first.text and "<a" not in first.text  # CMP-06: inert, data-only
    assert "Acme Web Studio" in first.text
    assert first.raw["hn_id"] == 111
    assert first.raw["thread_id"] == "9999"
    assert first.raw["author"] == "acme-web-studio"
    assert first.normalized["website"].endswith("example.com")
    assert first.normalized["name"] == "Acme Web Studio"
    assert first.normalized["location"] == "Remote (Worldwide)"
    assert {"name", "website", "location"} <= set(first.normalized)

    assert items[1].normalized["name"] == "Globex"
    assert items[1].normalized["location"] == "Berlin"
    assert stat.requests_made == 2  # search + items, both through the compliant door


async def test_hn_short_and_deleted_comments_rejected_not_candidates(
    mock_transport, test_session
) -> None:
    """<4-word comments (deleted posts) are counted as TOO_SHORT rejections."""
    stat = SourceStatCollector("hn")
    ctx = _ctx(stat, mock_transport, test_session)

    items = [candidate async for candidate in HNAlgoliaSource().fetch_candidates(ctx)]

    assert [c.source_item_id for c in items] == ["hn:111", "hn:222"]  # hn:333 never a candidate
    assert stat.found == 3
    assert stat.parsed_ok == 2
    assert stat.rejected == 1
    assert stat.rejection_buckets[RejectReason.TOO_SHORT.value] == 1


async def test_hn_no_thread_yields_no_candidates(mock_transport, test_session) -> None:
    """Empty search hits — no thread, no ITEM fetch, zero candidates."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/items/" in request.url.path:
            return httpx.Response(200, json={"children": []})
        return httpx.Response(200, json={"hits": []})

    stat = SourceStatCollector("hn")
    client = build_compliant_client(
        mock_transport(handler), api_hosts=frozenset({"hn.algolia.com"})
    )
    ctx = RunContext(
        run_id=uuid4(), correlation_id="corr", client=client, session=test_session, stat=stat
    )

    items = [candidate async for candidate in HNAlgoliaSource().fetch_candidates(ctx)]

    assert items == []
    assert stat.found == 0
    assert stat.parsed_ok == 0
    assert stat.requests_made == 1  # only the search request


@pytest.mark.parametrize(
    "payload",
    [
        '{"hits": [{"objectID": "1"}], "children": "not-a-list"}',
        '{"hits": [{"objectID": "1"}], "children": [{"id": 9}]}',
    ],
)
async def test_hn_malformed_payloads_never_crash(payload: str, mock_transport, test_session) -> None:
    """Hostile or malformed API payloads are contained — no exceptions escape."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/items/" in request.url.path:
            return httpx.Response(200, content=payload)
        return httpx.Response(200, json={"hits": [{"objectID": "1"}]})

    stat = SourceStatCollector("hn")
    client = build_compliant_client(
        mock_transport(handler), api_hosts=frozenset({"hn.algolia.com"})
    )
    ctx = RunContext(
        run_id=uuid4(), correlation_id="corr", client=client, session=test_session, stat=stat
    )

    items = [candidate async for candidate in HNAlgoliaSource().fetch_candidates(ctx)]

    assert items == []
