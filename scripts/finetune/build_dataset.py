"""train.jsonl → 微調用 {system, prompt, completion} 樣本（沿用 prompts.py 模板）。

關鍵：prompt 模板完全沿用 soc_agent.classifiers.prompts，使「訓練時看到的格式」
＝「推論時餵入的格式」。本腳本為離線資料前處理，絕不進 pytest。

用法：
    uv run python scripts/finetune/build_dataset.py                       # 原始自然分布 → sft.jsonl
    uv run python scripts/finetune/build_dataset.py --balanced \
        --dst data/triage/sft_balanced.jsonl                             # 類別平衡（過採樣少數類）

`--balanced`：對 **訓練集**（train.jsonl）按 alert_type 過採樣少數類到多數類數量，
得到近等量的 TP/BP/FP（《執行指南》§A.3）。holdout 不動、評估仍走自然分布。
過採樣以固定 seed 重複既有樣本（資料就這麼多），目的是讓模型別再坍縮成多數類。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 讓 soc_agent 可匯入

from soc_agent.classifiers.prompts import TRIAGE_SYSTEM_PROMPT, build_triage_prompt  # noqa: E402

DEFAULT_SRC = Path("data/triage/train.jsonl")
DEFAULT_DST = Path("data/triage/sft.jsonl")
SEED = 42


def load_records(src: Path) -> list[dict]:
    """讀 train.jsonl 成記錄串列（每筆 {'alert':..., 'expected':...}）。"""
    records: list[dict] = []
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def balance(records: list[dict]) -> list[dict]:
    """按 alert_type 過採樣少數類到多數類數量，回傳打散後的近等量記錄。"""
    rng = random.Random(SEED)
    by_label: dict[str, list[dict]] = {}
    for rec in records:
        by_label.setdefault(rec["expected"]["alert_type"], []).append(rec)
    target = max(len(v) for v in by_label.values())
    out: list[dict] = []
    for _label, recs in by_label.items():
        # 完整重複到 >= target，再裁到剛好 target（最後一輪用洗牌避免固定尾段偏置）。
        pool: list[dict] = []
        while len(pool) < target:
            chunk = recs[:]
            rng.shuffle(chunk)
            pool.extend(chunk)
        out.extend(pool[:target])
    rng.shuffle(out)
    return out


def to_sft(rec: dict) -> dict:
    """單筆記錄 → {system, prompt, completion}（沿用推論時的 prompt 模板）。"""
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
    return {
        "system": TRIAGE_SYSTEM_PROMPT,
        "prompt": build_triage_prompt(rec["alert"]),
        "completion": completion,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="來源 train.jsonl")
    ap.add_argument("--dst", default=str(DEFAULT_DST), help="輸出 sft.jsonl")
    ap.add_argument("--balanced", action="store_true", help="類別平衡：過採樣少數類到多數類數量")
    args = ap.parse_args()

    records = load_records(Path(args.src))
    before = Counter(r["expected"]["alert_type"] for r in records)
    if args.balanced:
        records = balance(records)
    after = Counter(r["expected"]["alert_type"] for r in records)

    with open(args.dst, "w", encoding="utf-8") as out:
        for rec in records:
            out.write(json.dumps(to_sft(rec), ensure_ascii=False) + "\n")

    print(f"wrote {len(records)} samples -> {args.dst} (balanced={args.balanced})")
    print(f"  before: {dict(before)}")
    print(f"  after : {dict(after)}")


if __name__ == "__main__":
    main()
