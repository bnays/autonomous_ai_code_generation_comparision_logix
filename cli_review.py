"""
Walks through a results file and asks you to enter a usability score (0-10)
for each final attempt, the same way NIT6001's expert-review dimension worked.
Only scores the LAST turn per (task, model, mode) -- i.e. the final attempt,
since that's what would actually ship.

Usability is only a defined dimension for tasks whose tasks.json entry lists
it (page-level/cross-cutting integration tasks -- FE1, INT1, FE2 as of this
writing) -- every other task is skipped entirely and keeps
usability_score = null. Read from tasks.json's "dimensions" field rather
than hardcoded here, so adding a task doesn't require touching this file.

Before each prompt, prints the actual generated code from
results/generated/<run_id>/ for that task/model pair, so you're reviewing
real code instead of guessing from test output alone.

Usage: python cli_review.py results/results-<run_id>.jsonl
"""

import sys
import os
import json


def load_tasks_json(base_dir):
    with open(os.path.join(base_dir, "tasks.json")) as f:
        return json.load(f)


def load_target_files(tasks):
    return {t["task_id"]: t["target_file"] for t in tasks}


def load_usability_tasks(tasks):
    return {t["task_id"] for t in tasks if "Usability" in t.get("dimensions", [])}


def load_generated_code(base_dir, run_id, task_id, model_name, mode, turn, target_file):
    basename = os.path.basename(target_file)
    path = os.path.join(
        base_dir, "results", "generated", run_id,
        f"{task_id}__{model_name}__{mode}__turn{turn}__{basename}",
    )
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read()


def main():
    if len(sys.argv) != 2:
        print("Usage: python cli_review.py <results.jsonl>")
        sys.exit(1)

    path = sys.argv[1]
    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_id = os.path.basename(path)
    if run_id.startswith("results-"):
        run_id = run_id[len("results-"):]
    if run_id.endswith(".jsonl"):
        run_id = run_id[: -len(".jsonl")]
    tasks_json = load_tasks_json(base_dir)
    target_files = load_target_files(tasks_json)
    usability_tasks = load_usability_tasks(tasks_json)

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
        if task_id not in usability_tasks:
            r["usability_score"] = None
            reviewed.append(r)
            continue

        print(f"\n--- {task_id} | {model_name} | {mode} | turn {r['turn']} ---")
        print(f"Passed tests: {r['passed_tests']} | Security findings: {r['security_findings']}")

        code = load_generated_code(base_dir, run_id, task_id, model_name, mode, r["turn"], target_files[task_id])
        if code is None:
            print("(No saved generated code found for this row -- it predates code-capture in loop.py.)")
        else:
            print(f"\n{'=' * 20} {target_files[task_id]} {'=' * 20}")
            print(code)
            print("=" * 60)

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
