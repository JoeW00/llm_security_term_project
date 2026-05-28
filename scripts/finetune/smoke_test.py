"""微調模型冒煙測試：確認 soc-triage 經分類管線能產出**合法 JSON 分類**。

比 `ollama run soc-triage "test"` 更嚴格——後者只證明 GGUF 能載入，不證明輸出能被
`parse_classification` 驗證。本檔直接走 parse；模型若沒輸出合法 JSON 會拋 ValueError。
手動腳本，絕不進 pytest。

用法：OLLAMA_MODEL=soc-triage uv run --group eval python scripts/finetune/smoke_test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ollama  # noqa: E402

from soc_agent.classifiers.ollama import OllamaClassifier  # noqa: E402
from soc_agent.classifiers.prompts import (  # noqa: E402
    TRIAGE_SYSTEM_PROMPT,
    build_triage_prompt,
    parse_classification,
)

MODEL = os.environ.get("OLLAMA_MODEL", "soc-triage")
# 微調目標是 IncidentGrade；冒煙測試要求模型輸出落在這三類（共享 prompt/schema 未硬性
# 限制 alert_type，故在此額外把關，確認微調確實學到了窄標籤空間）。
GRADES = {"true_positive", "benign_positive", "false_positive"}
ALERT = {
    "source": "guide",
    "category": "suspicious login",
    "severity": "high",
    "message": "impossible travel sign-in for user admin from two countries in 5 minutes",
    "indicators": ["198.51.100.7"],
    "raw": {},
}


class _Adapter:
    def generate(self, *, model: str, system: str, prompt: str) -> dict[str, Any]:
        r = ollama.generate(model=model, system=system, prompt=prompt, options={"temperature": 0})
        return {"response": r["response"]}


def main() -> None:
    raw = ollama.generate(
        model=MODEL,
        system=TRIAGE_SYSTEM_PROMPT,
        prompt=build_triage_prompt(ALERT),
        options={"temperature": 0},
    )["response"]
    print("raw model output:", raw)
    # 直接驗證：失敗會拋 ValueError（代表模型沒輸出合法 JSON，需檢查訓練/Modelfile）。
    parsed = parse_classification(raw)
    print("parsed (valid JSON path):", parsed.model_dump())
    if parsed.alert_type not in GRADES:
        raise SystemExit(
            f"alert_type={parsed.alert_type!r} 不在 IncidentGrade 三類 {sorted(GRADES)}；"
            " 微調可能沒收斂到窄標籤空間，請檢查 sft.jsonl 與訓練。"
        )
    # 端到端：經 OllamaClassifier（含退路）。
    e2e = OllamaClassifier(_Adapter(), model=MODEL).classify(ALERT)
    print("end-to-end classify   :", e2e.model_dump())
    print("SMOKE OK: 模型輸出為合法 JSON 且 alert_type 落在 IncidentGrade 三類。")


if __name__ == "__main__":
    main()
