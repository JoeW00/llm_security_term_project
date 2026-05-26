# 計畫 C LLM 軌：接上真實 Anthropic 後端 設計 spec

> 建立日期：2026-05-26
> 範圍：計畫 C 延伸——把已就緒的推理邊界接上真實 Anthropic LLM（計畫 C spec §9 列為 live 軌）
> 對應：`soc_agent/reasoners/*`、`soc_agent/reasoning.py`、`soc_agent/__main__.py`、`demo/`

---

## 1. 目標與範圍

把計畫 C 已交付的可注入推理邊界（`LLMInvestigator`/`LLMPlaybookGenerator`/`LLMCritic`
+ `AnthropicLLMClient`）真正接上 Anthropic API：補上**失敗時的韌性**（網路／SDK 錯誤要退回
確定性預設、不可讓整條圖崩潰）、加上**工廠 + CLI 旗標 + Demo 切換**讓使用者用自己的金鑰跑真實推理。

**決策（brainstorming 已確認）= 接線 + 韌性，全部離線可測**。實際「帶金鑰跑出真實 verdict 準確率／
rubric／收斂數字」是使用者的手動步驟（需 `ANTHROPIC_API_KEY` + 網路 + 真實費用），不在自動測試內、
也不由本工作執行。

**不在範圍**：實跑 live 評估並記錄數字、prompt 調校、串流輸出、重試／退避策略。

---

## 2. 韌性修補（核心正確性）

目前 live 失敗會讓圖崩潰：reasoner 只 catch `(KeyError, TypeError, ValueError)`，但真實呼叫可能丟
`ConnectionError`（網路）或在 `response.content[0].text` 取值時丟 `IndexError`/`AttributeError`
（空回應／非文字 block）。**在轉接器層把失敗正規化**，讓既有退路接手：

- **`soc_agent/reasoning.py`**：新增 `LLMClientError(Exception)`——`LLMClient.complete` 的契約失敗型別。
- **`AnthropicLLMClient.complete`**（`soc_agent/reasoners/anthropic_client.py`）：把
  `messages.create(...)` 呼叫與 `response.content[0].text` 取值包進 try/except；**任何**失敗
  （網路、SDK 例外、空／非文字 content 造成的 `IndexError`/`AttributeError`）一律改丟
  `LLMClientError`。合法回應仍原樣回傳文字交給 `parse_json` 驗證——**信任邊界不變**。
- **三個 reasoner**（`investigator.py`/`playbook.py`/`critic.py`）：在各自的 except tuple 加入
  `LLMClientError`，使 client 失敗退回確定性預設而非崩潰。

`LLMClient` 契約因此明確化：`complete()` 成功回傳文字，失敗丟 `LLMClientError`。

---

## 3. 接線（工廠 + CLI + Demo）

### 3.1 可選相依
`pyproject.toml` 新增 `[dependency-groups] llm = ["anthropic>=0.40"]`，核心測試套件在未安裝
anthropic 下仍全跑（同 `demo` 群組做法）。

### 3.2 工廠（`soc_agent/reasoners/factory.py`）
- `anthropic_llm_client(model: str = _DEFAULT_MODEL, *, max_tokens: int = 1024) -> AnthropicLLMClient`：
  (1) 先檢查 `ANTHROPIC_API_KEY`，缺則丟清楚的 `RuntimeError`；(2) 延遲 `import anthropic`，未安裝
  則丟清楚 `RuntimeError`（指向 `--group llm`）；(3) 以 `anthropic.Anthropic()` 構建並包成
  `AnthropicLLMClient`。`_DEFAULT_MODEL = "claude-sonnet-4-6"`（可由參數／CLI 覆寫）。
- `llm_reasoners(client: LLMClient) -> dict[str, Any]`：把一個 `LLMClient` 包成三個 LLM reasoner，
  回 `{"investigator": LLMInvestigator(client), "playbook_gen": LLMPlaybookGenerator(client),
  "critic": LLMCritic(client)}`——鍵名對齊 `build_graph` 參數，可直接 `build_graph(**llm_reasoners(client))`。
  以假 `LLMClient` 即可離線測試。

