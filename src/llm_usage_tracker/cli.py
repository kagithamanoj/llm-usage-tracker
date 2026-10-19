"""CLI: report on a JSONL usage log produced by UsageTracker."""

from __future__ import annotations

import argparse
import json
import sys

from .tracker import UsageTracker, budget_status, load_events


def cmd_report(args: argparse.Namespace) -> int:
    tracker = UsageTracker()
    for row in load_events(args.log):
        tracker.record(
            row["provider"],
            row["model"],
            row["prompt_tokens"],
            row["completion_tokens"],
            label=row.get("label", ""),
        )
    summary = tracker.summary()
    if args.format == "json":
        print(json.dumps(summary, indent=2))
        return 0
    print(f"Calls:          {summary['calls']}")
    print(f"Total tokens:   {summary['total_tokens']:,}")
    print(f"Total cost:     ${summary['total_cost_usd']:.4f} USD")
    print()
    print(f"{'Model':<32}{'Calls':>8}{'Tokens':>12}{'Cost USD':>12}")
    for model, bucket in sorted(summary["by_model"].items()):
        print(
            f"{model:<32}{bucket['calls']:>8}{bucket['tokens']:>12}"
            f"{bucket['cost_usd']:>12.4f}"
        )
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    tracker = UsageTracker()
    for row in load_events(args.log):
        tracker.record(
            row["provider"],
            row["model"],
            row["prompt_tokens"],
            row["completion_tokens"],
            label=row.get("label", ""),
        )
    total_cost = tracker.summary()["total_cost_usd"]
    try:
        status = budget_status(total_cost, args.max, warn_pct=args.warn_pct)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(status, indent=2))
    else:
        print(f"Total cost:     ${status['total_cost_usd']:.4f} USD")
        print(f"Budget:         ${status['max_usd']:.4f} USD")
        print(f"Used:           {status['pct_used']:.1f}%")
        if status["status"] == "exceeded":
            print("BUDGET EXCEEDED")
        elif status["status"] == "warning":
            print(f"WARNING: past {status['warn_pct']:.0f}% of budget")
        else:
            print("Status:         within budget")
    return 1 if status["status"] == "exceeded" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm-usage", description="Report LLM token usage and cost."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    report = sub.add_parser("report", help="Summarize a JSONL usage log.")
    report.add_argument("log", help="Path to the JSONL usage log.")
    report.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    budget = sub.add_parser(
        "budget", help="Warn when cumulative cost passes a threshold."
    )
    budget.add_argument("log", help="Path to the JSONL usage log.")
    budget.add_argument(
        "--max",
        type=float,
        required=True,
        help="Budget in USD. Exits 1 when cumulative cost reaches it.",
    )
    budget.add_argument(
        "--warn-pct",
        type=float,
        default=80.0,
        help="Warn once this percent of the budget is used (default 80).",
    )
    budget.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    args = parser.parse_args(argv)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "budget":
        return cmd_budget(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
