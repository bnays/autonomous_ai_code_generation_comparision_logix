"""
Loads task definitions from a JSON file.

Each task describes one unit of the benchmark: what to ask the model for,
which file(s) it should touch, how to test the result, and how to scan it.
Replace tasks.json with your real 10-task Logix set.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Task:
    task_id: str                 # e.g. "FE2", "BE2", "DB2"
    category: str                # "FE" | "BE" | "PY" | "DB" | "INT"
    description: str             # the prompt given to the model
    context_files: List[str]     # relative paths in the repo to include as context
    target_file: str             # relative path the model's output should modify/create
    test_command: str            # shell command to run this task's tests, e.g. "npx jest tasks/fe2.test.ts"
    security_scan_command: Optional[str] = None  # e.g. "semgrep --config=auto <file>" or "bandit <file>"
    language: str = "typescript"  # "typescript" | "python" | "sql"
    dimensions: List[str] = field(default_factory=list)
    # Which of Correctness/Quality/Security/Usability/Consistency this task
    # is evaluated on. Correctness and Quality apply to every task (computed
    # automatically from test results and MI/complexity respectively) but are
    # still listed explicitly here so this field is the single source of
    # truth -- analysis scripts (cli_review.py, analysis/anova.py) read it
    # instead of hardcoding per-task-id sets.


def load_tasks(path: str) -> List[Task]:
    with open(path, "r") as f:
        raw = json.load(f)
    return [Task(**t) for t in raw]
