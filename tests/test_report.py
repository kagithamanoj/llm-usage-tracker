"""Tests for the report command and per-day cost breakdown."""

import json
import os
import time
from datetime import datetime, timezone

import pytest

from llm_usage_tracker.cli import main
from llm_usage_tracker.tracker import UsageTracker


def _ts(day: int, hour: int = 12) -> float:
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc).timestamp()


def _row(provider, model, prompt, completion, ts, label=""):
    return {
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "cost_usd": 0.0,
        "timestamp": ts,
        "label": label,
    }


def _make_log(tmp_path, rows):
    log = os.path.join(str(tmp_path), "usage.jsonl")
    with open(log, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return log


def test_summary_groups_events_by_utc_day():
    tracker = UsageTracker()
    tracker.record("openai", "gpt-4o-mini", 1000, 500, timestamp=_ts(19))
    tracker.record("openai", "gpt-4o-mini", 2000, 500, timestamp=_ts(20))
    tracker.record("anthropic", "claude-haiku-4-5", 1000, 1000, timestamp=_ts(20, 23))
    by_day = tracker.summary()["by_day"]
    assert set(by_day) == {"2026-10-19", "2026-10-20"}
    assert by_day["2026-10-19"]["calls"] == 1
    assert by_day["2026-10-20"]["calls"] == 2
    assert by_day["2026-10-20"]["tokens"] == 4500
    assert by_day["2026-10-20"]["cost_usd"] > 0
    assert by_day["2026-10-19"]["cost_usd"] <= by_day["2026-10-20"]["cost_usd"]


def test_record_preserves_explicit_timestamp():
    tracker = UsageTracker()
    ts = _ts(19)
    event = tracker.record("openai", "gpt-4o-mini", 100, 100, timestamp=ts)
    assert event.timestamp == ts


def test_record_defaults_to_now_without_timestamp():
    tracker = UsageTracker()
    before = time.time()
    event = tracker.record("openai", "gpt-4o-mini", 100, 100)
    assert before <= event.timestamp <= time.time()


def test_report_text_shows_per_day_table(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [
            _row("openai", "gpt-4o-mini", 1000, 500, _ts(19)),
            _row("openai", "gpt-4o-mini", 2000, 500, _ts(20)),
        ],
    )
    assert main(["report", log]) == 0
    out = capsys.readouterr().out
    assert "Cost by day (UTC):" in out
    assert "2026-10-19" in out
    assert "2026-10-20" in out


def test_report_json_includes_by_day(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [_row("openai", "gpt-4o-mini", 1000, 500, _ts(19))],
    )
    assert main(["report", log, "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["by_day"]["2026-10-19"]["calls"] == 1


def test_report_groups_by_original_timestamps_not_today(tmp_path, capsys):
    """Events replayed from a log must keep their logged day."""
    log = _make_log(
        tmp_path,
        [_row("openai", "gpt-4o-mini", 1000, 500, _ts(19))],
    )
    assert main(["report", log, "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    today = datetime.now(timezone.utc).date().isoformat()
    assert "2026-10-19" in summary["by_day"]
    if today != "2026-10-19":
        assert today not in summary["by_day"]


def test_budget_still_works_with_timestamps(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [_row("openai", "gpt-4o-mini", 1000, 500, _ts(19))],
    )
    assert main(["budget", log, "--max", "1000.00"]) == 0
    assert "within budget" in capsys.readouterr().out
