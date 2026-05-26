# Plan C LLM Track (live Anthropic backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing Plan C reasoner boundary to a real Anthropic LLM — crash-safe (live failures fall back to deterministic), via an optional dependency + factory + CLI flag + demo toggle — all offline-testable.

**Architecture:** Normalize any live-call failure at the adapter (`AnthropicLLMClient.complete` raises a new `LLMClientError`); the three reasoners add `LLMClientError` to their except tuples so they fall back to the deterministic default instead of crashing. A factory builds the live client from env + wraps it into the three reasoners (keys match `build_graph`). The CLI `--llm` flag and a demo checkbox opt in. Real key-bearing runs are a documented manual step.

**Tech Stack:** Python 3.12, LangGraph, Pydantic v2, `anthropic` (optional `llm` group), pytest, ruff, uv.

---

## Background for the implementer

- Plan C already built `soc_agent/reasoning.py` (`LLMClient` Protocol, Pydantic models, `parse_json`), `soc_agent/reasoners/{investigator,playbook,critic}.py` (each: an LLM-backed class wrapping an `LLMClient` with a deterministic fallback, catching `(KeyError, TypeError, ValueError)`), and `soc_agent/reasoners/anthropic_client.py` (`AnthropicLLMClient` wrapping an injected SDK client, returning `response.content[0].text`).
- `build_graph(classifier=None, investigator=None, playbook_gen=None, critic=None, approval_policy=None, checkpointer=None)` injects reasoners via `functools.partial`. Bare `build_graph()` = deterministic defaults.
- `demo/controller.py::IncidentSession(thread_id, *, build=build_graph)` builds the graph with `InterruptApprovalPolicy()` + `MemorySaver()`. `demo/app.py` is the Streamlit view (NOT unit-tested).
- `soc_agent/__main__.py::run(alert_path)` reads an alert JSON and invokes `build_graph()`.
- A post-edit hook auto-runs `ruff format` + `pytest` after edits under `soc_agent/`/`tests/`. It does NOT sort imports — before each commit run `uv run ruff check --fix .` then `uv run ruff check .` (must print "All checks passed!").
- Non-test `.py` files start with `from __future__ import annotations`; test files do NOT (project convention). Type hints; Traditional Chinese docstrings; ruff line-length=100 (E/F/I/UP). ruff `E731` forbids `x = lambda`. Lazy imports *inside a function* are fine (no E402).
- `anthropic` is NOT a dependency and will NOT be installed in the test environment. So: the factory must `import anthropic` **lazily inside the function** (never at module top), and no test may import `anthropic`. Tests cover the no-key path and the wiring with a fake `LLMClient`.
- Baseline: `uv run pytest -q` shows **112 passed**. You are on branch `feat/plan-c-llm-track`. Commit after every task.

### Final file structure this plan produces

```
soc_agent/
    reasoning.py                  # MODIFY (Task 1): add LLMClientError
    reasoners/
        anthropic_client.py       # MODIFY (Task 1): normalize failures -> LLMClientError
        investigator.py           # MODIFY (Task 2): catch LLMClientError
        playbook.py               # MODIFY (Task 2): catch LLMClientError
        critic.py                 # MODIFY (Task 2): catch LLMClientError
        factory.py                # NEW (Task 3): anthropic_llm_client + llm_reasoners
    __main__.py                   # MODIFY (Task 4): --llm / --model
demo/
    controller.py                 # MODIFY (Task 5): IncidentSession(reasoners=...)
    app.py                        # MODIFY (Task 5): live-LLM checkbox (not unit-tested)
pyproject.toml                    # MODIFY (Task 3): add llm = ["anthropic>=0.40"]
tests/
    test_anthropic_client.py      # MODIFY (Task 1): failure-normalization tests
    test_reasoner_llm_fallback.py # NEW (Task 2)
    test_llm_factory.py           # NEW (Task 3)
    test_cli.py                   # MODIFY (Task 4)
    test_demo_controller.py       # MODIFY (Task 5)
```

---

## Task 1: `LLMClientError` + harden `AnthropicLLMClient`

**Files:**
- Modify: `soc_agent/reasoning.py`
- Modify: `soc_agent/reasoners/anthropic_client.py`
- Test: `tests/test_anthropic_client.py`

- [ ] **Step 1: Add the failure tests to `tests/test_anthropic_client.py`**

First, add these two imports at the TOP of `tests/test_anthropic_client.py` (with the existing imports, NOT lower down — appended imports trip ruff E402):

