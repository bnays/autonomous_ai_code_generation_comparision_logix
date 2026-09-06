"""
Two-way ANOVA (model x mode), per Methodology section 5.4, across five
outcome measures:

  1. Correctness  -- passed_tests (0/1), all 5 tasks              n=5/cell
  2. Quality       -- maintainability_index, all 5 tasks            n=5/cell
  3. Security      -- derived pass/fail from embedded jest security
                       tests, BE1 + DB1 only (the only two tasks with
                       an embedded security-test subset; no separate
                       scanner was configured for any task)          n=2/cell
  4. Usability     -- usability_score, FE1 + INT1 only (the only two
                       tasks with a scored usability dimension)      n=2/cell
  5. Consistency   -- pairwise NED, INT1 only, model main effect
                       only (NED is single-turn-by-definition, so
                       there is no "mode" factor to test)            n=3/group

Uses statsmodels (OLS + Type II anova_lm) for the two-way tests and
scipy.stats.f_oneway for the one-way consistency test.

Usage:
    python analysis/anova.py
"""

import json
import os
import re
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RESULTS = os.path.join(_BASE_DIR, "results")

SECURITY_TASKS = {"BE1", "DB1"}
USABILITY_TASKS = {"FE1", "INT1"}

SIG_ALPHA = 0.05
MIN_CELL_N_FOR_POWER_NOTE = 5  # below this, flag the test as likely underpowered


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def build_frame():
    single = load_jsonl(os.path.join(_RESULTS, "results-baseline2-reviewed.jsonl"))
    agentic = load_jsonl(os.path.join(_RESULTS, "results-agentic1-reviewed.jsonl"))
    rows = single + agentic
    df = pd.DataFrame(rows)
    df["passed_tests_num"] = df["passed_tests"].astype(int)
    df["security_pass"] = df.apply(derive_security_pass, axis=1)
    return df


def derive_security_pass(row):
    """1 if every test in the suite passed (BE1's suite is entirely
    security tests -- JWT auth middleware; DB1's suite embeds a 4-case
    'SQL injection safety' describe block among 9 tests). Since a
    security-specific test is a subset of the suite, a security test can
    only fail if the suite as a whole reports at least one failure --
    so 100% suite pass implies the security subset passed too. If the
    suite did report failures, this falls back to keyword-matching the
    FAILED test names jest prints, since jest's default reporter only
    lists names for failing tests, not passing ones."""
    if row["task_id"] not in SECURITY_TASKS:
        return np.nan
    output = row["test_output"]
    m = re.search(r"Tests:\s+(?:(\d+) failed, )?(?:(\d+) passed, )?(\d+) total", output)
    if m and (m.group(1) is None or int(m.group(1)) == 0):
        return 1
    # There were reported failures -- check whether any failing test name
    # looks security-related (SQL injection / auth / token / 401 / 403).
    security_kw = re.compile(r"sql injection|token|auth|401|403|jwt", re.IGNORECASE)
    failed_names = re.findall(r"^\s*(?:✕|x)\s+(.+)$", output, re.MULTILINE)
    if any(security_kw.search(n) for n in failed_names):
        return 0
    return 1  # failures existed but none matched a security-test name


def two_way_anova(df, value_col, task_filter=None, label=""):
    sub = df.copy()
    if task_filter is not None:
        sub = sub[sub["task_id"].isin(task_filter)]
    sub = sub.dropna(subset=[value_col])

    n_per_cell = sub.groupby(["model_name", "mode"]).size()
    total_n = len(sub)

    desc = (
        sub.groupby(["model_name", "mode"])[value_col]
        .agg(["mean", "std", "count"])
        .rename(columns={"mean": "mean", "std": "sd", "count": "n"})
        .round(4)
    )

    result = {
        "label": label,
        "value_col": value_col,
        "n_total": total_n,
        "n_per_cell": n_per_cell.to_dict(),
        "min_cell_n": int(n_per_cell.min()) if len(n_per_cell) else 0,
        "descriptives": desc,
        "degenerate": sub[value_col].nunique() <= 1,
    }

    if result["degenerate"]:
        result["anova"] = None
        result["note"] = (
            f"'{value_col}' has zero variance across all {total_n} observations "
            f"(every cell scored the same value) -- F is mathematically undefined "
            f"(0/0). No ANOVA is reported; this is stated as a finding in its own "
            f"right, not a computed non-significant result."
        )
        return result

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = smf.ols(f"{value_col} ~ C(model_name) * C(mode)", data=sub).fit()
        aov = sm.stats.anova_lm(model, typ=2)

    result["anova"] = aov
    result["note"] = None
    return result


