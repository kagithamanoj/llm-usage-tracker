"""Tests for CSV export of the usage summary."""

import csv
import io
import json
import os
from datetime import datetime, timezone

import pytest

from llm_usage_tracker import UsageTracker, summary_to_csv
from llm_usage_tracker.cli import main


def _ts(day: int) -> float:
    return datetime(2026, 10, day, 12, tzinfo=timezone.utc).timestamp()


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


def _parse(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_summary_to_csv_layout():
    tracker = UsageTracker()
    tracker.record("anthropic", "claude-haiku-4-5", 1000, 500, timestamp=_ts(20))
    tracker.record("openai", "gpt-4o-mini", 1000, 500, timestamp=_ts(19))
    tracker.record("openai", "gpt-4o-mini", 2000, 500, timestamp=_ts(19))
    rows = _parse(summary_to_csv(tracker.summary()))
    header = io.StringIO(summary_to_csv(tracker.summary()))
    assert header.readline().strip() == "section,group,calls,tokens,cost_usd"
    model_rows = [r for r in rows if r["section"] == "model"]
    day_rows = [r for r in rows if r["section"] == "day"]
    totals = [r for r in rows if r["section"] == "total"]
    assert [r["group"] for r in model_rows] == [
        "anthropic/claude-haiku-4-5",
        "openai/gpt-4o-mini",
    ]
    mini = model_rows[1]
    assert mini["calls"] == "2"
    assert mini["tokens"] == "4000"
    assert float(mini["cost_usd"]) > 0
    assert [r["group"] for r in day_rows] == ["2026-10-19", "2026-10-20"]
    assert day_rows[0]["calls"] == "2"
    assert len(totals) == 1
    assert totals[0]["calls"] == "3"
    assert totals[0]["tokens"] == "5500"
    summary = tracker.summary()
    assert totals[0]["cost_usd"] == f"{summary['total_cost_usd']:.6f}"


def test_summary_to_csv_empty_summary():
    tracker = UsageTracker()
    rows = _parse(summary_to_csv(tracker.summary()))
    assert len(rows) == 1
    assert rows[0]["section"] == "total"
    assert rows[0]["calls"] == "0"
    assert rows[0]["tokens"] == "0"


def test_report_csv_end_to_end(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [
            _row("openai", "gpt-4o-mini", 1000, 500, _ts(19)),
            _row("openai", "gpt-4o-mini", 2000, 500, _ts(20)),
        ],
    )
    assert main(["report", log, "--format", "csv"]) == 0
    rows = _parse(capsys.readouterr().out)
    assert [r["section"] for r in rows] == ["model", "day", "day", "total"]
    total = rows[-1]
    assert total["calls"] == "2"
    assert total["tokens"] == "4000"


def test_report_csv_rejects_bad_format(tmp_path, capsys):
    log = _make_log(tmp_path, [_row("openai", "gpt-4o-mini", 100, 100, _ts(19))])
    with pytest.raises(SystemExit) as exc:
        main(["report", log, "--format", "yaml"])
    assert exc.value.code == 2
