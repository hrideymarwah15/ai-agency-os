"""Source registry — ordered source map with settings-driven enable gating and MOCK_MODE swap.

Registry order drives the UI source_columns (UI-SPEC fixed column order: HN,
Reddit, Yelp, G Maps, Mock). MOCK_MODE swaps adapter classes HERE (D-23) —
never inside adapter internals. Key-gated sources (yelp/google_places) are
enabled only when both the flag and the API key are present (D-21).
"""

from dataclasses import dataclass

from backend.config import settings
from backend.services.discovery.base import SourceAdapter
from backend.services.discovery.sources.google_places import (
    GooglePlacesSource,
    MockGooglePlaces,
)
from backend.services.discovery.sources.hn import HNAlgoliaSource, MockHN
from backend.services.discovery.sources.mock_directory import MockDirectorySource
from backend.services.discovery.sources.reddit import MockReddit, RedditSource
from backend.services.discovery.sources.yelp import MockYelp, YelpSource


# Row: (source_id, live class, mock class, settings flag, requires key, key settings attr)
@dataclass(frozen=True)
class _SourceEntry:
    source_id: str
    live: type[SourceAdapter]
    mock: type[SourceAdapter]
    flag: str
    requires_keys: bool = False
    key_attr: str | None = None


_ENTRIES: tuple[_SourceEntry, ...] = (
    _SourceEntry("hn", HNAlgoliaSource, MockHN, "source_hn_enabled"),
    _SourceEntry("reddit", RedditSource, MockReddit, "source_reddit_enabled"),
    _SourceEntry("yelp", YelpSource, MockYelp, "source_yelp_enabled", True, "yelp_api_key"),
    _SourceEntry(
        "google_places",
        GooglePlacesSource,
        MockGooglePlaces,
        "source_google_places_enabled",
        True,
        "google_places_api_key",
    ),
    _SourceEntry(
        "mock_directory", MockDirectorySource, MockDirectorySource, "source_mock_directory_enabled"
    ),
)


def _enabled(entry: _SourceEntry) -> bool:
    """Settings flag AND key presence for key-gated sources (D-21)."""
    if not getattr(settings, entry.flag):
        return False
    return not entry.requires_keys or bool(getattr(settings, entry.key_attr or ""))


def all_sources() -> list[tuple[str, type[SourceAdapter], bool, str, str]]:
    """Ordered (source_id, adapter_class, enabled, display_name, short_name) rows — UI column order."""
    rows: list[tuple[str, type[SourceAdapter], bool, str, str]] = []
    for entry in _ENTRIES:
        adapter_class = entry.mock if settings.mock_mode else entry.live
        rows.append(
            (
                entry.source_id,
                adapter_class,
                _enabled(entry),
                adapter_class.display_name,
                adapter_class.short_name,
            )
        )
    return rows


def enabled_sources() -> list[tuple[str, type[SourceAdapter], bool, str, str]]:
    """Only sources whose settings flag (and key, if gated) is enabled."""
    return [row for row in all_sources() if row[2]]