```python
import pytest

from soc_agent.reasoning import LLMClientError
```

Then append these classes and tests at the END of the file (keep the existing test):

```python
class _RaisingMessages:
    def create(self, **kwargs):
        raise ConnectionError("network down")


class _RaisingSDK:
    def __init__(self):
        self.messages = _RaisingMessages()


class _EmptyResponse:
    content = []


class _EmptyMessages:
    def create(self, **kwargs):
        return _EmptyResponse()


class _EmptySDK:
    def __init__(self):
        self.messages = _EmptyMessages()


def test_complete_raises_llmclienterror_on_transport_error():
    client = AnthropicLLMClient(_RaisingSDK(), model="m")
    with pytest.raises(LLMClientError):
        client.complete(system="s", prompt="p")


def test_complete_raises_llmclienterror_on_empty_content():
    client = AnthropicLLMClient(_EmptySDK(), model="m")
    with pytest.raises(LLMClientError):
        client.complete(system="s", prompt="p")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_anthropic_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'LLMClientError'` (and, once that exists, the transport/empty-content cases would raise the raw exception instead of `LLMClientError`).

- [ ] **Step 3a: Add `LLMClientError` to `soc_agent/reasoning.py`**

Immediately after the imports (before `class Investigation`), add:

```python
class LLMClientError(Exception):
    """LLMClient.complete 的失敗：呼叫或回應解析出錯（網路 / SDK / 空回應等）。

    LLMClient 實作在任何失敗時丟此例外，呼叫端（reasoner）據此退回確定性預設。
    """
```

- [ ] **Step 3b: Harden `AnthropicLLMClient.complete` in `soc_agent/reasoners/anthropic_client.py`**

Add the import (below the existing `from typing import ...` line):

```python
from soc_agent.reasoning import LLMClientError
```

Replace the `complete` method body so any failure normalizes to `LLMClientError`:

```python
    def complete(self, *, system: str, prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                system=system,
                max_tokens=self._max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:  # 網路 / SDK / 空或非文字 content 一律正規化為 LLMClientError
            raise LLMClientError(str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_anthropic_client.py -v`
Expected: PASS — the original arg-mapping test plus the two new failure tests (transport error and empty content both raise `LLMClientError`).

- [ ] **Step 5: Lint then commit**

```bash
uv run ruff check --fix .
uv run ruff check .   # must print: All checks passed!
git add soc_agent/reasoning.py soc_agent/reasoners/anthropic_client.py tests/test_anthropic_client.py
git commit -m "feat: normalize AnthropicLLMClient failures into LLMClientError

Co-creating with artificial intelligence."
```

---

## Task 2: reasoners fall back on `LLMClientError`

**Files:**
- Modify: `soc_agent/reasoners/investigator.py`
- Modify: `soc_agent/reasoners/playbook.py`
- Modify: `soc_agent/reasoners/critic.py`
- Test: `tests/test_reasoner_llm_fallback.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_reasoner_llm_fallback.py`:

```python
from soc_agent.reasoners.critic import LLMCritic
from soc_agent.reasoners.investigator import LLMInvestigator
from soc_agent.reasoners.playbook import LLMPlaybookGenerator
from soc_agent.reasoning import LLMClientError


class FailingClient:
    """complete 一律丟 LLMClientError，模擬 live 呼叫失敗。"""

    def complete(self, *, system, prompt):
        raise LLMClientError("boom")


def test_investigator_falls_back_on_llmclienterror():
    inv = LLMInvestigator(client=FailingClient()).assess({"severity": "high"})
    assert inv.verdict == "true_positive"  # rule-based fallback


def test_playbook_falls_back_on_llmclienterror():
    pb = LLMPlaybookGenerator(client=FailingClient()).generate({})
    assert pb.model_dump().keys() == {"containment", "eradication", "recovery"}


def test_critic_falls_back_on_llmclienterror():
    c = LLMCritic(client=FailingClient()).review({"critique_iterations": 0})
    assert c.complete is False  # deterministic fallback, first pass incomplete
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reasoner_llm_fallback.py -v`
Expected: FAIL — the reasoners' `except (KeyError, TypeError, ValueError)` does NOT catch `LLMClientError`, so it propagates and the tests error.

- [ ] **Step 3a: `soc_agent/reasoners/investigator.py`**

Change the import line to add `LLMClientError`:

