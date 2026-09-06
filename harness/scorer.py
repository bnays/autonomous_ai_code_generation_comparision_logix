"""
Scores one attempt against the five NIT6001 dimensions:
  1. Correctness      -> pass/fail from test_command
  2. Code quality      -> Maintainability Index (via radon for Python; a
                           cyclomatic-complexity-based proxy via ESLint for
                           TypeScript/JavaScript, see compute_js_ts_complexity)
  3. Security          -> pass/fail + finding count from security_scan_command
  4. Consistency        -> Normalised Edit Distance across repeated runs (computed
                           separately in loop.py by comparing multiple attempts)
  5. Usability          -> NOT automatable. Recorded as a manual score you enter
                           after reviewing the diff (see prompt_for_usability below).
"""

from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, asdict
from harness.sandbox import Sandbox

_ESLINT_TOOLING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eslint-tooling")
_ESLINT_BIN = os.path.join(_ESLINT_TOOLING_DIR, "node_modules", ".bin", "eslint")
_ESLINT_CONFIG = os.path.join(_ESLINT_TOOLING_DIR, "complexity.config.mjs")


@dataclass
class TurnScore:
    task_id: str
    model_name: str
    turn: int
    mode: str                 # "single" | "agentic"
    passed_tests: bool
    test_output: str
    security_findings: int
    security_output: str
    maintainability_index: float | None  # None if not computed for this language
    usability_score: float | None = None  # filled in manually, see cli_review.py


def run_tests(sandbox: Sandbox, test_command: str) -> tuple[bool, str]:
    exit_code, output = sandbox.run_command(test_command)
    return exit_code == 0, output


def run_security_scan(sandbox: Sandbox, scan_command: str | None) -> tuple[int, str]:
    if not scan_command:
        return 0, "(no security scan configured for this task)"
    exit_code, output = sandbox.run_command(scan_command)
    # Most scanners return non-zero when findings exist; count occurrences
    # of common finding markers as a rough proxy. Adjust parsing to match
    # your actual scanner's output format (Semgrep/Bandit JSON is more reliable
    # than this line-count heuristic -- swap in --json output and json.loads
    # once you've confirmed the exact schema your scanner version returns).
    finding_count = output.lower().count("finding") + output.lower().count("issue:")
    return finding_count, output


def compute_js_ts_complexity(sandbox: Sandbox, target_file: str) -> float | None:
    """Cyclomatic-complexity-based maintainability proxy for TS/JS, since radon
    only covers Python. Uses a standalone ESLint install owned by this harness
    (harness/eslint-tooling) rather than either target repo's own config --
    client's eslint.config.mjs imports eslint-config-next, which isn't
    installed, and backend has no ESLint at all. The `complexity` rule is set
    to threshold 0 so every function reports its complexity as a message,
    turning the rule into a metric dump instead of a pass/fail lint.

    Not a real Halstead-based Maintainability Index like radon's -- just an
    average-cyclomatic-complexity score linearly mapped onto the same 0-100,
    higher-is-better scale so it stays directionally comparable at a glance.
    A file that fails to parse (e.g. genuinely broken generated code) or
    defines no functions returns None, same as radon's failure case.
    """
    command = (
        f"{shlex.quote(_ESLINT_BIN)} --no-config-lookup "
        f"--config {shlex.quote(_ESLINT_CONFIG)} --format json {shlex.quote(target_file)}"
    )
    _, output = sandbox.run_command(command)
    try:
        results = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return None

    complexities = []
    for file_result in results:
        for message in file_result.get("messages", []):
            match = re.search(r"complexity of (\d+)", message.get("message", ""))
            if match:
                complexities.append(int(match.group(1)))

    if not complexities:
        return None

    avg_complexity = sum(complexities) / len(complexities)
    return max(0.0, round(100.0 - (avg_complexity - 1) * 10, 2))


def compute_maintainability_index(sandbox: Sandbox, target_file: str, language: str) -> float | None:
    if language in ("typescript", "javascript"):
        return compute_js_ts_complexity(sandbox, target_file)
    if language != "python":
        return None
    exit_code, output = sandbox.run_command(f"radon mi {target_file} -s")
    if exit_code != 0:
        return None
    # radon mi output looks like: "path/to/file.py - A (85.32)"
    try:
        return float(output.split("(")[-1].split(")")[0])
    except (IndexError, ValueError):
        return None


def score_attempt(sandbox: Sandbox, task, model_name: str, turn: int, mode: str) -> TurnScore:
    passed, test_output = run_tests(sandbox, task.test_command)
    findings, sec_output = run_security_scan(sandbox, task.security_scan_command)
    mi = compute_maintainability_index(sandbox, task.target_file, task.language)

    return TurnScore(
        task_id=task.task_id,
        model_name=model_name,
        turn=turn,
        mode=mode,
        passed_tests=passed,
        test_output=test_output,
        security_findings=findings,
        security_output=sec_output,
        maintainability_index=mi,
    )
