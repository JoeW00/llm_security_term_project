#!/usr/bin/env python3
"""PostToolUse hook.

After any edit to a Python file under ``soc_agent/`` or ``tests/``:

  1. Format just that file with ``ruff format`` (no-op if ruff is unavailable).
  2. Run the full pytest suite — it is fast and deterministic, so this catches
     contract regressions (e.g. a change to ``state.py`` breaking routing) the
     moment they happen.

Exits 2 with the failing output on stdout/stderr so Claude sees and fixes it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    path = data.get("tool_input", {}).get("file_path", "")
    if not path.endswith(".py"):
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    try:
        rel = os.path.relpath(path, project_dir)
    except ValueError:
        rel = path

    if not (rel.startswith("soc_agent/") or rel.startswith("tests/")):
        sys.exit(0)

    # Format only the edited file; ignore failures (e.g. ruff not installed).
    subprocess.run(
        ["uv", "run", "ruff", "format", path],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(f"pytest failed after editing {rel}:\n")
        sys.stderr.write((result.stdout or "")[-3000:])
        sys.stderr.write((result.stderr or "")[-1000:])
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
