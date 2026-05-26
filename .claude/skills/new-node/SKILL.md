---
name: new-node
description: Replace a stub node in the SOC agent with a real implementation (Plans A–D), or add a new LangGraph node. Use when implementing a node function in soc_agent/nodes.py, wiring it into the graph, and writing its pytest. Keeps every node consistent with the IncidentState contract.
disable-model-invocation: true
---

# new-node

Scaffold or replace a node in the LangGraph SOC incident-response agent. Every
node is the same shape, so this skill keeps Plans A–D consistent across the
team.

## The contract (read first)

`soc_agent/state.py` defines `IncidentState` (a `TypedDict`, `total=False`) and
the `Alert` Pydantic model. A node:

- Takes the **full** `state: IncidentState`.
- Returns a `dict[str, Any]` of **only the keys it updates** — never the whole
  state. LangGraph merges the partial update.
- Is pure where possible: a real node (LLM call, threat-intel lookup) belongs to
  one subsystem; keep network/LLM calls inside that node, not in `state.py` or
  `routing.py`.

Existing nodes and their replacement plans:

| Node | Stub does | Replace with (plan) |
|------|-----------|---------------------|
| `triage` | reads category/severity | fine-tuned local classifier (Plan A) |
| `enrich` | fakes IOC reputation | real threat-intel tool calls (Plan B) |
| `attack_mapping` | hard-coded `T1110` | retrieval-based MITRE ATT&CK mapping (Plan B) |
| `investigate` | severity heuristic | LLM verdict (Plan C) |
| `playbook` | static 3-phase plan | LLM-generated playbook (Plan C) |
| `critique` | loops once | LLM reflection loop (Plan C/D) |

## Steps

1. **Confirm the target node and plan.** Which stub in `soc_agent/nodes.py` are
   you replacing, and what new `IncidentState` keys (if any) does it read/write?
   New keys must be added to `IncidentState` in `state.py` first — that edit is
   guarded, so confirm it's intentional.

2. **Write/replace the node function** in `soc_agent/nodes.py`. Template:

   ```python
   def NODE_NAME(state: IncidentState) -> dict[str, Any]:
       """<繁中一句話：這個節點做什麼，屬於哪個計畫>。"""
       # Read only what you need from state.
       ...
       # Validate structured output against a Pydantic model where it leaves
       # the trust boundary (especially LLM-generated content).
       return {"KEY": VALUE}  # partial update only
   ```

   - Match the file's style: `from __future__ import annotations` is already at
     the top; docstrings are Traditional Chinese; type hints required.
   - If the node calls an LLM, treat alert fields as **untrusted input** — never
     interpolate raw alert text into a system prompt without separation, and
     validate the model's output against a Pydantic schema before returning it.
     (See the `security-reviewer` subagent.)

3. **Wire it** in `soc_agent/graph.py` if the node is new (`add_node` +
   `add_edge`/`add_conditional_edges`). Replacing an existing stub needs no
   graph change.

4. **Write the test** in `tests/test_nodes.py` (or a new `tests/test_<node>.py`
   for a heavier subsystem). Follow the existing pattern — call the node with a
   minimal state dict and assert on the returned keys:

   ```python
   def test_NODE_does_X():
       out = nodes.NODE_NAME({"<input key>": ...})
       assert out["<output key>"] == ...
   ```

   For nodes that call an LLM or network, inject/patch the client so the test
   stays deterministic and offline (the suite must run with no network).

5. **Run the suite:** `uv run pytest -q`. The PostToolUse hook also runs it
   automatically after your edits.

## Checklist

- [ ] Node returns a partial update, not the full state
- [ ] New `IncidentState` keys added to `state.py` (if any)
- [ ] LLM/tool calls are contained in this node; output validated with Pydantic
- [ ] Alert-derived text treated as untrusted (no prompt injection surface)
- [ ] Test added; `uv run pytest -q` green
- [ ] Routing/loop behavior unchanged unless intended (`route_after_*` in `routing.py`)
