# 計畫 A：告警分流（Ingest + Triage）設計 spec

> 建立日期：2026-05-26
> 負責子系統：P1 告警分流（Ingest + Triage ⭐）
> 對應節點：`soc_agent/nodes.ingest`、`soc_agent/nodes.triage`

---

## 1. 目標與範圍

把骨架中確定性的 `ingest` / `triage` stub，換成可接上**本地微調分類器（LoRA +
Ollama）**的真實實作。`triage` 是本子系統的 ⭐ 節點：由告警內容推導
`alert_type`（告警類型）與 `severity`（嚴重度）。

**本 spec 採「整合邊界優先（integration-boundary-first）」策略**：先把工程邊界
與測試立起來——分類器介面、離線確定性預設、Ollama 後端實作、節點替換、評估
框架——讓真正訓練好的 LoRA 權重日後可**零下游改動**地插進來。實際的資料集清理、
LoRA 微調、GGUF 轉檔與 `ollama create`、真實評估數字，屬於**平行的研究／訓練軌**，
不在本 spec 範圍內（見 §8）。

### 設計決策（brainstorming 已確認）

1. **整合邊界優先**：先落地可測試的工程邊界，微調權重後插即可。
2. **分類器預測 `alert_type` + `severity`**：與 spec 原文與現有節點契約一致。
3. **graph 組裝時注入分類器；預設為規則式（rule-based）**：`build_graph()` 用
   `functools.partial` 注入；裸呼叫退回確定性規則式分類器（沿用現有行為，既有測試
   不動）；測試注入 fake；正式環境用 Ollama。**`IncidentState` 不變**（不動受保護檔）。

---

## 2. 模組佈局

```
soc_agent/
    classifier.py        # 新增 —— 可注入的分類邊界（契約 + 預設）
    nodes.py             # 修改 ingest + triage
    graph.py             # 修改 build_graph(classifier=...)
soc_agent/classifiers/
    __init__.py
    ollama.py            # 新增 —— OllamaClassifier（本地微調模型）
eval/
    __init__.py
    zero_shot.py         # 新增 —— 雲端 zero-shot 基線（僅供消融）
    triage_eval.py       # 新增 —— Accuracy/F1/混淆矩陣 + 消融 runner
data/triage/             # 新增 —— GUIDE 衍生的標註留出集（JSONL fixtures）
```

---

## 3. 邊界契約（`soc_agent/classifier.py`）

整個子系統圍繞一個小而清楚的介面：給一筆告警，回傳一個**已驗證**的分類結果。

- **`ClassificationResult`（Pydantic）**：分類器的唯一輸出型別。
  - `alert_type: str`
  - `severity: Severity`（沿用 `state.Severity` 的 `Literal`）
  - `confidence: float`（`0.0–1.0`，供評估與日後路由參考；本階段不寫入 `IncidentState`）
  - **沒有任何未驗證的模型輸出能進入 `IncidentState`**：所有實作都必須回傳本型別。

- **`Classifier`（`typing.Protocol`）**：單一方法
  `classify(self, alert: dict[str, Any]) -> ClassificationResult`。
  以 Protocol 表達結構型介面，任何符合的物件都可注入，便於測試替身。

- **`RuleBasedClassifier`**：**預設**實作，確定性、離線。直接取
  `alert["category"]` / `alert["severity"]`，缺值時安全退回（type→`"unknown"`、
  severity→`"medium"`）。等同今日 `triage` 行為，因此既有測試不動即過。

---

## 4. 分類器實作

### 4.1 `OllamaClassifier`（`soc_agent/classifiers/ollama.py`）—— 正式環境

- 透過 Ollama 呼叫微調後的本地模型，用受限 prompt 取得標籤，**解析後以
  `ClassificationResult` 驗證**才回傳。
- **LLM 信任邊界（CLAUDE.md 規範）**：告警的 `message`、`raw`、`indicators` 是
  **不可信輸入**，只能放進清楚分隔的 user 區段，**絕不**塞進 system prompt；模型
  輸出在進入狀態前一律 Pydantic 驗證；**解析或驗證失敗時，退回
  `RuleBasedClassifier` 的確定性保守結果**（並記錄該次失敗），不得讓畸形輸出污染狀態。
- 本階段**不需要真實權重**：以「可注入的 Ollama client」建構，介面先就緒，權重日後插入。

