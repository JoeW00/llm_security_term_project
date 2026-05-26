---
name: run-alert
description: Run a sample alert through the SOC agent graph and show the resulting IncidentState / final report. Use to demo the agent or validate the full path vs. the low-risk bypass after changing nodes or routing.
---

# run-alert

Run an alert end-to-end through the LangGraph SOC agent and pretty-print the
result. Use this to demo the pipeline or to sanity-check a change.

## Available sample alerts

- `data/sample_alerts/ssh_bruteforce.json` — high severity → exercises the
  **full path** (`ingest → triage → enrich → investigate → attack_mapping →
  playbook → critique loop → human_approval → report`).
- `data/sample_alerts/info_heartbeat.json` — low severity → exercises the
  **low-risk bypass** (`triage` routes straight to `human_approval`).

List others with: `ls data/sample_alerts/`

## Run it

```bash
uv run python -m soc_agent run data/sample_alerts/ssh_bruteforce.json
```

The CLI prints the `final_report` as JSON. To inspect the **full**
`IncidentState` (every intermediate key, useful when debugging routing or a new
node), invoke the graph directly:

```bash
uv run python -c "import json; from soc_agent.graph import build_graph; \
print(json.dumps(build_graph().invoke({'alert': json.load(open('data/sample_alerts/ssh_bruteforce.json')), 'critique_iterations': 0}), ensure_ascii=False, indent=2))"
```

## What to check

- High-severity alert → `verdict: true_positive`, a 3-phase `playbook`
  (containment / eradication / recovery), and `attack_techniques` populated.
- Low-severity alert → bypass: no enrichment/investigation, goes to approval.
- `critique_iterations` should stop at or below `MAX_CRITIQUE_ITERATIONS` (3) —
  if it doesn't, the reflection loop in `routing.py` regressed.

If output looks wrong, run `uv run pytest -q` to localize the broken node.
