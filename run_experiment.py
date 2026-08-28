"""
Runs the full comparison: every task x every model x both modes (single, agentic).

Usage:
    python run_experiment.py --mode single      # run baseline only first
    python run_experiment.py --mode agentic     # run agentic condition
    python run_experiment.py --mode both        # run both (more API cost)

Before running:
  1. Set env vars: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
  2. Set LOGIX_REPO_PATH to a clean local clone of Logix
  3. Replace tasks.example.json with your real 20-task set
  4. pip install -r requirements.txt
"""

import argparse
import csv
import json
import os
import time
from dataclasses import asdict

from harness.config import MODELS, TASKS_FILE, RESULTS_DIR
from harness.tasks import load_tasks
from harness.loop import run_task


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["single", "agentic", "both"], default="single")
    parser.add_argument("--run-id", default=str(int(time.time())))
    args = parser.parse_args()

    modes = ["single", "agentic"] if args.mode == "both" else [args.mode]

    tasks = load_tasks(TASKS_FILE)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, f"results-{args.run_id}.jsonl")

    print(f"Running {len(tasks)} tasks x {len(MODELS)} models x modes={modes}")
    print(f"Writing results to {out_path}\n")

    with open(out_path, "w") as f:
        for task in tasks:
            for model_cfg in MODELS:
                for mode in modes:
                    print(f"-> {task.task_id} | {model_cfg.name} | {mode}")
                    try:
                        scores = run_task(task, model_cfg, mode, run_id=args.run_id)
                    except Exception as e:
                        print(f"   FAILED: {e}")
                        continue
                    for s in scores:
                        f.write(json.dumps(asdict(s)) + "\n")
                        f.flush()

    print(f"\nDone. Results in {out_path}")
    print("Next: fill in usability scores manually (see cli_review.py), "
          "then run analysis/summarize.py.")


if __name__ == "__main__":
    main()
