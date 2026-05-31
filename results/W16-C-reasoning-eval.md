# W16-C 研判子系統地端評估：確定性 vs 地端 LLM

> 來源：`scripts/eval/run_local_cd_eval.py`（全本地、無金鑰，編排主腦跑 ollama `qwen2.5:7b`）。
> 6 筆標註告警（3 真攻擊 / 3 良性誤報）。產生時間：2026-05-30。

## verdict 準確率（true_positive 為正類）

| runner | accuracy | precision | recall |
|---|---|---|---|
| 確定性預設（rule-based） | 0.500 | 0.500 | 1.000 |
| 地端 LLM（qwen2.5:7b） | **0.833** | **1.000** | **1.000** |

> 確定性研判僅依 severity（high → 一律 true_positive），故對良性高嚴重度告警全判錯；
> 地端 LLM 讀告警內容後能區分真攻擊與良性誤報。

## 反思迴圈收斂

- 確定性：平均迭代 2.00，100% 在 cap=3 內收斂。
- 地端 LLM：平均迭代 2.17，100% 在 cap 內收斂。

## 劇本 rubric（地端 LLM-as-judge，0–5）

`{'coverage': 5, 'executability': 5, 'safety': 5}`

## 平均延遲：確定性 0.004s / 地端 LLM 22.14s（每筆完整路徑）
