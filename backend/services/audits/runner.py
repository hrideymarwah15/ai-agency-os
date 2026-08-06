"""Audit run executor (T04) — one audit, one transaction (Pitfall 5).

For one WebsiteAudit row: static pass through the compliant door (D-32) →
HTMLParser analysis + signatures + rule-table scores → optional rendered pass
via an injected renderer seam (browser-gated default) → capped broken-link
probes → ONE commit at completion. Failures (robots denial, HTTP errors,
unexpected exceptions) mark the row FAILED with last_error and emit
run-granularity audit events — never one audit log per broken link
(Phase 2 Anti-Patterns).
"""

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend import database
from backend.config import settings
from backend.database import AuditStatus, Business, WebsiteAudit
from backend.services.audit import AuditService
from backend.services.audits.renderer import browser_available, render_audit
from backend.services.audits.scoring import (
    build_cwv_report,
    score_accessibility,
    score_mobile,
    score_performance,
    score_seo,
)
from backend.services.audits.signatures import match_signatures
from backend.services.audits.static_analyzer import (
    AuditStats,
    analyze_html,
    find_conversion_gaps,
)
from backend.services.discovery.normalize import normalize_domain
from backend.tools.http_client import (
    CompliantHTTPClient,
    RobotsDeniedError,
    build_compliant_client,
)

# Builds the single-domain compliant client for one audit (test seam: injected).
ClientFactory = Callable[[], CompliantHTTPClient]
# Injected render seam: returns rendered-DOM signals or None (static mode).
RendererFactory = Callable[[str], Awaitable[dict[str, Any] | None]]

_SECURITY_HEADERS = (
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
)
_ASSET_PROBE_CAP = 15  # RESEARCH §Pattern 3: size up to 15 assets through the door
_MAX_ERROR_LENGTH = 1000


def _default_client_factory(session: AsyncSession) -> ClientFactory:
    """Production factory: shared token bucket + robots DB caching (D-32 lock)."""

    def build() -> CompliantHTTPClient:
        return build_compliant_client(session=session)

    return build


async def default_renderer(url: str) -> dict[str, Any] | None:
    """Browser-gated render pass — static mode when Playwright is unavailable (D-33).

    The production worker passes this seam explicitly; tests inject fakes so the
    runner suite never launches a real browser (`renderer=None` = static only).
    """
    if not browser_available():
        return None
    return await render_audit(url)


def _absolutize(website_url: str, href: str) -> str:
    """Resolve a (possibly relative) href against the audited page URL."""
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(website_url, href)


async def _probe_status(client: CompliantHTTPClient, url: str) -> dict[str, Any]:
    """Status probe through the compliant door (AUDT-03, D-37) — never raw fetch.

    The door's streaming extension is GET-based; the body is never read — the
    probe ends at response headers, the etiquette-equivalent of a HEAD request.
    """
    try:
        response, _ttfb = await client.fetch_stream(url)
    except RobotsDeniedError:
        return {"url": url, "status": "robots_denied", "status_code": None}
    except httpx.TimeoutException:
        return {"url": url, "status": "timeout", "status_code": None}
    code = response.status_code
    if 200 <= code < 300:
        status = "ok"
    elif 300 <= code < 400:
        status = "redirect"
    else:
        status = "broken"
    return {"url": url, "status": status, "status_code": code}


async def _link_pass(
    client: CompliantHTTPClient,
    website_url: str,
    link_hrefs: list[str],
) -> list[dict[str, Any]]:
    """Capped broken-link pass (AUDT-03/D-37): internal sample, external cap."""
    site_domain = normalize_domain(website_url)
    internal: list[str] = []
    external: list[str] = []
    for href in link_hrefs:
        url = _absolutize(website_url, href)
        bucket = internal if normalize_domain(url) == site_domain else external
        bucket.append(url)

    results: list[dict[str, Any]] = []
    for url in internal[: settings.audit_broken_link_sample]:
        results.append(await _probe_status(client, url))
    for url in external[: settings.audit_external_link_cap]:
        results.append(await _probe_status(client, url))
    for url in external[settings.audit_external_link_cap :]:
        results.append({"url": url, "status": "skipped", "status_code": None})
    return results


