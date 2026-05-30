# W15-P1 §A.3 類別平衡重訓：soc-triage（原始）vs soc-triage-balanced

> 來源：`scripts/finetune/build_dataset.py --balanced` + `scripts/finetune/train_lora.py`
> （`SFT_PATH`/`ADAPTER_DIR`/`MERGED_DIR` 環境變數覆寫）→ GGUF → `ollama create
> soc-triage-balanced`。在 `data/triage/holdout.jsonl`（1,000 筆，**自然分布**，未動）
> 上評估。temperature=0。產生時間：2026-05-30。

## 做了什麼

§C 完整消融顯示原微調模型 `soc-triage` **坍縮成多數類 benign_positive**（TP-F1=0）。
本實驗驗證這是否為「類別不平衡」造成的人為現象：

- **訓練集重採樣**：原 train.jsonl 為 BP 2516 / FP 1093 / TP 391（自然分布、嚴重不平衡）。
  對少數類**過採樣**（固定 seed 重複）到與多數類等量 → **TP/BP/FP 各 2516，共 7548 筆**
  （`data/triage/sft_balanced.jsonl`）。
- **重訓**：同 LoRA 超參（r=16, alpha=32, lr=2e-4, 3 epoch），最終 train_loss 0.1033。
- **holdout 不動**：評估仍走自然分布（BP 632 / FP 277 / TP 91），確保可比性。

## 結果（alert_type，holdout 1,000 筆）

| 模型 | accuracy | macro-F1 | TP F1 | BP F1 | FP F1 | TP 召回 | BP 召回 | FP 召回 |
|---|---|---|---|---|---|---|---|---|
| soc-triage（原始） | **0.635** | 0.273 | 0.000 | 0.777 | 0.042 | 0/91 = **0.000** | 0.995 | 0.022 |
| soc-triage-balanced | 0.423 | **0.382** | **0.301** | 0.518 | 0.325 | 39/91 = **0.429** | 0.429 | 0.408 |

> macro-F1 +0.109（0.273→0.382）；TP-F1 0.000→0.301；三類召回從「極度偏多數類」
> （0.995 / 0.022 / 0.000）變成**近乎均衡**（0.429 / 0.408 / 0.429）。

### 混淆矩陣（列=真實 / 欄=預測）

**原始 soc-triage**（989/1000 預測 BP）：

| 真實＼預測 | BP | FP | TP |
|---|---|---|---|
| BP (632) | 629 | 3 | 0 |
| FP (277) | 271 | 6 | 0 |
| TP (91) | 88 | 3 | 0 |

**soc-triage-balanced**（預測分散到三類）：

| 真實＼預測 | BP | FP | TP |
|---|---|---|---|
| BP (632) | 271 | 273 | 88 |
| FP (277) | 123 | 113 | 41 |
| TP (91) | 20 | 32 | 39 |

## 解讀

1. **坍縮是不平衡造成的人為現象，可修正。** 僅改變「訓練集類別比例」（過採樣少數類），
   不動模型、超參、prompt，就讓模型從「一個 `true_positive` 都不預測」變成
   **TP 召回 0.429**。這直接證明 §C 的坍縮源自類別不平衡，而非模型無能或標籤不可學。
2. **accuracy 掉、macro-F1 升——後者才是真相。** acc 0.635→0.423 看似變差，但原本的高 acc
   純粹來自無腦猜多數類（TP 召回 0、對 SOC 毫無價值）。平衡後模型真的在做三類研判，
   macro-F1（不偏袒多數類的指標）由 0.273 升到 0.382。
3. **對 SOC 的實務意義**：Tier-1 分流最在意「**別漏掉真陽性**」。原模型漏掉 100% 的 TP；
   平衡模型抓回 ~43%。即使整體仍不算強（受 §C 已證實的匿名特徵天花板所限），
   在「抓真陽性」這個最關鍵維度上是**質的改善**。
4. **天花板仍在**：三類召回都只到 ~0.41–0.43，與 §C 結論一致——匿名特徵
   （message/indicators 為不透明整數 ID）限制了可達上界。平衡解決的是「坍縮」，
   不是「特徵資訊量不足」。要再往上，需非匿名特徵的資料集。

## 產物

- 平衡資料：`data/triage/sft_balanced.jsonl`（不進版控，可由 `build_dataset.py --balanced` 重生）
- 模型：ollama `soc-triage-balanced`（本機）；HF merged `out/merged-triage-balanced`、
  GGUF `out/gguf/triage-balanced-f16.gguf`（皆不進版控）
- 數值：`results/W15-P1-B2-balanced-retrain.json`
