"""train.jsonl → 微調用 {system, prompt, completion} 樣本（沿用 prompts.py 模板）。

關鍵：prompt 模板完全沿用 soc_agent.classifiers.prompts，使「訓練時看到的格式」
＝「推論時餵入的格式」。本腳本為離線資料前處理，絕不進 pytest。

用法：uv run python scripts/finetune/build_dataset.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 讓 soc_agent 可匯入

from soc_agent.classifiers.prompts import TRIAGE_SYSTEM_PROMPT, build_triage_prompt  # noqa: E402

SRC = Path("data/triage/train.jsonl")
DST = Path("data/triage/sft.jsonl")


def main() -> None:
    n = 0
    with open(SRC, encoding="utf-8") as f, open(DST, "w", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            # severity 可能不在 expected（GUIDE 無嚴重度真值）；退回 alert 的輸入嚴重度。
            severity = rec["expected"].get("severity") or rec["alert"].get("severity", "medium")
            completion = json.dumps(
                {
                    "alert_type": rec["expected"]["alert_type"],
                    "severity": severity,
                    "confidence": 1.0,
                },
                ensure_ascii=False,
            )
            out.write(
                json.dumps(
                    {
                        "system": TRIAGE_SYSTEM_PROMPT,
                        "prompt": build_triage_prompt(rec["alert"]),
                        "completion": completion,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            n += 1
    print(f"wrote {n} samples -> {DST}")


if __name__ == "__main__":
    main()
