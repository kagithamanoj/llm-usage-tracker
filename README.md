# llm-usage-tracker

A tiny, dependency-free Python library and CLI for tracking LLM token usage
and cost across providers. Record usage events as your app makes calls, get
cost estimates from a built-in pricing table, and summarize a JSONL log.

## Install

```bash
pip install -e .
```

## Library use

```python
from llm_usage_tracker import UsageTracker

tracker = UsageTracker(log_path="usage.jsonl")
tracker.record("openai", "gpt-4o-mini", prompt_tokens=1200, completion_tokens=300,
               label="summarizer")
print(tracker.summary())
```

## CLI

```bash
llm-usage report usage.jsonl
llm-usage report usage.jsonl --format json
llm-usage budget usage.jsonl --max 10.00
llm-usage budget usage.jsonl --max 10.00 --warn-pct 75 --format json
```

`budget` compares cumulative cost against a threshold: it warns once the
warn band is reached (default 80%) and exits 1 when the budget is exceeded,
so it works as a CI or cron guardrail for spending.

## Pricing

Built-in per-1K-token prices (USD) cover common OpenAI, Anthropic, and
Google models and were last reviewed 2026-09-30. Unknown models fall back
to a conservative default. Override the table in code if prices drift.

## Development

```bash
pip install pytest
pytest
```