```python
from soc_agent.reasoning import Investigation, Investigator, LLMClient, LLMClientError, parse_json
```

Change the except clause in `assess`:

```python
        except (KeyError, TypeError, ValueError, LLMClientError):
            return self._fallback.assess(state)
```

- [ ] **Step 3b: `soc_agent/reasoners/playbook.py`**

Add `LLMClientError` to the `from soc_agent.reasoning import ...` line (alphabetical with the other names), then change the except clause in `generate`:

```python
        except (KeyError, TypeError, ValueError, LLMClientError):
            return self._fallback.generate(state)
```

- [ ] **Step 3c: `soc_agent/reasoners/critic.py`**

Add `LLMClientError` to the `from soc_agent.reasoning import ...` line, then change the except clause in `review`:

```python
        except (KeyError, TypeError, ValueError, LLMClientError):
            return self._fallback.review(state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reasoner_llm_fallback.py tests/test_investigator.py tests/test_playbook_reasoner.py tests/test_critic.py -v`
Expected: PASS — the new fallback tests pass and the pre-existing reasoner tests still pass.

- [ ] **Step 5: Lint then commit**

```bash
uv run ruff check --fix .
uv run ruff check .   # must print: All checks passed!
git add soc_agent/reasoners/investigator.py soc_agent/reasoners/playbook.py soc_agent/reasoners/critic.py tests/test_reasoner_llm_fallback.py
git commit -m "feat: reasoners fall back to deterministic on LLMClientError

Co-creating with artificial intelligence."
```

---

## Task 3: factory (`anthropic_llm_client` + `llm_reasoners`) + `llm` dep group

**Files:**
- Create: `soc_agent/reasoners/factory.py`
- Modify: `pyproject.toml`
- Test: `tests/test_llm_factory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm_factory.py`:

```python
import pytest

from soc_agent.graph import build_graph
from soc_agent.reasoners.factory import anthropic_llm_client, llm_reasoners

ALERT = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "brute force",
    "indicators": [],
    "raw": {},
}


class FakeLLMClient:
    def complete(self, *, system, prompt):
        return '{"verdict": "false_positive", "confidence": 0.2, "rationale": "x"}'


def test_llm_reasoners_returns_build_graph_keys():
    r = llm_reasoners(FakeLLMClient())
    assert set(r) == {"investigator", "playbook_gen", "critic"}


def test_llm_reasoners_wire_into_build_graph():
    graph = build_graph(**llm_reasoners(FakeLLMClient()))
    result = graph.invoke({"alert": ALERT, "critique_iterations": 0})
    assert result["final_report"] is not None


def test_anthropic_llm_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        anthropic_llm_client()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'soc_agent.reasoners.factory'`.

- [ ] **Step 3a: Create `soc_agent/reasoners/factory.py`**

```python
"""建構 live LLM reasoner 的工廠：從環境取 Anthropic client，包成三個推理器。

`import anthropic` 為延遲匯入（僅在 anthropic_llm_client 內），核心測試無需安裝 anthropic。
"""

from __future__ import annotations

import os
from typing import Any

from soc_agent.reasoners.anthropic_client import AnthropicLLMClient
from soc_agent.reasoners.critic import LLMCritic
from soc_agent.reasoners.investigator import LLMInvestigator
from soc_agent.reasoners.playbook import LLMPlaybookGenerator
from soc_agent.reasoning import LLMClient

_DEFAULT_MODEL = "claude-sonnet-4-6"


def anthropic_llm_client(
    model: str = _DEFAULT_MODEL, *, max_tokens: int = 1024
) -> AnthropicLLMClient:
    """從 `ANTHROPIC_API_KEY` 建 Anthropic client 並包成 `AnthropicLLMClient`。

    缺金鑰或未安裝 anthropic 套件時，丟帶清楚訊息的 RuntimeError。
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY 未設定；live LLM 需要它（export ANTHROPIC_API_KEY=...）。"
        )
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "未安裝 anthropic 套件；請以 `uv run --group llm ...` 執行或安裝 anthropic。"
        ) from exc
    return AnthropicLLMClient(anthropic.Anthropic(), model=model, max_tokens=max_tokens)


def llm_reasoners(client: LLMClient) -> dict[str, Any]:
    """把一個 LLMClient 包成三個 LLM reasoner；鍵名對齊 build_graph 參數。"""
    return {
        "investigator": LLMInvestigator(client),
        "playbook_gen": LLMPlaybookGenerator(client),
        "critic": LLMCritic(client),
    }
```