async def _measure_assets(client: CompliantHTTPClient, script_srcs: list[str]) -> tuple[int, int]:
    """Total asset bytes for script srcs, sized through the door (capped)."""
    asset_urls = list(dict.fromkeys(src for src in script_srcs if src))
    total_bytes = 0
    for url in asset_urls[:_ASSET_PROBE_CAP]:
        try:
            response, _ttfb = await client.fetch_stream(url)
            total_bytes += int(response.headers.get("content-length") or 0)
        except (RobotsDeniedError, httpx.TimeoutException, httpx.HTTPStatusError):
            continue
    return total_bytes, min(len(asset_urls), _ASSET_PROBE_CAP)


def _steady_signals(stats: AuditStats, website_url: str) -> dict[str, Any]:
    """Flat signal dict the four rule tables share (measured signals only)."""
    return {
        "html_lang": stats.html_lang,
        "has_title": bool(stats.title),
        "title_length": len(stats.title) if stats.title else 0,
        "has_meta_description": stats.meta_description,
        "has_og_title": stats.og_title,
        "has_og_image": stats.og_image,
        "has_twitter_card": stats.twitter_card,
        "has_canonical": stats.canonical,
        "has_json_ld": stats.json_ld,
        "viewport_meta": stats.viewport_meta,
        "h1_count": stats.h1_count,
        "heading_order_violation": stats.heading_order_violation,
        "img_total": stats.img_total,
        "img_missing_alt": stats.img_missing_alt,
        "images_with_srcset": stats.images_with_srcset,
        "fixed_width_elements": stats.fixed_width_elements,
        "render_blocking_head_scripts": stats.render_blocking_head_scripts,
        "input_missing_label": stats.input_missing_label,
        "button_empty_name": stats.button_empty_name,
        "iframe_missing_title": stats.iframe_missing_title,
        "tables": stats.tables,
        "scheme": urlparse(website_url).scheme,
        # Measured by the runner — never guessed (D-36).
        "content_encoded": False,
        "ttfb_ms": None,
        "html_bytes": None,
        "asset_bytes": None,
        "asset_count": None,
        "robots_present": None,
        "sitemap_present": None,
        "lcp_ms": None,
        "cls": None,
        "inp_ms": None,
    }


async def _present(client: CompliantHTTPClient, url: str) -> bool:
    """True when the door reaches url with a non-error status (probe)."""
    try:
        response, _ttfb = await client.fetch_stream(url)
        return response.status_code < 400
    except (RobotsDeniedError, httpx.TimeoutException, httpx.HTTPStatusError):
        return False


