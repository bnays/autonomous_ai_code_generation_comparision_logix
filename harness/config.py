"""
Central configuration for the LLM code-generation experiment harness.

Fill in the values below to match your actual setup before running anything.
Nothing here executes API calls or touches your repo by itself.
"""

import os
from dataclasses import dataclass, field

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # .../harness/
_PROJECT_ROOT = os.path.dirname(_BASE_DIR)                    # project root, one level up


@dataclass
class ModelConfig:
    name: str            # human-readable label used in results, e.g. "gpt-5"
    provider: str        # "openai" | "anthropic" | "google"
    model_id: str        # the actual model string the provider API expects
    api_key_env: str      # name of the environment variable holding the API key


# --- 1. Register the models you're comparing -------------------------------
# Update model_id values to whatever current model strings you're testing.
MODELS = [
    ModelConfig(name="gpt", provider="openai", model_id="gpt-5", api_key_env="OPENAI_API_KEY"),
    ModelConfig(name="gemini", provider="google", model_id="gemini-3.6-flash", api_key_env="GOOGLE_API_KEY"),
    ModelConfig(name="claude", provider="anthropic", model_id="claude-sonnet-4-6", api_key_env="ANTHROPIC_API_KEY"),
]

# --- 2. Path to a LOCAL, DISPOSABLE clone of Logix --------------------------
# Never point this at your real working copy. Clone Logix fresh into its own
# folder and point this there. The sandbox module creates per-run worktrees
# from this clone so nothing here gets permanently modified.
REPO_PATH = os.environ.get("LOGIX_REPO_PATH")
if not REPO_PATH:
    raise RuntimeError(
        "LOGIX_REPO_PATH is not set. Export it to point at your Logix clone, e.g.:\n"
        '  export LOGIX_REPO_PATH="/path/to/your/logix/clone"'
    )

# --- 3. Iteration settings for the agentic (multi-turn) condition ----------
MAX_TURNS_AGENTIC = 4       # hard cap so a non-converging model can't loop forever
MAX_TURNS_SINGLE = 1        # baseline / NIT6001-equivalent condition

# --- 4. Where results get written -------------------------------------------
RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(_PROJECT_ROOT, "results"))

# --- 5. Task definitions file ------------------------------------------------
TASKS_FILE = os.environ.get(
    "TASKS_FILE", os.path.join(_PROJECT_ROOT, "tasks.json")
)