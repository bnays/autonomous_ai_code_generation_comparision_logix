# LLM Code-Gen Experiment Harness (NIT6002)

This runs your real single-turn baseline and agentic self-correction comparison
across GPT / Gemini / Claude on the Logix codebase, replacing the NIT6001 data
that wasn't from actual runs.

## 1. Setup

```bash
pip install -r requirements.txt

export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...
export LOGIX_REPO_PATH=/path/to/a/clean/local/clone/of/logix
```

Clone Logix fresh somewhere dedicated to this — the sandbox creates disposable
git worktrees from this path per task/model/turn, so it must be a clean repo
with no uncommitted changes, but it should NOT be your everyday working copy.

## 2. Replace the example tasks

Edit `tasks.example.json` (or copy it to `tasks.json` and point
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

## What's NOT built for you (on purpose)

- **Real task definitions** — only you know what the 20 Logix tasks should be
- **Consistency (NED) scoring** — run each task 2-3 times per model/mode and
  compute Normalised Edit Distance between the repeated outputs yourself;
  the harness logs every attempt so the raw data is there
- **TS/JS Maintainability Index** — `compute_maintainability_index` only
  handles Python (via `radon`) right now; add an equivalent for your
  TypeScript files if MI matters for those tasks
- **Security scanner output parsing** — the finding-count logic in
  `scorer.py` is a rough heuristic; switch your scanners to `--json` output
  and parse it properly once you've confirmed the schema

## Cost/time note

Agentic mode with `MAX_TURNS_AGENTIC=4` means up to 4x the API calls per
task/model versus single-turn. Test on 2-3 tasks first before running the
full set to catch config problems early and estimate cost.
