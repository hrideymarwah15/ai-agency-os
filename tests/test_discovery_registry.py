"""Registry tests — source order, settings-driven enable flags, key gating, and
the MOCK_MODE adapter swap (D-21/D-23). Registry order is the UI-SPEC fixed
column order (HN, Reddit, Yelp, G Maps, Mock); unconfigured sources are
disabled; yelp/google_places are key-gated.
"""

from backend.services.discovery import registry
from backend.services.discovery.sources.google_places import (
    GooglePlacesSource,
    MockGooglePlaces,
)
from backend.services.discovery.sources.hn import HNAlgoliaSource, MockHN
from backend.services.discovery.sources.mock_directory import MockDirectorySource
from backend.services.discovery.sources.reddit import MockReddit, RedditSource
from backend.services.discovery.sources.yelp import MockYelp, YelpSource

SOURCE_ORDER = ["hn", "reddit", "yelp", "google_places", "mock_directory"]
SHORT_NAMES = ["HN", "Reddit", "Yelp", "G Maps", "Mock"]


def _enabled_ids() -> list[str]:
    return [row[0] for row in registry.enabled_sources()]


def test_registry_returns_five_sources_in_column_order() -> None:
    """all_sources() yields exactly the 5 adapters in UI-SPEC column order."""
    rows = registry.all_sources()
    assert len(rows) == 5
    assert [row[0] for row in rows] == SOURCE_ORDER
    assert [row[4] for row in rows] == SHORT_NAMES


def test_source_flags_default_hn_enabled_only() -> None:
    """D-21: unconfigured sources are disabled; hn is the only default-on flag."""
    assert _enabled_ids() == ["hn"]


def test_yelp_requires_key_presence(monkeypatch) -> None:
    """Key-gated: yelp needs BOTH its flag and a non-empty YELP_API_KEY."""
    monkeypatch.setattr(registry.settings, "source_yelp_enabled", True)
    monkeypatch.setattr(registry.settings, "yelp_api_key", "")
    assert "yelp" not in _enabled_ids()
    monkeypatch.setattr(registry.settings, "yelp_api_key", "test-key")
    assert "yelp" in _enabled_ids()


def test_google_places_requires_key_presence(monkeypatch) -> None:
    """Key-gated: google_places needs BOTH its flag and GOOGLE_PLACES_API_KEY."""
    monkeypatch.setattr(registry.settings, "source_google_places_enabled", True)
    monkeypatch.setattr(registry.settings, "google_places_api_key", "")
    assert "google_places" not in _enabled_ids()
    monkeypatch.setattr(registry.settings, "google_places_api_key", "test-key")
    assert "google_places" in _enabled_ids()


def test_flag_off_stays_disabled_even_with_key(monkeypatch) -> None:
    """A key alone never enables a source whose flag is off."""
    monkeypatch.setattr(registry.settings, "source_yelp_enabled", False)
    monkeypatch.setattr(registry.settings, "yelp_api_key", "test-key")
    assert "yelp" not in _enabled_ids()


def test_mock_mode_swaps_adapter_classes(monkeypatch) -> None:
    """D-23: MOCK_MODE swaps registry entries to Mock adapters — never adapter internals."""
    monkeypatch.setattr(registry.settings, "mock_mode", False)
    live = {row[0]: row[1] for row in registry.all_sources()}
    assert live["hn"] is HNAlgoliaSource
    assert live["reddit"] is RedditSource
    assert live["yelp"] is YelpSource
    assert live["google_places"] is GooglePlacesSource

    monkeypatch.setattr(registry.settings, "mock_mode", True)
    mocked = {row[0]: row[1] for row in registry.all_sources()}
    assert mocked["hn"] is MockHN
    assert mocked["reddit"] is MockReddit
    assert mocked["yelp"] is MockYelp
    assert mocked["google_places"] is MockGooglePlaces
    # mock_directory is mock-only: the same class in both modes.
    assert mocked["mock_directory"] is MockDirectorySource
    assert live["mock_directory"] is MockDirectorySource
