"""Tests for the top-labels view grouping cost by the label field."""

import json
import os
from datetime import datetime, timezone

from llm_usage_tracker.cli import main
from llm_usage_tracker.tracker import UsageTracker


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


def test_summary_groups_cost_by_label():
    tracker = UsageTracker()
    tracker.record("openai", "gpt-4o-mini", 1000, 500, label="summarizer")
    tracker.record("openai", "gpt-4o-mini", 2000, 500, label="summarizer")
    tracker.record("anthropic", "claude-haiku-4-5", 1000, 1000, label="qa")
    by_label = tracker.summary()["by_label"]
    assert set(by_label) == {"summarizer", "qa"}
    assert by_label["summarizer"]["calls"] == 2
    assert by_label["summarizer"]["tokens"] == 4000
    assert by_label["qa"]["calls"] == 1
    assert by_label["qa"]["cost_usd"] > 0


def test_summary_groups_unlabeled_events_together():
    tracker = UsageTracker()
    tracker.record("openai", "gpt-4o-mini", 1000, 500)
    tracker.record("openai", "gpt-4o-mini", 1000, 500, label="")
    tracker.record("openai", "gpt-4o-mini", 1000, 500, label="qa")
    by_label = tracker.summary()["by_label"]
    assert by_label["(unlabeled)"]["calls"] == 2
    assert by_label["qa"]["calls"] == 1


def test_top_labels_text_ranks_by_cost_descending(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [
            _row("openai", "gpt-4o-mini", 1000, 500, _ts(19), "cheap"),
            _row("anthropic", "claude-haiku-4-5", 10000, 10000, _ts(19), "pricey"),
            _row("openai", "gpt-4o-mini", 1000, 500, _ts(20), "cheap"),
        ],
    )
    assert main(["top-labels", log]) == 0
    out = capsys.readouterr().out
    assert "Cost by label:" in out
    assert out.index("pricey") < out.index("cheap")
    assert "pricey" in out and "cheap" in out


def test_top_labels_limit_and_json(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [
            _row("openai", "gpt-4o-mini", 1000, 500, _ts(19), "a"),
            _row("anthropic", "claude-haiku-4-5", 10000, 10000, _ts(19), "b"),
            _row("openai", "gpt-4o-mini", 1000, 500, _ts(20), "c"),
        ],
    )
    assert main(["top-labels", log, "--limit", "1", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["labels"]) == 1
    assert data["labels"][0]["label"] == "b"
    assert data["labels"][0]["calls"] == 1
    assert data["calls"] == 3
    assert data["total_cost_usd"] > 0


def test_top_labels_rejects_limit_below_one(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [_row("openai", "gpt-4o-mini", 1000, 500, _ts(19), "a")],
    )
    assert main(["top-labels", log, "--limit", "0"]) == 1
    assert "limit" in capsys.readouterr().err


def test_report_json_includes_by_label(tmp_path, capsys):
    log = _make_log(
        tmp_path,
        [_row("openai", "gpt-4o-mini", 1000, 500, _ts(19), "summarizer")],
    )
    assert main(["report", log, "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["by_label"]["summarizer"]["calls"] == 1
