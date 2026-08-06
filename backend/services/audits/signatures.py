"""Deterministic tech-stack / CMS / hosting / analytics detection (D-38, AUDT-02).

An ordered table of (category, signal_type, pattern, name, confidence):
matching is first-match-wins per category for CMS and hosting, set-union for
stack and analytics (a site can run React + jQuery + GA4 — RESEARCH §Pattern
4). Every pattern is a compiled regex; the three signal sources are the HTML
string, response headers and cookie dicts. Storage shapes follow RESEARCH line
305: tech_stack/analytics are lists with confidence, cms/hosting single dicts
or None.
"""

import re
from dataclasses import dataclass
from typing import Any

# signal_type values and where they search:
_HTML_SOURCES = ("html", "script_src", "meta_generator")


@dataclass(frozen=True)
class Signature:
    """One deterministic detection row (RESEARCH §Pattern 4 table shape)."""

    category: str  # cms | framework | backend | hosting | analytics
    signal_type: str  # html | script_src | meta_generator | header | cookie
    pattern: str
    name: str
    confidence: float


_SIGNATURES: tuple[Signature, ...] = (
    # ---- CMS (first match wins) ----
    Signature("cms", "html", r"wp-content/", "wordpress", 0.9),
    Signature(
        "cms",
        "meta_generator",
        r'generator["\']?\s*content=["\'][^"\']*wordpress',
        "wordpress",
        0.95,
    ),
    Signature("cms", "script_src", r"cdn\.shopify\.com", "shopify", 0.9),
    Signature(
        "cms", "meta_generator", r'generator["\']?\s*content=["\'][^"\']*shopify', "shopify", 0.95
    ),
    Signature("cms", "html", r"webflow\.js|data-wf-site", "webflow", 0.9),
    Signature("cms", "html", r"static\.wixstatic\.com|data-wix", "wix", 0.9),
    Signature("cms", "html", r"static1\.squarespace\.com", "squarespace", 0.9),
    Signature(
        "cms",
        "meta_generator",
        r'generator["\']?\s*content=["\'][^"\']*squarespace',
        "squarespace",
        0.95,
    ),
    Signature("cms", "html", r"sites/default/files", "drupal", 0.8),
    Signature(
        "cms", "meta_generator", r'generator["\']?\s*content=["\'][^"\']*drupal', "drupal", 0.85
    ),
    Signature(
        "cms", "meta_generator", r'generator["\']?\s*content=["\'][^"\']*ghost', "ghost", 0.8
    ),
    Signature("cms", "script_src", r"framer\.com", "framer", 0.9),
    Signature("cms", "html", r"data-framer-site-id", "framer", 0.9),
    # ---- Framework (set union → tech_stack) ----
    Signature("framework", "html", r"data-reactroot", "react", 0.9),
    Signature("framework", "html", r"__reactFiber|__reactContainer", "react", 0.9),
    Signature("framework", "html", r'id=["\']root["\']', "react", 0.8),
    Signature("framework", "html", r"__NEXT_DATA__", "nextjs", 0.9),
    Signature("framework", "html", r"/_next/", "nextjs", 0.9),
    Signature("framework", "html", r"data-v-[a-f0-9]+|__vue__", "vue", 0.9),
    Signature("framework", "html", r"<app-root|ng-version", "angular", 0.9),
    Signature("framework", "script_src", r"jquery[.-]min\.js", "jquery", 0.8),
    Signature("framework", "html", r"window\.jQuery", "jquery", 0.7),
    Signature("framework", "script_src", r"tailwindcss", "tailwind", 0.7),
    Signature("framework", "script_src", r"bootstrap[.-].*\.css", "bootstrap", 0.7),
    Signature("framework", "html", r"data-bs-", "bootstrap", 0.7),
    Signature("framework", "html", r'__sveltekit|class=["\'][^"\']*svelte-', "svelte", 0.8),
    Signature("framework", "html", r"/@vite/|vite\.", "vite", 0.6),
    # ---- Backend (set union → tech_stack) ----
    Signature("backend", "html", r"csrfmiddlewaretoken", "django", 0.9),
    Signature("backend", "cookie", r"^django", "django", 0.9),
    Signature("backend", "cookie", r"^laravel_session", "laravel", 0.9),
    Signature("backend", "cookie", r"authenticity_token|^_session", "rails", 0.9),
    Signature("backend", "header", r"x-aspnet-version|__viewstate", "aspnet", 0.9),
    # ---- Hosting (first match wins) ----
    Signature("hosting", "header", r"cf-ray|^server:\s*cloudflare", "cloudflare", 0.98),
    Signature("hosting", "header", r"x-nf-request-id|^server:\s*netlify", "netlify", 0.95),
    Signature("hosting", "header", r"x-vercel-id|^server:\s*vercel", "vercel", 0.95),
    Signature("hosting", "header", r"^server:\s*github\.com", "github-pages", 0.95),
    Signature("hosting", "header", r"x-amz-cf-id|^server:\s*cloudfront", "aws-cloudfront", 0.9),
    Signature("hosting", "header", r"x-heroku-", "heroku", 0.9),
    Signature("hosting", "header", r"x-served-by:\s*shopify|x-shopid", "shopify", 0.9),
    # ---- Analytics (set union) ----
    Signature("analytics", "html", r"gtag\('js'", "ga4", 0.9),
    Signature(
        "analytics", "script_src", r"googletagmanager\.com/gtag/js\?id=G-[A-Z0-9]{6,}", "ga4", 0.9
    ),
    Signature(
        "analytics", "script_src", r"google-analytics\.com/analytics\.js|ga\('send'", "ga-ua", 0.9
    ),
    Signature("analytics", "script_src", r"googletagmanager\.com/gtm\.js\?id=GTM-", "gtm", 0.9),
    Signature(
        "analytics", "script_src", r'connect\.facebook\.net/[^"\']*fbevents\.js', "meta-pixel", 0.9
    ),
    Signature(
        "analytics", "script_src", r'static\.hotjar\.com/c/hotjar-[^"\']*\.js', "hotjar", 0.9
    ),
    Signature("analytics", "script_src", r"clarity\.ms/tag/", "ms-clarity", 0.9),
    Signature(
        "analytics", "script_src", r"snap\.licdn\.com/li\.lms-analytics", "linkedin-insight", 0.9
    ),
    Signature("analytics", "script_src", r"analytics\.tiktok\.com/i18n/pixel", "tiktok-pixel", 0.9),
    Signature("analytics", "script_src", r"plausible\.io/js/", "plausible", 0.9),
    Signature("analytics", "script_src", r"matomo\.js|piwik\.js", "matomo", 0.8),
    Signature("analytics", "script_src", r"js\.hs-scripts\.com|hs-analytics", "hubspot", 0.8),
    Signature("analytics", "script_src", r"widget\.intercom\.io", "intercom", 0.8),
    Signature("analytics", "script_src", r"cdn\.mxpnl\.com", "mixpanel", 0.8),
    Signature("analytics", "script_src", r"mc\.yandex\.ru/metrika", "yandex-metrica", 0.8),
)

