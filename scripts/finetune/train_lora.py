"""LoRA 微調分流模型——DGX Spark（aarch64 + Blackwell GB10）穩健路徑。

刻意「不」用 Unsloth / bitsandbytes 4-bit：在 aarch64 + Blackwell 上這兩者
的 wheel/核心相容性不穩。DGX Spark 有 128GB 統一記憶體，3B 小模型用 bf16
LoRA 綽綽有餘，改用純 transformers + peft + trl，省去量化工具鏈的痛。

需 GPU，且 `import torch` 必須是 DGX 上 NVIDIA 的 aarch64+CUDA 版（見《執行指南》§2）。
本檔依現行 TRL API（>=0.20：`processing_class`、`SFTConfig.max_length`）撰寫；建議釘版本：
    transformers>=4.46 peft>=0.13 trl>=0.20 datasets>=3.0 accelerate>=1.0
若你裝到較舊 TRL（用 `tokenizer=`/`max_seq_length`），在 DGX 上請 Claude Code 依實際版本微調。

用法（在有 CUDA torch 的環境裡，非必要走 uv）：python scripts/finetune/train_lora.py
產物：out/merged-triage/（已合併 LoRA 的 HF 模型，供轉 GGUF）

路徑可用環境變數覆寫（不覆蓋既有產物，供平衡重訓等變體並存）：
    SFT_PATH=data/triage/sft_balanced.jsonl \
    ADAPTER_DIR=out/lora-triage-balanced MERGED_DIR=out/merged-triage-balanced \
    python scripts/finetune/train_lora.py
"""

from __future__ import annotations

import os
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

# 非 gated，免 HF 授權。要改用 Llama-3.2-3B-Instruct 須先 `huggingface-cli login`。
BASE = "Qwen/Qwen2.5-3B-Instruct"
SFT = os.environ.get("SFT_PATH", "data/triage/sft.jsonl")
ADAPTER_DIR = os.environ.get("ADAPTER_DIR", "out/lora-triage")
MERGED_DIR = os.environ.get("MERGED_DIR", "out/merged-triage")


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit(
            "需要 CUDA 版 torch（見《執行指南》§2）：torch.cuda.is_available() 為 False。"
            " 請在 NGC 容器或裝了 aarch64+CUDA torch 的環境裡跑。"
        )
    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        BASE, torch_dtype=torch.bfloat16, device_map="auto"
    )

    ds = load_dataset("json", data_files=SFT, split="train")

    def fmt(ex: dict) -> dict:
        # 用模型自帶 chat template，使訓練格式對齊推論時 Ollama 的 system/user 結構。
        messages = [
            {"role": "system", "content": ex["system"]},
            {"role": "user", "content": ex["prompt"]},
            {"role": "assistant", "content": ex["completion"]},
        ]
        return {"text": tok.apply_chat_template(messages, tokenize=False)}

    ds = ds.map(fmt, remove_columns=ds.column_names)

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=ds,
        processing_class=tok,
        peft_config=lora,
        args=SFTConfig(
            output_dir=ADAPTER_DIR,
            dataset_text_field="text",
            max_length=1024,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            num_train_epochs=3,
            logging_steps=10,
            bf16=True,
            report_to="none",
            seed=42,
        ),
    )
    trainer.train()  # ← 終端會印出 train loss；記錄最終 loss 回填報告 §5.2
    trainer.save_model(ADAPTER_DIR)

    # 合併 LoRA → 完整模型，供轉 GGUF（Ollama 不直接吃 PEFT adapter）。
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained(MERGED_DIR)
    tok.save_pretrained(MERGED_DIR)
    print(f"merged model -> {Path(MERGED_DIR).resolve()}")


if __name__ == "__main__":
    main()
