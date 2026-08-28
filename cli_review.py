"""
Walks through a results file and asks you to enter a usability score (0-10)
for each final attempt, the same way NIT6001's expert-review dimension worked.
Only scores the LAST turn per (task, model, mode) -- i.e. the final attempt,
since that's what would actually ship.

Usage: python cli_review.py results/results-<run_id>.jsonl
"""

import sys
import json
from collections import defaultdict


def main():
    if len(sys.argv) != 2:
        print("Usage: python cli_review.py <results.jsonl>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path) as f:
        rows = [json.loads(line) for line in f]

    # keep only the final (highest turn) attempt per task/model/mode
    latest = {}
    for r in rows:
        key = (r["task_id"], r["model_name"], r["mode"])
        if key not in latest or r["turn"] > latest[key]["turn"]:
            latest[key] = r

    reviewed = []
    for (task_id, model_name, mode), r in latest.items():
        print(f"\n--- {task_id} | {model_name} | {mode} | turn {r['turn']} ---")
        print(f"Passed tests: {r['passed_tests']} | Security findings: {r['security_findings']}")
        print("(Open the sandbox output / diff manually to review the actual code)")
        while True:
            val = input("Usability score (0-10): ").strip()
            try:
                r["usability_score"] = float(val)
                break
            except ValueError:
                print("Enter a number 0-10.")
        reviewed.append(r)

    out_path = path.replace(".jsonl", "-reviewed.jsonl")
    with open(out_path, "w") as f:
        for r in reviewed:
            f.write(json.dumps(r) + "\n")

    print(f"\nSaved reviewed results to {out_path}")


if __name__ == "__main__":
    main()
