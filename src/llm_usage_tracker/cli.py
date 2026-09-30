"""CLI: report on a JSONL usage log produced by UsageTracker."""

from __future__ import annotations

import argparse
import json
import sys

from .tracker import UsageTracker, load_events


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
    args = parser.parse_args(argv)
    if args.command == "report":
        return cmd_report(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
