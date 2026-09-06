"""
Walks through a results file and asks you to enter a usability score (0-10)
for each final attempt, the same way NIT6001's expert-review dimension worked.
Only scores the LAST turn per (task, model, mode) -- i.e. the final attempt,
since that's what would actually ship.

Usability is only a defined dimension for FE1 and INT1 (the two tasks with a
real end-user/integration surface) -- BE1, PY1, and DB1 are skipped entirely
and keep usability_score = null.

Before each prompt, prints the actual generated code from
results/generated/<run_id>/ for that task/model pair, so you're reviewing
real code instead of guessing from test output alone.

Usage: python cli_review.py results/results-<run_id>.jsonl
"""

import sys
import os
import json

USABILITY_TASKS = {"FE1", "INT1"}


def load_target_files(base_dir):
    with open(os.path.join(base_dir, "tasks.json")) as f:
        tasks = json.load(f)
    return {t["task_id"]: t["target_file"] for t in tasks}


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
    target_files = load_target_files(base_dir)

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
        if task_id not in USABILITY_TASKS:
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