async def execute_audit(
    audit_id: UUID,
    *,
    client_factory: ClientFactory | None = None,
    renderer: RendererFactory | None = None,
) -> None:
    """Run one website audit: static → gated rendered → links → ONE commit.

    All rows commit in one transaction (Pitfall 5). Unrecoverable failures
    (robots denial / HTTP errors / unexpected exceptions) mark the row FAILED
    with last_error and emit run-granularity events in their own commit.
    renderer=None means static-only; pass default_renderer for the
    browser-gated production seam.
    """
    session_maker = database.async_session_maker
    if session_maker is None:
        raise RuntimeError("Database not initialized")
    async with session_maker() as session:
        audit = await session.get(WebsiteAudit, audit_id)
        if audit is None:
            raise RuntimeError(f"audit {audit_id} not found")
        business = await session.get(Business, audit.business_id)
        if business is None or not business.website_url:
            raise RuntimeError(f"audit {audit_id} has no website URL")
        website_url = business.website_url
        build_client = (
            client_factory if client_factory is not None else _default_client_factory(session)
        )
        client = build_client()
        await AuditService.record(
            session,
            actor="system",
            action="audit_run_started",
            entity_type="website_audit",
            entity_id=str(audit.id),
            payload={"audit_version": audit.audit_version, "website": website_url},
        )
        logger.info("audit {} started for {}", audit.id, website_url)

        try:
            # -- 1) Static pass through the compliant door (D-32) ----------
            response = await client.fetch(website_url)
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"homepage returned {response.status_code}",
                    request=response.request,
                    response=response,
                )
            html = response.text[: settings.audit_html_max_bytes]
            headers = response.headers
            cookies = dict(response.cookies)
            _streamed, ttfb_ms = await client.fetch_stream(website_url)
            robots_present = await _present(client, urljoin(website_url, "robots.txt"))
            sitemap_present = await _present(client, urljoin(website_url, "sitemap.xml"))

            stats = analyze_html(html)
            asset_bytes, asset_count = await _measure_assets(
                client, [s.get("src", "") for s in stats.scripts]
            )
            signature_hits = match_signatures(html, dict(headers), cookies)

            signals = _steady_signals(stats, website_url)
            signals.update(
                {
                    "ttfb_ms": int(ttfb_ms),
                    "html_bytes": len(html),
                    "asset_bytes": asset_bytes,
                    "asset_count": asset_count,
                    "content_encoded": bool(headers.get("content-encoding")),
                    "robots_present": robots_present,
                    "sitemap_present": sitemap_present,
                }
            )

            # -- 2) Rendered pass — only via the render seam (D-33) ---------
            rendered: dict[str, Any] | None = None
            if renderer is not None:
                try:
                    rendered = await renderer(website_url)
                except Exception:  # noqa: BLE001 — render failure degrades, never fails
                    logger.warning("audit {} render degraded", audit.id)
                    rendered = None
            if rendered:
                signals["lcp_ms"] = rendered.get("lcp_ms")
                signals["cls"] = rendered.get("cls")
                signals["inp_ms"] = rendered.get("inp_ms")

            cwv = build_cwv_report(int(ttfb_ms), rendered=rendered or None)

            # -- 3) Broken links (capped) + conversion gaps (AUDT-03) ------
            broken_links = await _link_pass(
                client, website_url, [link["href"] for link in stats.links]
            )
            gaps = find_conversion_gaps(stats)
            security_headers = {name: (headers.get(name) or "") for name in _SECURITY_HEADERS}

            # -- Persist + ONE commit (Pitfall 5) --------------------------
            audit.performance_score = score_performance(signals)
            audit.accessibility_score = score_accessibility(signals)
            audit.seo_score = score_seo(signals)
            audit.mobile_score = score_mobile(signals)
            audit.cwv = cwv
            audit.tech_stack = signature_hits["tech_stack"]
            audit.cms = signature_hits["cms"]
            audit.hosting = signature_hits["hosting"]
            audit.analytics = signature_hits["analytics"]
            audit.broken_links = broken_links
            audit.gaps = gaps
            audit.security_headers = security_headers
            audit.raw_stats = {**asdict(stats), "signals": signals}
            audit.status = AuditStatus.COMPLETED
            audit.finished_at = datetime.now(UTC)
            await AuditService.record(
                session,
                actor="system",
                action="audit_run_finished",
                entity_type="website_audit",
                entity_id=str(audit.id),
                payload={
                    "status": audit.status.value,
                    "performance": audit.performance_score,
                    "accessibility": audit.accessibility_score,
                    "seo": audit.seo_score,
                    "mobile": audit.mobile_score,
                },
            )
            await session.commit()
            logger.info("audit {} completed", audit.id)
        except (RobotsDeniedError, httpx.HTTPStatusError) as exc:
            await _mark_failed(session, audit, message=str(exc), event_action="audit_blocked")
        except Exception as exc:  # noqa: BLE001 — any failure surfaces as FAILED
            await _mark_failed(session, audit, message=str(exc))


async def _mark_failed(
    session: AsyncSession,
    audit: WebsiteAudit,
    *,
    message: str,
    event_action: str = "audit_run_failed",
) -> None:
    """Mark the row FAILED and emit run-granularity events — one commit (P5)."""
    audit.status = AuditStatus.FAILED
    audit.last_error = message[:_MAX_ERROR_LENGTH]
    audit.finished_at = datetime.now(UTC)
    await AuditService.record(
        session,
        actor="system",
        action=event_action,
        entity_type="website_audit",
        entity_id=str(audit.id),
        payload={"error": message},
    )
    await AuditService.record(
        session,
        actor="system",
        action="audit_run_finished",
        entity_type="website_audit",
        entity_id=str(audit.id),
        payload={"status": AuditStatus.FAILED.value, "error": message},
    )
    await session.commit()
    logger.error("audit {} failed: {}", audit.id, message)


_MAX_ERROR_LENGTH = 1000