def print_two_way(result):
    print(f"\n{'=' * 78}\n{result['label']}  (DV = {result['value_col']})\n{'=' * 78}")
    print(f"Total N = {result['n_total']}, n per cell = {result['n_per_cell']}, min cell n = {result['min_cell_n']}")
    if result["min_cell_n"] < MIN_CELL_N_FOR_POWER_NOTE:
        print(f"*** LOW POWER WARNING: min cell n = {result['min_cell_n']} (< {MIN_CELL_N_FOR_POWER_NOTE}). "
              f"With this few observations per cell, treat any p-value here as indicative, not confirmatory. ***")

    print("\nDescriptive stats (mean, sd, n) per model x mode:")
    print(result["descriptives"].to_string())

    if result["degenerate"]:
        print(f"\nANOVA: NOT COMPUTABLE -- {result['note']}")
        return

    aov = result["anova"]
    print("\nType II ANOVA:")
    print(f"{'source':22} {'sum_sq':>10} {'df':>5} {'F':>10} {'p-value':>10}  significant(p<.05)")
    for source in aov.index:
        if source == "Residual":
            continue
        row = aov.loc[source]
        f_val = row["F"]
        p_val = row["PR(>F)"]
        sig = "YES" if pd.notna(p_val) and p_val < SIG_ALPHA else "no"
        print(f"{source:22} {row['sum_sq']:>10.4f} {row['df']:>5.0f} {f_val:>10.4f} {p_val:>10.4f}  {sig}")


def one_way_consistency():
    path = os.path.join(_RESULTS, "consistency-int1.json")
    with open(path) as f:
        data = json.load(f)

    groups = {}
    for model, info in data["per_model"].items():
        groups[model] = [p["ned"] for p in info["pairwise_ned"]]

    print(f"\n{'=' * 78}\nConsistency (NED) -- one-way ANOVA, model main effect only, INT1, single-turn\n{'=' * 78}")
    print("(No 'mode' factor: NED is computed only over repeated single-turn generations,")
    print(" so there is nothing to compare it against under agentic mode.)\n")
    print(f"n per model = 3 (the 3 pairwise NED values among 3 repeated generations)")
    print("*** VALIDITY WARNING: the 3 pairwise NED values per model are NOT independent "
          "samples -- all 3 are derived from the same 3 underlying generations (r1-r2, r1-r3, "
          "r2-r3 share members), so they are correlated by construction. A one-way ANOVA here "
          "treats them as if independent, which violates the test's core assumption. Combined "
          "with n=3 per group, this result should be read as descriptive, not inferential. ***\n")

    print("Descriptive stats (mean, sd, n) per model:")
    for model, vals in groups.items():
        arr = np.array(vals)
        print(f"  {model:8} mean={arr.mean():.4f}  sd={arr.std(ddof=1):.4f}  n={len(arr)}  values={[round(v,4) for v in vals]}")

    f_val, p_val = stats.f_oneway(*groups.values())
    sig = "YES" if p_val < SIG_ALPHA else "no"
    print(f"\nOne-way ANOVA: F = {f_val:.4f}, p = {p_val:.4f}, significant(p<.05) = {sig}")


def main():
    df = build_frame()

    r1 = two_way_anova(df, "passed_tests_num", task_filter=None, label="1. Correctness (all 5 tasks)")
    print_two_way(r1)

    r2 = two_way_anova(df, "maintainability_index", task_filter=None, label="2. Quality / Maintainability Index (all 5 tasks)")
    print_two_way(r2)

    r3 = two_way_anova(df, "security_pass", task_filter=SECURITY_TASKS, label="3. Security (BE1 + DB1 only -- embedded jest security tests)")
    print_two_way(r3)

    r4 = two_way_anova(df, "usability_score", task_filter=USABILITY_TASKS, label="4. Usability (FE1 + INT1 only)")
    print_two_way(r4)

    one_way_consistency()


if __name__ == "__main__":
    main()
