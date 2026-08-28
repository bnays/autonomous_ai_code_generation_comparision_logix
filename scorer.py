"""
Scores one attempt against the five NIT6001 dimensions:
  1. Correctness      -> pass/fail from test_command
  2. Code quality      -> Maintainability Index (via radon, Python; adapt for TS)
  3. Security          -> pass/fail + finding count from security_scan_command
  4. Consistency        -> Normalised Edit Distance across repeated runs (computed
                           separately in loop.py by comparing multiple attempts)
  5. Usability          -> NOT automatable. Recorded as a manual score you enter
                           after reviewing the diff (see prompt_for_usability below).
"""

from dataclasses import dataclass, asdict
from harness.sandbox import Sandbox


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


def compute_maintainability_index(sandbox: Sandbox, target_file: str, language: str) -> float | None:
    if language != "python":
        return None  # add a TS/JS equivalent (e.g. via `ts-complexity` or eslint) if needed
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
