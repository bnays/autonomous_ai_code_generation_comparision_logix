"""
Consistency dimension (Methodology section 3.5): pairwise Normalised Edit
Distance (NED) across repeated single-turn generations of the same task,
per model. Lower NED means the model's output is more consistent
(deterministic) across repeated runs; higher NED means more variability.

    NED(o_i, o_j) = Levenshtein(o_i, o_j) / max(len(o_i), len(o_j))
    NED_avg        = (2 / (n * (n - 1))) * sum over all pairs

Reads the 3 repeat generations per model straight from
results/generated/<run_id_prefix>-r{1,2,3}/, since NED is computed over the
raw generated file content, not the scored TurnScore rows.

Usage:
    python analysis/consistency.py --task INT1 --run-id-prefix consistency1 --repeats 3
"""

import argparse
import itertools
import json
import os

import Levenshtein

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_target_file(task_id):
    with open(os.path.join(_BASE_DIR, "tasks.json")) as f:
        tasks = json.load(f)
    for t in tasks:
        if t["task_id"] == task_id:
            return t["target_file"]
    raise ValueError(f"Unknown task_id: {task_id}")


def load_generation(run_id_prefix, repeat, task_id, model_name, mode, turn, basename):
    path = os.path.join(
        _BASE_DIR, "results", "generated", f"{run_id_prefix}-r{repeat}",
        f"{task_id}__{model_name}__{mode}__turn{turn}__{basename}",
    )
    with open(path) as f:
        return f.read(), path


def ned(a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    return Levenshtein.distance(a, b) / max(len(a), len(b))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="INT1")
    parser.add_argument("--run-id-prefix", default="consistency1")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--mode", default="single")
    parser.add_argument("--turn", type=int, default=1)
    parser.add_argument("--models", nargs="+", default=["gpt", "gemini", "claude"])
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--target-file",
        default=None,
        help="Override: skip the tasks.json lookup and use this target file path directly "
        "(for a task not yet added to tasks.json).",
    )
    args = parser.parse_args()

    basename = os.path.basename(args.target_file) if args.target_file else os.path.basename(load_target_file(args.task))

    results = {}
    for model in args.models:
        generations = []
        for repeat in range(1, args.repeats + 1):
            content, path = load_generation(
                args.run_id_prefix, repeat, args.task, model, args.mode, args.turn, basename
            )
            generations.append({"repeat": repeat, "path": path, "content": content, "chars": len(content)})

        pairs = list(itertools.combinations(range(len(generations)), 2))
        pairwise = []
        for i, j in pairs:
            d = ned(generations[i]["content"], generations[j]["content"])
            pairwise.append({
                "pair": [generations[i]["repeat"], generations[j]["repeat"]],
                "ned": d,
            })

        n = len(generations)
        ned_avg = (2 / (n * (n - 1))) * sum(p["ned"] for p in pairwise) if n > 1 else 0.0

        results[model] = {
            "task_id": args.task,
            "n_generations": n,
            "char_lengths": [g["chars"] for g in generations],
            "pairwise_ned": pairwise,
            "ned_avg": ned_avg,
            "generation_paths": [g["path"] for g in generations],
        }

        print(f"\n{model}:")
        for g in generations:
            print(f"  repeat {g['repeat']}: {g['chars']} chars  ({g['path']})")
        for p in pairwise:
            print(f"  NED(r{p['pair'][0]}, r{p['pair'][1]}) = {p['ned']:.4f}")
        print(f"  NED_avg = {ned_avg:.4f}")

    out_path = args.out or os.path.join(_BASE_DIR, "results", f"consistency-{args.task.lower()}.json")
    with open(out_path, "w") as f:
        json.dump({
            "task_id": args.task,
            "mode": args.mode,
            "run_id_prefix": args.run_id_prefix,
            "repeats": args.repeats,
            "formula": "NED_avg = (2 / (n*(n-1))) * sum(pairwise NED)",
            "per_model": results,
        }, f, indent=2)

    print(f"\nWrote {out_path}")
    print("\n=== Summary: avg NED per model (lower = more consistent) ===")
    for model in args.models:
        print(f"  {model:8} {results[model]['ned_avg']:.4f}")


if __name__ == "__main__":
    main()