_compiled: tuple[tuple[str, str, re.Pattern[str], str, float], ...] = tuple(
    (
        sig.category,
        sig.signal_type,
        re.compile(sig.pattern, re.IGNORECASE),
        sig.name,
        sig.confidence,
    )
    for sig in _SIGNATURES
)

# Set-union categories vs first-match-wins categories.
_SINGLE = frozenset({"cms", "hosting"})


def _sources(html: str, headers: dict[str, str], cookies: dict[str, str]) -> dict[str, str]:
    """One lookup dict per signal source — headers/cookies lowercased."""
    header_text = "\n".join(f"{k}: {v}" for k, v in headers.items()).lower()
    cookie_text = "\n".join(f"{name}={value}" for name, value in cookies.items()).lower()
    return {
        "html": html,
        "script_src": html,
        "meta_generator": html,
        "header": header_text,
        "cookie": cookie_text,
    }


def match_signatures(html: str, headers: dict[str, str], cookies: dict[str, str]) -> dict[str, Any]:
    """Detect CMS/hosting (first match wins) and stack/analytics (set union).

    html is the sanitized, size-capped page HTML; headers raw response headers;
    cookies a {name: value} dict. Never raises on hostile input (CMP-06).
    """
    sources = _sources(html, headers, cookies)
    hits: dict[str, list[tuple[str, str, float]]] = (
        {}
    )  # name -> [(category, signal_type, confidence)]
    single_hits: dict[str, dict[str, Any] | None] = {"cms": None, "hosting": None}
    for category, signal_type, pattern, name, confidence in _compiled:
        if category in _SINGLE:
            # First-match-wins per category: the earliest table row whose
            # pattern matches the page owns the slot (RESEARCH Pattern 4).
            if single_hits[category] is None and pattern.search(sources[signal_type]):
                single_hits[category] = {"name": name, "confidence": confidence}
            continue
        if pattern.search(sources[signal_type]):
            hits.setdefault(name, []).append((category, signal_type, confidence))

    single = dict(single_hits)
    stack: list[dict[str, Any]] = []
    analytics: list[dict[str, Any]] = []
    for name, matches in hits.items():
        category = matches[0][0]
        confidence = max(match[2] for match in matches)
        if len(matches) > 1:
            confidence = min(0.99, confidence + 0.05 * (len(matches) - 1))
        if category == "analytics":
            analytics.append({"name": name, "confidence": round(confidence, 2)})
        else:
            stack.append({"name": name, "category": category, "confidence": round(confidence, 2)})

    # Deterministic display order: table order for stack/analytics.
    order = {sig.name: i for i, sig in enumerate(_SIGNATURES)}
    stack.sort(key=lambda item: order.get(item["name"], 0))
    analytics.sort(key=lambda item: order.get(item["name"], 0))
    return {
        "tech_stack": stack,
        "cms": single["cms"],
        "hosting": single["hosting"],
        "analytics": analytics,
    }