- [ ] **Step 3b: Add the `llm` dependency group to `pyproject.toml`**

In `[dependency-groups]`, add the `llm` line so the section reads (keep `dev` and any existing `demo` line):

```toml
[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6"]
demo = ["streamlit>=1.30"]
llm = ["anthropic>=0.40"]
```

(If a `demo` line isn't present, just add the `llm` line alongside `dev`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm_factory.py -v`
Expected: PASS (3 tests). The wiring test runs the graph end-to-end with the fake client (each reasoner either parses the fake JSON or falls back, so the run completes).

- [ ] **Step 5: Lint then commit**

```bash
uv run ruff check --fix .
uv run ruff check .   # must print: All checks passed!
git add soc_agent/reasoners/factory.py pyproject.toml tests/test_llm_factory.py
git commit -m "feat: add LLM reasoner factory and optional anthropic dependency group

Co-creating with artificial intelligence."
```

---

## Task 4: CLI `--llm` / `--model`

**Files:**
- Modify: `soc_agent/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Edit `tests/test_cli.py` (keep the existing test). At the TOP of the file, change the existing import line and add `import pytest` (imports must stay at the top — ruff E402):

```python
import pytest

from soc_agent.__main__ import main, run
```

Then append these tests at the END of the file:

```python
def test_run_default_is_deterministic():
    report = run(ALERT_PATH)
    assert report["verdict"] == "true_positive"  # deterministic path unchanged


def test_run_llm_flag_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        run(ALERT_PATH, use_llm=True)


def test_main_llm_flag_is_wired(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        main(["run", ALERT_PATH, "--llm"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `run()` has no `use_llm` parameter and `main` rejects `--llm`.

- [ ] **Step 3: Update `soc_agent/__main__.py`**

Replace the `run` function:

```python
def run(
    alert_path: str, *, use_llm: bool = False, model: str = "claude-sonnet-4-6"
) -> dict[str, Any]:
    """讀取單筆告警 JSON，跑完整圖，回傳 final_report。

    use_llm=True 時注入 Anthropic-backed 推理器（需 ANTHROPIC_API_KEY + `--group llm`）。
    """
    with open(alert_path, encoding="utf-8") as f:
        alert = json.load(f)
    if use_llm:
        from soc_agent.reasoners.factory import anthropic_llm_client, llm_reasoners

        graph = build_graph(**llm_reasoners(anthropic_llm_client(model)))
    else:
        graph = build_graph()
    result = graph.invoke({"alert": alert, "critique_iterations": 0})
    return result["final_report"]
```

In `main`, add the two arguments to the `run` subparser (after the existing `run_p.add_argument("alert", ...)` line):

```python
    run_p.add_argument("--llm", action="store_true", help="Use the Anthropic LLM reasoners")
    run_p.add_argument(
        "--model", default="claude-sonnet-4-6", help="Anthropic model id (with --llm)"
    )
```

And change the `run` call in the `if args.command == "run":` block:

```python
        report = run(args.alert, use_llm=args.llm, model=args.model)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS — deterministic default unchanged; the `--llm` path routes through the factory (raises the clear key error when `ANTHROPIC_API_KEY` is unset).

- [ ] **Step 5: Lint then commit**

```bash
uv run ruff check --fix .
uv run ruff check .   # must print: All checks passed!
git add soc_agent/__main__.py tests/test_cli.py
git commit -m "feat: add --llm/--model flags to the CLI run command

Co-creating with artificial intelligence."
```

---

## Task 5: demo live-LLM toggle

**Files:**
- Modify: `demo/controller.py`
- Modify: `demo/app.py` (UI glue — not unit-tested)
- Test: `tests/test_demo_controller.py`

- [ ] **Step 1: Write the failing test**

Edit `tests/test_demo_controller.py` (keep existing). Add this import at the TOP of the file (with the existing imports — ruff E402):

```python
from soc_agent.reasoners.factory import llm_reasoners
```

Then append the class and test at the END of the file:

```python
class _FakeLLMClient:
    def complete(self, *, system, prompt):
        return '{"verdict": "false_positive", "confidence": 0.1, "rationale": "fake-llm"}'


def test_incident_session_forwards_injected_reasoners():
    pending = IncidentSession(
        "t-llm", reasoners=llm_reasoners(_FakeLLMClient())
    ).start(HIGH)
    # the injected LLM investigator parsed the fake response -> verdict reflects it
    assert pending.state["verdict"] == "false_positive"
    assert "fake-llm" in pending.state["rationale"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_demo_controller.py -v`
Expected: FAIL — `IncidentSession.__init__` has no `reasoners` parameter.

- [ ] **Step 3a: Update `IncidentSession` in `demo/controller.py`**

Replace the `IncidentSession.__init__` so it accepts and forwards `reasoners`:

```python
    def __init__(
        self,
        thread_id: str,
        *,
        build: Callable[..., Any] = build_graph,
        reasoners: dict[str, Any] | None = None,
    ) -> None:
        self._graph = build(
            approval_policy=InterruptApprovalPolicy(),
            checkpointer=MemorySaver(),
            **(reasoners or {}),
        )
        self._config = {"configurable": {"thread_id": thread_id}}
```

- [ ] **Step 3b: Add the live-LLM checkbox to `demo/app.py`**

Add a checkbox in the sidebar (below the file uploader, before the Run button):

```python
use_llm = st.sidebar.checkbox("使用 live LLM（需 ANTHROPIC_API_KEY）")
```

Replace the `Run` button block so it builds reasoners when the box is checked:

```python
if st.sidebar.button("Run", disabled=alert is None) and alert is not None:
    reasoners = None
    if use_llm:
        try:
            from soc_agent.reasoners.factory import anthropic_llm_client, llm_reasoners

            reasoners = llm_reasoners(anthropic_llm_client())
        except RuntimeError as exc:
            st.sidebar.error(str(exc))
            st.stop()
    session = IncidentSession(thread_id=str(uuid.uuid4()), reasoners=reasoners)
    st.session_state["pending"] = session.start(alert)
    st.session_state["session"] = session
    st.session_state.pop("final_report", None)
```

- [ ] **Step 4: Verify**

```bash
uv run ruff check --fix .
uv run ruff check .                              # must print: All checks passed!
uv run python -c "import ast; ast.parse(open('demo/app.py').read())"   # syntax OK, silent
uv run pytest -q                                 # all pass (app.py not imported by tests)
```

Expected: ruff clean; `ast.parse` silent; pytest all green (the new controller test passes; `app.py` is not imported by tests).

- [ ] **Step 5: Commit**

```bash
git add demo/controller.py demo/app.py tests/test_demo_controller.py
git commit -m "feat: optional live-LLM reasoners in demo (IncidentSession + checkbox)

Co-creating with artificial intelligence."
```

---

## Task 6: Reviews

**No code changes — run the project's review subagents over the diff.**

- [ ] **Step 1: Security review**

Dispatch the `security-reviewer` subagent over the changed files, focusing on: the broad `except Exception` in `AnthropicLLMClient.complete` only normalizes failures (it does not swallow or return unvalidated output — valid responses still flow through `parse_json`); the reasoner fallback on `LLMClientError` doesn't let a failed/half LLM response reach `IncidentState`; the factory reads `ANTHROPIC_API_KEY` from env (no hardcoded secret, no logging of the key); the trust boundary (untrusted text only in the user prompt) is unchanged.

- [ ] **Step 2: LangGraph review**

Dispatch the `langgraph-reviewer` subagent over `soc_agent/__main__.py`, `soc_agent/reasoners/factory.py`, and `demo/controller.py`. Verify: `llm_reasoners(...)` keys (`investigator`/`playbook_gen`/`critic`) exactly match `build_graph` kwargs; `build_graph(**llm_reasoners(...))` preserves the graph contract; `IncidentSession(reasoners=...)` forwarding doesn't break the interrupt/resume path; the deterministic default path is unchanged.

- [ ] **Step 3: Address findings**

Fix any issues raised (write a failing test first for behavioral bugs), re-run `uv run pytest -q`, and commit each fix.

---

## Notes / manual step (NOT this plan — needs your key)

- Run on the real LLM: `ANTHROPIC_API_KEY=... uv run --group llm python -m soc_agent run data/sample_alerts/ssh_bruteforce.json --llm`
- Demo on the real LLM: `uv run --group demo --group llm streamlit run demo/app.py`, then check "使用 live LLM".
- Real eval numbers: build `anthropic_llm_client()`-backed reasoners and use the live graph as the runner for `eval/reasoning_eval.py` (verdict accuracy / rubric / convergence) and `demo/controller.injection_report` / `eval/runtime_metrics.py`. Needs a labeled dataset + network + cost.
```
