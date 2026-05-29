# W15-P1 §B LoRA 微調（資料存檔，非報告）

補報告 §5.2。日期：2026-05-29。硬體：NVIDIA GB10（DGX Spark, aarch64, sm_121）。

## 環境

| 項目 | 值 |
|------|----|
| torch | 2.9.1+cu130（PTX JIT 支援 sm_121；獨立 venv `.venv-finetune`） |
| 套件 | transformers 5.9.0、trl 1.5.1、peft 0.19.1、datasets 4.8.5、accelerate 1.13.0 |
| 路線 | 純 transformers + peft + trl（不用 Unsloth/bitsandbytes，aarch64+Blackwell 相容性考量） |

## 訓練

| 項目 | 值 |
|------|----|
| 基礎模型 | `Qwen/Qwen2.5-3B-Instruct`（非 gated） |
| SFT 樣本數 | 4,000（data/triage/sft.jsonl，沿用 prompts.py 模板） |
| LoRA | r=16, alpha=32, dropout=0.05, target=q/k/v/o/gate/up/down_proj |
| 超參 | bf16, batch=2 × grad_accum=4（有效 8）, lr=2e-4, epochs=3, max_length=1024, seed=42 |
| 步數 | 1,500 |
| 訓練時間 | 2,313 s（≈38.5 分） |
| **最終 train_loss** | **0.1176** |
| mean_token_accuracy | ~0.965 |
| throughput | 5.19 samples/s、0.65 steps/s |

## 產物

| 產物 | 路徑 | 大小 |
|------|------|------|
| 合併權重（HF） | `out/merged-triage/`（model.safetensors） | 6.17 GB |
| GGUF（f16, Qwen2, 434 tensors） | `out/gguf/triage-f16.gguf` | 6.18 GB |
| ollama 模型 | `soc-triage:latest` | 6.2 GB |

## 修正（影響可重現性）

轉檔後 `ollama create` **未自動帶入 chat template**，退成 passthrough `{{ .Prompt }}`：丟掉
system 與 ChatML 標記 → 模型不進入 assistant 模式，輸出散文而非 JSON（冒煙測試一度失敗）。
修法：在 `scripts/finetune/Modelfile` 顯式加入 Qwen2 ChatML `TEMPLATE`（含 `.System` 槽）+
`stop` 標記，並把相對 `FROM` 改為 `../../out/gguf/...`（ollama 以 Modelfile 所在目錄解析相對路徑）。

## 冒煙測試

`OLLAMA_MODEL=soc-triage ... smoke_test.py` → PASS：輸出合法 JSON、`alert_type` 落在
{true_positive, benign_positive, false_positive}。範例輸出：
`{"alert_type": "benign_positive", "severity": "medium", "confidence": 1.0}`。

> 權重與 GGUF 皆在 `.gitignore`（out/、*.gguf）內，不進版控；本檔為耐久存檔。
