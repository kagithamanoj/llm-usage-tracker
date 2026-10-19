"""Tests for the budget command and the budget_status helper."""

import json

import pytest

from llm_usage_tracker.cli import main
from llm_usage_tracker.tracker import UsageTracker, budget_status


def make_log(path, rows):
    tracker = UsageTracker(log_path=str(path))
    for provider, model, prompt, completion in rows:
        tracker.record(provider, model, prompt, completion)
    return str(path)


def test_budget_status_ok():
    status = budget_status(0.5, 10.0)
    assert status["status"] == "ok"
    assert status["pct_used"] == 5.0
    assert status["total_cost_usd"] == 0.5
    assert status["max_usd"] == 10.0


def test_budget_status_warning_at_band():
    # exactly 80% of the budget counts as a warning
    assert budget_status(8.0, 10.0)["status"] == "warning"


def test_budget_status_warning_just_under_max():
    assert budget_status(9.99, 10.0)["status"] == "warning"


def test_budget_status_exceeded_at_max():
    assert budget_status(10.0, 10.0)["status"] == "exceeded"
    assert budget_status(12.5, 10.0)["status"] == "exceeded"


def test_budget_status_custom_warn_pct():
    assert budget_status(5.0, 10.0, warn_pct=60.0)["status"] == "ok"
    assert budget_status(6.0, 10.0, warn_pct=60.0)["status"] == "warning"


def test_budget_status_rejects_bad_budget():
    with pytest.raises(ValueError):
        budget_status(1.0, 0)
    with pytest.raises(ValueError):
        budget_status(1.0, -5.0)


def test_budget_status_rejects_bad_warn_pct():
    with pytest.raises(ValueError):
        budget_status(1.0, 10.0, warn_pct=-1)
    with pytest.raises(ValueError):
        budget_status(1.0, 10.0, warn_pct=101)


def test_budget_cli_within_budget(tmp_path, capsys):
    log = make_log(
        tmp_path / "usage.jsonl",
        [("openai", "gpt-4o-mini", 1000, 1000)],  # cost $0.00075
    )
    assert main(["budget", log, "--max", "1.0"]) == 0
    out = capsys.readouterr().out
    assert "within budget" in out
    assert "0.1%" in out


def test_budget_cli_warning_band(tmp_path, capsys):
    log = make_log(
        tmp_path / "usage.jsonl",
        [("openai", "gpt-4o-mini", 1000, 1000)],  # 83.3% of $0.0009
    )
    assert main(["budget", log, "--max", "0.0009"]) == 0
    out = capsys.readouterr().out
    assert "WARNING" in out


def test_budget_cli_exceeded(tmp_path, capsys):
    log = make_log(
        tmp_path / "usage.jsonl",
        [("openai", "gpt-4o-mini", 1000, 1000)],
    )
    assert main(["budget", log, "--max", "0.0005"]) == 1
    out = capsys.readouterr().out
    assert "BUDGET EXCEEDED" in out


def test_budget_cli_json_format(tmp_path, capsys):
    log = make_log(
        tmp_path / "usage.jsonl",
        [("openai", "gpt-4o-mini", 1000, 1000)],
    )
    assert main(["budget", log, "--max", "0.0005", "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "exceeded"
    assert data["total_cost_usd"] == pytest.approx(0.00075)
    assert data["pct_used"] == pytest.approx(150.0)


def test_budget_cli_rejects_bad_max(tmp_path, capsys):
    log = make_log(
        tmp_path / "usage.jsonl",
        [("openai", "gpt-4o-mini", 1000, 1000)],
    )
    assert main(["budget", log, "--max=-1"]) == 1
    assert "budget must be greater than zero" in capsys.readouterr().err
