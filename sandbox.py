"""
Creates a disposable git worktree per (task, model, turn) so generated code
is applied and tested in isolation, never touching your real Logix checkout.

Requires REPO_PATH (harness.config.REPO_PATH) to be a clean local clone with
no uncommitted changes.
"""

import subprocess
import tempfile
import shutil
import os
from pathlib import Path

from harness.config import REPO_PATH


class Sandbox:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.worktree_path = Path(tempfile.mkdtemp(prefix=f"logix-sandbox-{run_id}-"))

    def __enter__(self):
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(self.worktree_path)],
            cwd=REPO_PATH,
            check=True,
            capture_output=True,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(self.worktree_path)],
            cwd=REPO_PATH,
            capture_output=True,
        )
        shutil.rmtree(self.worktree_path, ignore_errors=True)

    def read_context(self, relative_paths: list[str]) -> str:
        """Concatenate the given files' contents for use in the model prompt."""
        chunks = []
        for rel in relative_paths:
            full = self.worktree_path / rel
            if full.exists():
                chunks.append(f"# File: {rel}\n{full.read_text()}")
        return "\n\n".join(chunks)

    def write_file(self, relative_path: str, content: str):
        full = self.worktree_path / relative_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    def run_command(self, command: str) -> tuple[int, str]:
        """Run a shell command inside the sandbox. Returns (exit_code, combined_output)."""
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.worktree_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output
