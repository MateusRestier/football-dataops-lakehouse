"""Unit tests for pipeline assets (no running Dagster or MinIO required)."""

import pandas as pd
import pytest

from pipeline.assets.validation import _flatten_events


# ── Fixtures ─────────────────────────────────────────────────────────────────


def make_pass_event(match_id=3788741) -> dict:
    return {
        "id": "abc-001",
        "index": 1,
        "period": 1,
        "minute": 5,
        "second": 12,
        "timestamp": "00:05:12.000",
        "type": {"id": 30, "name": "Pass"},
        "possession": 4,
        "possession_team": {"id": 217, "name": "Barcelona"},
        "play_pattern": {"id": 1, "name": "Regular Play"},
        "team": {"id": 217, "name": "Barcelona"},
        "player": {"id": 5503, "name": "Lionel Messi"},
        "location": [45.2, 34.1],
        "duration": 0.5,
        "related_events": [],
    }


def make_administrative_event() -> dict:
    """Starting XI — no location, no player (team-level event)."""
    return {
        "id": "abc-002",
        "index": 0,
        "period": 1,
        "minute": 0,
        "second": 0,
        "timestamp": "00:00:00.000",
        "type": {"id": 35, "name": "Starting XI"},
        "possession": 1,
        "possession_team": {"id": 217, "name": "Barcelona"},
        "play_pattern": {"id": 1, "name": "Regular Play"},
        "team": {"id": 217, "name": "Barcelona"},
        "player": None,
        "location": None,
        "duration": 0.0,
        "related_events": [],
    }


def make_shot_event() -> dict:
    return {
        "id": "abc-003",
        "index": 50,
        "period": 1,
        "minute": 22,
        "second": 5,
        "timestamp": "00:22:05.000",
        "type": {"id": 16, "name": "Shot"},
        "possession": 20,
        "possession_team": {"id": 217, "name": "Barcelona"},
        "play_pattern": {"id": 1, "name": "Regular Play"},
        "team": {"id": 217, "name": "Barcelona"},
        "player": {"id": 5503, "name": "Lionel Messi"},
        "location": [110.0, 40.0],
        "duration": 0.5,
        "shot": {"statsbomb_xg": 0.35, "outcome": {"id": 58, "name": "Goal"}},
        "related_events": [],
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_flatten_events_returns_correct_shape():
    events = [make_pass_event(), make_administrative_event(), make_shot_event()]
    rows = _flatten_events(events)
    assert len(rows) == 3
    assert all("event_id" in r for r in rows)
    assert all("loc_x" in r for r in rows)


def test_flatten_events_null_location():
    events = [make_administrative_event()]
    rows = _flatten_events(events)
    assert rows[0]["loc_x"] is None
    assert rows[0]["loc_y"] is None


def test_flatten_events_location_coords():
    events = [make_pass_event()]
    rows = _flatten_events(events)
    assert rows[0]["loc_x"] == pytest.approx(45.2)
    assert rows[0]["loc_y"] == pytest.approx(34.1)


def test_location_within_pitch_bounds():
    events = [make_pass_event(), make_shot_event()]
    rows = _flatten_events(events)
    df = pd.DataFrame(rows).dropna(subset=["loc_x", "loc_y"])

    assert (df["loc_x"] >= 0).all() and (df["loc_x"] <= 120).all(), "loc_x out of bounds"
    assert (df["loc_y"] >= 0).all() and (df["loc_y"] <= 80).all(), "loc_y out of bounds"


def test_all_events_have_non_null_id():
    events = [make_pass_event(), make_administrative_event(), make_shot_event()]
    rows = _flatten_events(events)
    assert all(r["event_id"] is not None for r in rows)


def test_definitions_loadable():
    """Smoke test: Dagster definitions must load without errors."""
    import os

    os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
    os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
    os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")

    from pipeline.definitions import defs

    defs.validate_loadable()
