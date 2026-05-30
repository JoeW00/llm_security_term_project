# W15-P1 §C 消融（完整四臂）：規則式 vs 本地零樣本（同基底 / 大模型）vs 微調本地

> 來源：`scripts/eval/run_ablation.py`（**全本地、無金鑰**，告警不送出企業邊界）。
> 留出集 `data/triage/holdout.jsonl`（1,000 筆，自然分布）。產生時間：2026-05-30。
> 模型：`qwen2.5:3b`（同基底未微調）、`qwen2.5:32b`（本地能力上界代理）、
> `soc-triage`（§B 的 Qwen2.5-3B + LoRA 微調產物）。四臂共用同一 GRADE prompt
> + Pydantic 驗證 + 失敗退回規則式，確保公平比較。temperature=0（確定性）。
> 留出集 grade 分布：benign_positive 632 / false_positive 277 / true_positive 91（BP 基率 0.632）。

## alert_type（三類：true_positive / benign_positive / false_positive）

| 分類器 | 模型 | accuracy | macro-F1 | TP F1 | BP F1 | FP F1 |
|---|---|---|---|---|---|---|
| rule_based | — | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| zero_shot_local_base | qwen2.5:3b | 0.100 | 0.078 | 0.145 | 0.062 | 0.028 |
| zero_shot_local_large | qwen2.5:32b | 0.095 | 0.070 | 0.164 | 0.000 | 0.047 |
| finetuned_local | soc-triage (3B+LoRA) | **0.635** | **0.273** | 0.000 | 0.777 | 0.042 |

> 註：留出集嚴重不平衡（多數類 `benign_positive` 基率 63.2%），準確率會被多數類灌水，
> **macro-F1 才是真實分流能力指標**。`severity` 因 GUIDE 無嚴重度真值而跳過。
> 完整混淆矩陣見 `…full-ablation.json`。

### 各臂行為（混淆矩陣摘要，列=真實 / 欄=預測）

- **rule_based**：回傳 category（exfiltration/malware/…），永遠不等於 grade 標籤 → 全 0。
  證實任務非退化（category 規則式無法觸及 grade 預測）。沿用既有 partial 檔結論。
- **zero_shot 3b**：把 **944/1000** 判為 `true_positive`（警報狂）。TP 召回不錯（75/91），
  但 BP/FP 幾乎全被誤判成 TP → 在 BP 多數的留出集上 acc 僅 0.10。
- **zero_shot 32b**：比 3b **更極端**——**981/1000** 判為 `true_positive`，**0 個** benign_positive 預測
  （BP F1=0）。放大模型不但沒幫助、反而更退化。
- **finetuned**：坍縮成多數類 `benign_positive`（**900/1000** 預測 BP），**TP 一次都沒預測**
  （TP F1=0）。高 acc（0.635）純粹來自背多數類。

## 解讀（回答兩個科學問題）

### Q1：微調有沒有把模型變差？（同基底 `qwen2.5:3b` vs `finetuned_local`，兩者皆 Qwen2.5-3B）

兩者**各自坍縮到相反的退化解**，但沒有一個學會真正的分流：

- **未微調 base**：坍縮成「**全部都是 true_positive**」（警報狂）→ acc 0.10、macro-F1 0.078。
- **微調後**：坍縮成「**全部都是 benign_positive**」（多數類）→ acc 0.635、macro-F1 0.273。

也就是說 **LoRA 微調確實改變了行為**：它把模型從「無差別警報」拉去「背多數類先驗」，
帳面 acc／macro-F1 都變高（0.078→0.273），**但這個 macro-F1 提升完全來自學會 benign_positive
這個多數類（BP F1 0.78），對最關鍵的 `true_positive` 仍是 F1=0**。微調沒有教會模型偵測真陽性，
只教會它報多數類。先前訓練 loss 0.118 很低是「背多數類 + 固定 prompt」的假象。

### Q2：是資料集限制，還是小模型容量問題？（`qwen2.5:32b` 當能力上界代理）

**強烈指向資料集限制。** 把模型放大到 32B **沒有改善、反而更差**：

- 32B（macro-F1 0.070 / acc 0.095）比同 prompt 的 3B base（0.078 / 0.100）**還低**，
  退化得更徹底（全判 TP、0 個 BP）。
- 若是「小模型容量不足」，放大應該要好轉；這裡放大反而更糟 → 代表瓶頸**不在模型容量**，
  而在**特徵本身沒有可分類的訊號**。GUIDE 的 message/indicators 是匿名整數 ID，零樣本模型
  讀不到語意線索，只能退回各自的預設姿態（這裡是「全部當成攻擊」）。

## 結論

1. **沒有任何一臂學會真正的三類分流**：四臂的 `true_positive` F1 不是 0 就是 ≤0.16，
   且每臂都坍縮到某個退化解。
2. **微調未帶來真實分流能力**：`finetuned_local` 的高 acc/macro-F1 完全來自背多數類
   `benign_positive`（TP F1=0），不是學會偵測真陽性。
3. **資料集是主要瓶頸（非模型容量）**：放大到 32B 反而更差，證明匿名特徵
   （message/indicators 為不透明整數 ID、只有 category 帶弱訊號）＋ 類別不平衡，
   使可達上界極低。
4. **改善方向**：(a) 改用**非匿名**特徵的資料集（讓 message/indicators 真正帶語意）——
   這是天花板問題的根因；(b) 若維持此資料集，訓練時對少數類加權／過採樣
   （見《執行指南》§A.3 類別平衡重訓），至少避免坍縮成單一類；(c) 零樣本臂可加入
   few-shot 範例與機率校準，緩解「全判 TP」的偏置。
