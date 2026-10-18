# LLM Code-Gen Experiment Harness

Compares GPT, Gemini and Claude on real tasks in a production-style codebase (Logix), under two conditions: single-turn generation and agentic self-correction. Scores test pass rate, security findings, maintainability, consistency and usability.

## 1. Setup

```bash
pip install -r requirements.txt

export OPENAI_API_KEY=
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...
export LOGIX_REPO_PATH=/path/to/a/clean/local/clone/of/logix
```

Clone Logix fresh somewhere dedicated to this — the sandbox creates disposable
git worktrees from this path per task/model/turn, so it must be a clean repo
with no uncommitted changes, but it should NOT be your everyday working copy.

## 2. Replace the example tasks

Edit `tasks.json` (or copy it to `tasks.json` and point
`TASKS_FILE` at it) with your real ~20 tasks: real target files, real test
commands that exist in your repo, real security scan commands.

Test every `test_command` and `security_scan_command` manually in a shell
first, inside a worktree, before trusting the harness to run them —
a broken command will silently look like "model failed" otherwise.

## 3. Run the single-turn baseline first

Do this before anything agentic — you need a real baseline to compare against:

```bash
python run_experiment.py --mode single --run-id baseline1
```

## 4. Score usability manually

```bash
python cli_review.py results/results-baseline1.jsonl
```

## 5. Run the agentic condition

```bash
python run_experiment.py --mode agentic --run-id agentic1
python cli_review.py results/results-agentic1.jsonl
```

## 6. Analyse

Load the `*-reviewed.jsonl` files (one JSON object per line: task_id,
model_name, turn, mode, passed_tests, security_findings,
maintainability_index, usability_score) into pandas/R for your ANOVA and
comparison tables.

## Cost/time note

Agentic mode with `MAX_TURNS_AGENTIC=4` means up to 4x the API calls per
task/model versus single-turn. Test on 2-3 tasks first before running the
full set to catch config problems early and estimate cost.
