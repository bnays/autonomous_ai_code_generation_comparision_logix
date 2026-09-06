"""
Aggregates one or more results-<run_id>-reviewed.jsonl files (the output of
cli_review.py) into a per-model summary across the measurable NIT6001
dimensions, then -- if both a "single" and an "agentic" mode file are given
-- prints a baseline-vs-agentic delta per model.

Dimensions covered:
  1. Correctness      -- test pass rate at the final attempt
  2. Code quality      -- mean maintainability_index (radon MI / ESLint proxy)
  3. Security          -- mean security_findings at the final attempt
  4. Usability          -- mean manual usability_score (FE1/INT1 only)

Consistency (Normalised Edit Distance across repeated runs) is NOT computed
here: this harness runs each (task, model, mode) cell once, so there is no
repeat-run variance to measure it from.

Usage:
    python analysis/summarize.py results/results-baseline2-reviewed.jsonl results/results-agentic1-reviewed.jsonl
"""

import sys
import os
import json
from collections import defaultdict


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def per_model_stats(rows):
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model_name"]].append(r)

    stats = {}
    for model, cell_rows in by_model.items():
        n = len(cell_rows)
        passed = sum(1 for r in cell_rows if r["passed_tests"])
        mis = [r["maintainability_index"] for r in cell_rows if r["maintainability_index"] is not None]
        sec = [r["security_findings"] for r in cell_rows]
        us = [r["usability_score"] for r in cell_rows if r["usability_score"] is not None]
        stats[model] = {
            "n": n,
            "passed": passed,
            "pass_rate": passed / n if n else 0.0,
            "avg_mi": sum(mis) / len(mis) if mis else None,
            "avg_security_findings": sum(sec) / len(sec) if sec else None,
            "avg_usability": sum(us) / len(us) if us else None,
            "n_usability": len(us),
        }
    return stats


def print_table(label, stats):
    print(f"\n=== {label} ===")
    print(f"{'model':8} {'pass rate':>10} {'avg MI':>8} {'avg sec findings':>17} {'avg usability':>14} {'n scored':>9}")
    for model in sorted(stats):
        s = stats[model]
        pass_rate = f"{s['passed']}/{s['n']}"
        avg_mi = f"{s['avg_mi']:.1f}" if s["avg_mi"] is not None else "n/a"
        avg_sec = f"{s['avg_security_findings']:.2f}" if s["avg_security_findings"] is not None else "n/a"
        avg_us = f"{s['avg_usability']:.1f}" if s["avg_usability"] is not None else "n/a"
        print(f"{model:8} {pass_rate:>10} {avg_mi:>8} {avg_sec:>17} {avg_us:>14} {s['n_usability']:>9}")


def print_convergence(label, rows):
    """For agentic mode only: how many turns each cell actually took."""
    if not rows or rows[0].get("mode") != "agentic":
        return
    print(f"\n--- {label}: turns to converge (agentic only) ---")
    by_cell = defaultdict(list)
    for r in rows:
        by_cell[(r["task_id"], r["model_name"])] = r
    for (task, model), r in sorted(by_cell.items()):
        state = "converged" if r["passed_tests"] and r["security_findings"] == 0 else "hit cap, not converged"
        print(f"  {task:5} {model:8} turn {r['turn']}  ({state})")


def print_deltas(single_stats, agentic_stats):
    print("\n=== baseline (single) vs agentic -- per model deltas ===")
    print(f"{'model':8} {'pass rate':>18} {'avg MI':>14} {'avg usability':>16}")
    for model in sorted(set(single_stats) | set(agentic_stats)):
        s = single_stats.get(model, {})
        a = agentic_stats.get(model, {})

        def fmt_pass(d):
            return f"{d['passed']}/{d['n']}" if d else "n/a"

        def fmt_num(v):
            return f"{v:.1f}" if v is not None else "n/a"

        pass_delta = f"{fmt_pass(s)} -> {fmt_pass(a)}"
        mi_delta = f"{fmt_num(s.get('avg_mi'))} -> {fmt_num(a.get('avg_mi'))}"
        us_delta = f"{fmt_num(s.get('avg_usability'))} -> {fmt_num(a.get('avg_usability'))}"
        print(f"{model:8} {pass_delta:>18} {mi_delta:>14} {us_delta:>16}")


def main():
    paths = sys.argv[1:]
    if not paths:
        print("Usage: python analysis/summarize.py <reviewed.jsonl> [more...]")
        sys.exit(1)

    by_mode = {}
    for path in paths:
        rows = load(path)
        mode = rows[0]["mode"] if rows else "?"
        label = f"{os.path.basename(path)} (mode={mode})"
        stats = per_model_stats(rows)
        print_table(label, stats)
        print_convergence(label, rows)
        by_mode[mode] = (rows, stats)

    if "single" in by_mode and "agentic" in by_mode:
        _, single_stats = by_mode["single"]
        _, agentic_stats = by_mode["agentic"]
        print_deltas(single_stats, agentic_stats)


if __name__ == "__main__":
    main()
