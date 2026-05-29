# W15-P1 §C 消融評估（**部分**，資料存檔，非報告）

補報告 §6.3。日期：2026-05-29。留出集：`data/triage/holdout.jsonl`（1,000 筆）。
目標：`alert_type`（= IncidentGrade）。severity **跳過**（GUIDE 無嚴重度真值）。

> ⚠️ 這是**部分**消融：只有 `rule_based` + `finetuned_local` 兩臂。
> 雲端零樣本臂（`zero_shot_cloud`，需 `ANTHROPIC_API_KEY`）與「類別平衡重訓」**延後**（使用者決定，先存檔）。

## 結果

| 臂 | accuracy | macro-F1 | per-class F1 |
|----|----------|----------|--------------|
| `rule_based` | 0.000 | 0.000 | 全 0（預測的是 category，不是 grade） |
| `finetuned_local`（soc-triage） | **0.636** | **0.273** | BP 0.777 · FP 0.042 · TP 0.000 |

### finetuned_local 混淆矩陣（列=真實，欄=預測）

| 真實＼預測 | benign_positive | false_positive | true_positive |
|-----------|-----------------|----------------|---------------|
| benign_positive (632) | 630 | 2 | 0 |
| false_positive (277) | 271 | 6 | 0 |
| true_positive (91) | 88 | 3 | 0 |

## 關鍵發現

1. **微調模型坍成多數類預測**：989/1000 筆預測為 `benign_positive`（BP 基率 63.2%），
   accuracy 0.636 幾乎等於「永遠猜多數類」。**從不預測 `true_positive`**（最關鍵的資安類別）。
   macro-F1 0.273 揭穿了 accuracy 的假象。
2. **成因**：類別嚴重不平衡（TP 僅 ~10%）**＋** GUIDE 特徵已匿名化（message/indicators 是
   不透明整數 ID），可用訊號幾乎只剩 category，而 category→grade 非確定映射 → 模型退回先驗（多數類）。
   訓練 loss 低（0.118）具誤導性：主要反映記住固定 prompt + 主導的 BP completion。
3. **rule_based = 0.000**：回傳 category（exfiltration/malware/...），永遠不等於 grade →
   證實任務非退化（category 規則式無法觸及 grade 預測）。

## 延後事項（使用者：之後再重做）

- **完整 §C**：設 `ANTHROPIC_API_KEY`（.env）後跑 `scripts/eval/run_ablation.py` 取得
  `zero_shot_cloud` 臂。診斷價值：若 Claude Haiku 在同樣匿名特徵上也接近 63% 基率/低 macro-F1
  → 確認是「資料集限制」；若明顯較高 → 屬微調/容量問題。
- **類別平衡重訓**（指南 §A.3）：對**訓練集**重採樣成 TP/BP/FP 近等量再微調，看 TP 召回是否改善。

> 原始數值見 `results/W15-P1-C-partial-ablation.json`。
