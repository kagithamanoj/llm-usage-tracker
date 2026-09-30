"""Tests for llm_usage_tracker."""

import json
import os
import tempfile

import pytest

from llm_usage_tracker.tracker import (
    DEFAULT_PRICE,
    UsageEvent,
    UsageTracker,
    load_events,
)


def test_event_cost_known_model():
    event = UsageEvent("openai", "gpt-4o-mini", 1000, 1000)
    assert event.cost_usd() == pytest.approx(0.00015 + 0.0006)


def test_event_cost_unknown_model_falls_back():
    event = UsageEvent("acme", "mystery-9", 1000, 1000)
    expected = (DEFAULT_PRICE[0] + DEFAULT_PRICE[1])
    assert event.cost_usd() == pytest.approx(expected)


def test_total_tokens():
    event = UsageEvent("openai", "gpt-4o", 120, 80)
    assert event.total_tokens == 200


def test_record_rejects_negative_tokens():
    tracker = UsageTracker()
    with pytest.raises(ValueError):
        tracker.record("openai", "gpt-4o", -1, 10)


def test_summary_aggregates_by_model():
    tracker = UsageTracker()
    tracker.record("openai", "gpt-4o-mini", 1000, 500)
    tracker.record("openai", "gpt-4o-mini", 2000, 500)
    tracker.record("anthropic", "claude-haiku-4-5", 1000, 1000)
    summary = tracker.summary()
    assert summary["calls"] == 3
    assert summary["total_tokens"] == 5000
    assert summary["by_model"]["openai/gpt-4o-mini"]["calls"] == 2
    assert summary["total_cost_usd"] > 0


def test_jsonl_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "usage.jsonl")
        tracker = UsageTracker(log_path=log)
        tracker.record("google", "gemini-2.5-flash", 300, 700, label="qa")
        rows = load_events(log)
        assert len(rows) == 1
        assert rows[0]["label"] == "qa"
        assert rows[0]["total_tokens"] == 1000
        assert rows[0]["cost_usd"] >= 0
