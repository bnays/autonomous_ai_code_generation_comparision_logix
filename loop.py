"""
Runs one (task, model) pair through either:
  - "single" mode: one generation, one score. This is your NIT6001-equivalent
    baseline -- run it FIRST, for real, before touching agentic mode.
  - "agentic" mode: generate -> test -> feed failures back -> regenerate,
    up to config.MAX_TURNS_AGENTIC times or until tests+security pass.

Both modes share the same scoring so results are directly comparable.
"""

import re
from harness.config import MAX_TURNS_SINGLE, MAX_TURNS_AGENTIC
from harness.sandbox import Sandbox
from harness.scorer import score_attempt
from harness.model_clients import ModelClient


def extract_code_block(response_text: str) -> str:
    """Pull the first fenced code block out of the model's reply.
    Adjust this if your prompt asks for a diff/patch format instead."""
    match = re.search(r"```(?:\w+)?\n(.*?)```", response_text, re.DOTALL)
    return match.group(1) if match else response_text


def build_initial_prompt(task, context: str) -> str:
    return (
        f"You are working in the Logix warehouse management codebase.\n\n"
        f"Relevant existing code:\n{context}\n\n"
        f"Task: {task.description}\n\n"
        f"Write the complete updated content for {task.target_file}. "
        f"Return only the code in a single fenced code block."
    )


def build_feedback_prompt(test_output: str, security_output: str) -> str:
    return (
        f"Your previous code did not pass. Here is the test output:\n\n"
        f"{test_output}\n\n"
        f"Security scan output:\n\n{security_output}\n\n"
        f"Fix the code. Return the complete updated content for the same file "
        f"in a single fenced code block."
    )


def run_task(task, model_cfg, mode: str, run_id: str) -> list:
    """Returns a list of TurnScore, one per turn attempted."""
    assert mode in ("single", "agentic")
    max_turns = MAX_TURNS_SINGLE if mode == "single" else MAX_TURNS_AGENTIC

    client = ModelClient(model_cfg)
    scores = []

    with Sandbox(run_id=f"{run_id}-{task.task_id}-{model_cfg.name}-{mode}") as sandbox:
        context = sandbox.read_context(task.context_files)
        messages = [{"role": "user", "content": build_initial_prompt(task, context)}]

        for turn in range(1, max_turns + 1):
            reply = client.send(messages)
            code = extract_code_block(reply)
            sandbox.write_file(task.target_file, code)

            score = score_attempt(sandbox, task, model_cfg.name, turn, mode)
            scores.append(score)

            if score.passed_tests and score.security_findings == 0:
                break  # converged -- stop early, don't burn extra turns/cost

            if mode == "single":
                break  # baseline never gets a second attempt, by definition

            # agentic: append this turn's exchange and the feedback, then loop
            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "user",
                "content": build_feedback_prompt(score.test_output, score.security_output),
            })

    return scores
