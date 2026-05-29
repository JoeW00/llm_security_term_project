# W15-P1 §A 資料集策展（資料存檔，非報告）

- 資料源：Kaggle `Microsoft/microsoft-security-incident-prediction`（GUIDE_Train.csv，2.4 GB）
- 指令：`uv run python scripts/data/curate_guide.py --input data/triage/raw/GUIDE_Train.csv --limit 5000`
- 日期：2026-05-28　隨機種子：42（蓄水池抽樣 + 切分皆固定）
- 監督標籤：`expected.alert_type = IncidentGrade`（TP/BP/FP），**非** Category（避免規則式不勞而獲）

## 統計（補報告 §3.2）

| 指標 | 值 |
|------|----|
| scanned_rows | 9,516,837 |
| valid_unique（去重後合法標籤列） | 83,607 |
| kept（抽樣保留） | 5,000 |
| train | 4,000 |
| holdout | 1,000 |

### 類別分布（alert_type = IncidentGrade）

| 類別 | 數量 | 佔比 |
|------|------|------|
| benign_positive | 3,148 | 63.0% |
| false_positive | 1,370 | 27.4% |
| true_positive | 482 | 9.6% |

severity：GUIDE_Train.csv **無 Severity 欄** → `severity_is_ground_truth=false`，所有 severity 預設 `medium`，不進 `expected`。故 §C 消融會**略過 severity 評估**（只評 alert_type）。

## 觀察與限制（影響 §6.3 解讀）

1. **類別不平衡**：true_positive 僅 ~9.6%。macro-F1 對 TP 召回率敏感；如要改善可對**訓練集**（非留出集）重採樣（指南 §A.3），目前先用自然分布，誠實反映 GUIDE 真實偏斜。
2. **GUIDE 特徵已匿名化**：`AlertTitle`（→ message）與實體值（IpAddress/Url/Sha256/...）皆為整數編碼 ID（如 `message="59286"`、`indicators=["360606", ...]`）。可讀訊號主要是 `category`（如 `exfiltration`）。⇒ 分流是從「category + 實體出現結構」學，不是從告警文字語意學。
3. **任務非退化**：因 expected=IncidentGrade 而非 category，RuleBasedClassifier（回傳 category）無法不勞而獲；三臂都得真的研判。

> 留出集 `holdout.jsonl` 保留自然分布，作為三臂共同的公平評估集。原始 CSV 與 train/holdout/stats 皆在 `.gitignore` 內（不進版控）；本檔為耐久存檔。