### 4.2 `ZeroShotClassifier`（`eval/zero_shot.py`）—— 消融基線

- 雲端 zero-shot 分類器，**僅供評估框架的消融比較**使用，不參與正式流程。
- 雲端呼叫須可注入／可 mock，使測試維持離線。

---

## 5. 節點與圖的變更

### 5.1 `triage`

- 簽章改為 `triage(state, *, classifier: Classifier = RuleBasedClassifier()) -> dict[str, Any]`。
- 內部呼叫 `classifier.classify(state["alert"])`，把 `alert_type` / `severity` 寫回
  「部分狀態更新」dict（仍遵守「只回傳更新鍵、不原地改 state」契約）。
- `build_graph()` 透過 `functools.partial(triage, classifier=...)` 注入所選分類器；
  裸呼叫（既有測試、CLI 預設）退回 `RuleBasedClassifier`。

### 5.2 `ingest`

- 維持 `Alert.model_validate` 做入口驗證與正規化。
- 強化**離線 IOC 萃取**：以 regex 從 `message` 抽取 IP / domain / hash，與
  `indicators` 欄位合併去重，輸出到 `iocs`。正規化仍為規則式、確定性。

### 5.3 `IncidentState`

- **不變**。triage 仍只寫 `alert_type` + `severity`；`confidence` 僅用於評估，不入狀態，
  因此不動受保護的 `state.py`。

---

## 6. 測試策略（全部離線、確定性）

- **契約測試**：`ClassificationResult` 的 Pydantic 驗證會拒絕非法 `severity` / 型別。
- **`RuleBasedClassifier`**：既有 `test_triage_sets_type_and_severity` 維持綠燈；
  補缺值退路案例（無 category→`"unknown"`、無 severity→`"medium"`）。
- **注入測試**：`triage(state, classifier=FakeClassifier(...))` 驗證替身結果會流到
  `alert_type` / `severity`；`build_graph(classifier=fake)` 驗證端到端接線。
- **`ingest` IOC 萃取**：IP / domain / hash 自 `message` 抽出、去重、與 `indicators` 合併。
- **`OllamaClassifier`**：以 **mock 的 Ollama client**（無網路）測試——驗證 prompt
  結構（不可信欄位有分隔）、以及模型輸出畸形時會退回規則式保守結果而非污染狀態。
- **評估框架**：以小型標註 fixture 驗證 Accuracy / F1 / 混淆矩陣的計算正確。真實
  模型的評估**執行**是手動腳本，**絕不**進 `pytest`。

---

## 7. 評估與消融（`eval/triage_eval.py`）

- 載入 GUIDE 衍生的標註留出集（`data/triage/*.jsonl`），對**任一** `Classifier`
  跑分，輸出 Accuracy / F1 / 混淆矩陣。
- **消融** = 同一框架跑兩個分類器：`OllamaClassifier`（微調本地）對
  `ZeroShotClassifier`（雲端零樣本），產出第 15 週報告用的並列比較表。

---

## 8. 不在本 spec 範圍（研究／訓練軌另行處理）

實際 LoRA 微調、GGUF 轉檔、`ollama create`、資料集下載與清理、真實評估數字。
本 spec 只負責落地**完整測試過的整合邊界**，使訓練好的模型能無縫接到
`OllamaClassifier` 後方，下游零改動。

---

## 9. 建置順序（TDD，每步可獨立測試）

1. `classifier.py`：`ClassificationResult` + `Classifier` Protocol + `RuleBasedClassifier`（含測試）。
2. 改寫 `triage` 用注入分類器、預設規則式；`build_graph()` 加注入（含注入測試）。
3. 強化 `ingest` IOC 萃取（含測試）。
4. `OllamaClassifier`（以 mock client 建構，**尚無真實權重**，介面就緒，含測試）。
5. `eval/zero_shot.py` + `eval/triage_eval.py` 框架（以 fixture 測指標計算）。
6. 跑 `security-reviewer` + `langgraph-reviewer` subagent（LLM 信任邊界 + 節點契約）。

---

## 10. 相關文件

- 總體設計 spec：`docs/superpowers/specs/2026-05-24-soc-incident-response-agent-design.md`
- 計畫 0（骨架）：`docs/superpowers/plans/2026-05-24-soc-agent-foundation.md`
- 接手筆記：`docs/HANDOFF.md`
- 共享契約：`soc_agent/state.py`（`IncidentState`、`Alert`、`Severity`）
