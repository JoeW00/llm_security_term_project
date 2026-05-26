#!/usr/bin/env python3
"""PreToolUse guard hook.

Requires explicit confirmation before editing the two shared integration points
of the SOC agent:

  * ``soc_agent/state.py`` — the ``IncidentState`` contract every node and all
    four subsystems (Plans A–D) depend on.
  * ``data/sample_alerts/`` — the reproducible fixtures the test suite asserts
    against.

A change to either can silently break a teammate's subsystem or the whole
suite, so we surface a confirmation prompt rather than blocking outright.
"""

from __future__ import annotations

import json
import os
import sys

PROTECTED_PREFIXES = ("soc_agent/state.py", "data/sample_alerts/")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    path = data.get("tool_input", {}).get("file_path", "")
    if not path:
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    try:
        rel = os.path.relpath(path, project_dir)
    except ValueError:
        rel = path

    if any(rel.startswith(prefix) for prefix in PROTECTED_PREFIXES):
        reason = (
            f"{rel} is a shared integration point (IncidentState contract / "
            "sample-alert fixtures). Changes here can break every teammate's "
            "subsystem and the test suite. Confirm this edit is intentional."
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
