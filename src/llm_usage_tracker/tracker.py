"""Track LLM token usage and cost across providers.

A small, dependency-free library. Record usage events as they happen,
estimate cost from a built-in pricing table, and summarize or export
for reporting. Prices are per 1K tokens in USD and were last reviewed
2026-10-22; override them with your own table if they drift.
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

PRICING_PER_1K_USD = {
    "openai": {
        "gpt-4o": (0.0025, 0.010),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4.1": (0.002, 0.008),
        "gpt-4.1-mini": (0.0004, 0.0016),
    },
    "anthropic": {
        "claude-opus-4-1": (0.015, 0.075),
        "claude-sonnet-4-5": (0.003, 0.015),
        "claude-haiku-4-5": (0.001, 0.005),
    },
    "google": {
        "gemini-2.5-pro": (0.00125, 0.010),
        "gemini-2.5-flash": (0.0003, 0.0025),
    },
    "xai": {
        "grok-4": (0.003, 0.015),
        "grok-4.1-fast": (0.0002, 0.0005),
    },
    "deepseek": {
        # DeepSeek runs off-peak pricing half the day; entries below use the
        # off-peak rates, peak hours bill at double.
        "deepseek-flash": (0.00015, 0.0006),
        "deepseek-v4-pro": (0.00066, 0.00198),
    },
}

DEFAULT_PRICE = (0.002, 0.008)


@dataclass
class UsageEvent:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    timestamp: float = field(default_factory=time.time)
    label: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_usd(self, pricing=PRICING_PER_1K_USD) -> float:
        prompt_price, completion_price = pricing.get(self.provider, {}).get(
            self.model, DEFAULT_PRICE
        )
        return (
            self.prompt_tokens / 1000 * prompt_price
            + self.completion_tokens / 1000 * completion_price
        )

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd(), 6),
            "timestamp": self.timestamp,
            "label": self.label,
        }


class UsageTracker:
    """Collect usage events in memory; append to a JSONL log optionally."""

    def __init__(self, log_path: str | None = None):
        self.events: list[UsageEvent] = []
        self.log_path = log_path

    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        label: str = "",
        timestamp: float | None = None,
    ) -> UsageEvent:
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts cannot be negative")
        event = UsageEvent(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            label=label,
            timestamp=timestamp if timestamp is not None else time.time(),
        )
        self.events.append(event)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        return event

    def summary(self) -> dict:
        """Aggregate totals plus per-model, per-day (UTC), and per-label breakdowns."""
        total_tokens = sum(e.total_tokens for e in self.events)
        total_cost = sum(e.cost_usd() for e in self.events)
        by_model: dict[str, dict] = {}
        by_day: dict[str, dict] = {}
        by_label: dict[str, dict] = {}
        for e in self.events:
            key = f"{e.provider}/{e.model}"
            bucket = by_model.setdefault(
                key, {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            )
            bucket["calls"] += 1
            bucket["tokens"] += e.total_tokens
            bucket["cost_usd"] = round(bucket["cost_usd"] + e.cost_usd(), 6)
            day = (
                datetime.fromtimestamp(e.timestamp, tz=timezone.utc)
                .date()
                .isoformat()
            )
            day_bucket = by_day.setdefault(
                day, {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            )
            day_bucket["calls"] += 1
            day_bucket["tokens"] += e.total_tokens
            day_bucket["cost_usd"] = round(day_bucket["cost_usd"] + e.cost_usd(), 6)
            label_key = e.label if e.label else "(unlabeled)"
            label_bucket = by_label.setdefault(
                label_key, {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            )
            label_bucket["calls"] += 1
            label_bucket["tokens"] += e.total_tokens
            label_bucket["cost_usd"] = round(
                label_bucket["cost_usd"] + e.cost_usd(), 6
            )
        return {
            "calls": len(self.events),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "by_model": by_model,
            "by_day": by_day,
            "by_label": by_label,
        }


def load_events(log_path: str) -> list[dict]:
    events = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def summary_to_csv(summary: dict) -> str:
    """Render a summary() dict as CSV for spreadsheet import.

    One row per model and one per UTC day, followed by an overall totals
    row. Columns: section, group, calls, tokens, cost_usd.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "group", "calls", "tokens", "cost_usd"])
    for model, bucket in sorted(summary.get("by_model", {}).items()):
        writer.writerow(
            [
                "model",
                model,
                bucket["calls"],
                bucket["tokens"],
                f"{bucket['cost_usd']:.6f}",
            ]
        )
    for day, bucket in sorted(summary.get("by_day", {}).items()):
        writer.writerow(
            [
                "day",
                day,
                bucket["calls"],
                bucket["tokens"],
                f"{bucket['cost_usd']:.6f}",
            ]
        )
    writer.writerow(
        [
            "total",
            "all",
            summary.get("calls", 0),
            summary.get("total_tokens", 0),
            f"{summary.get('total_cost_usd', 0.0):.6f}",
        ]
    )
    return buf.getvalue()


def budget_status(
    total_cost_usd: float, max_usd: float, warn_pct: float = 80.0
) -> dict:
    """Compare cumulative cost against a budget threshold.

    Status is "ok" under the warning band, "warning" once warn_pct of the
    budget is used, and "exceeded" at or past max_usd.
    """
    if max_usd <= 0:
        raise ValueError("budget must be greater than zero")
    if not 0 <= warn_pct <= 100:
        raise ValueError("warn_pct must be between 0 and 100")
    pct = total_cost_usd / max_usd * 100
    if pct >= 100:
        status = "exceeded"
    elif pct >= warn_pct:
        status = "warning"
    else:
        status = "ok"
    return {
        "total_cost_usd": round(total_cost_usd, 6),
        "max_usd": max_usd,
        "pct_used": round(pct, 1),
        "warn_pct": warn_pct,
        "status": status,
    }