### 3.3 CLI（`soc_agent/__main__.py`）
- `run` 子指令加 `--llm`（旗標）與 `--model`（預設 `claude-sonnet-4-6`）。
- 帶 `--llm`：`client = anthropic_llm_client(model); graph = build_graph(**llm_reasoners(client))`。
- 不帶：維持現行確定性 `build_graph()`，行為不變。
- 啟動範例：`ANTHROPIC_API_KEY=... uv run --group llm python -m soc_agent run data/sample_alerts/ssh_bruteforce.json --llm`。

### 3.4 Demo（`demo/`）
- `IncidentSession.__init__` 加可選參數 `reasoners: dict[str, Any] | None = None`，spread 進
  `build(approval_policy=…, checkpointer=…, **(reasoners or {}))`。controller 仍**不依賴 streamlit、
  不碰 anthropic/env**，以假 reasoners 可離線測試。
- `demo/app.py`（薄層 view）加「使用 live LLM（需 `ANTHROPIC_API_KEY`）」勾選框；勾選時由 view 呼叫
  `anthropic_llm_client` + `llm_reasoners` 建好 reasoners 傳給 `IncidentSession(reasoners=…)`，
  並對缺金鑰／未裝套件顯示友善錯誤。env／anthropic 接觸點留在 view glue。

---

## 4. 測試策略（離線、確定性，不需 anthropic／金鑰）

- **轉接器韌性**：假 client 的 `messages.create` 丟 `ConnectionError` → `complete()` 丟
  `LLMClientError`；假回應 content 為空（`[]`）或非文字 block → `LLMClientError`；合法回應 → 回傳文字。
- **reasoner 退路**：注入一個 `complete` 會丟 `LLMClientError` 的假 client → reasoner 回確定性預設
  （不外漏例外）。
- **工廠**：`llm_reasoners(fake_client)` 回三個鍵且型別正確；`build_graph(**llm_reasoners(fake))`
  端到端可跑；`IncidentSession(reasoners=fake)` 會把 reasoners 轉給 `build_graph`。
- **env 工廠錯誤路徑**：`ANTHROPIC_API_KEY` 未設時 `anthropic_llm_client()` 丟帶清楚訊息的
  `RuntimeError`（用 `monkeypatch.delenv` 測，無需安裝 anthropic、不發網路）。
- `demo/app.py` 仍不單元測試（UI glue，手動驗證）。

---

## 5. 安全與信任邊界（不變）

- 不可信告警／情資文字仍只進 user prompt 的 `<<<CONTEXT>>>` 區段（既有 reasoner prompt 不動）。
- LLM 輸出仍一律經 `parse_json` 以 Pydantic 驗證才入狀態；`LLMCritic` 的 `complete` 仍由 rubric 門檻
  重算、不信任模型旗標。
- 新增的韌性只改「失敗如何被攔截」，不放寬輸出驗證。

---

## 6. 建置順序（TDD）

1. `reasoning.py` 加 `LLMClientError` + `AnthropicLLMClient` 韌性化（含轉接器測試）。
2. 三個 reasoner 的 except tuple 加 `LLMClientError`（含「client 失敗→退路」測試）。
3. `factory.py`（`anthropic_llm_client` + `llm_reasoners`）+ pyproject `llm` 群組（含工廠測試）。
4. CLI `--llm` / `--model` 接線（含旗標解析測試；不發真實呼叫）。
5. `IncidentSession(reasoners=…)` + `demo/app.py` live LLM 勾選框（controller 測試；app.py 手動）。
6. 跑 `security-reviewer`（信任邊界沒被韌性修補放寬）+ `langgraph-reviewer`（注入仍守契約）。

---

## 7. 相關文件

- 計畫 C spec / plan：`docs/superpowers/specs/2026-05-26-plan-c-reasoning-playbook-design.md`、
  `docs/superpowers/plans/2026-05-26-plan-c-reasoning-playbook.md`
- 推理邊界與契約：`soc_agent/reasoning.py`、`soc_agent/reasoners/`（`investigator`/`playbook`/`critic`/`anthropic_client`）
- 圖組裝：`soc_agent/graph.py`（`build_graph(investigator=…, playbook_gen=…, critic=…)`）
- 評估（手動 live 跑數字用）：`eval/reasoning_eval.py`
- Demo：`demo/controller.py`（`IncidentSession`）、`demo/app.py`
