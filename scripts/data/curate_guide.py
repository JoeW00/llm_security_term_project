"""把 GUIDE 原始資料對映成凍結的 JSONL 留出集格式並切分 train/holdout。

GUIDE 的監督標籤是 **IncidentGrade**（TruePositive / BenignPositive / FalsePositive），
也就是 Tier-1 分流真正要做的「真陽 / 良性 / 誤報」判定。故：
  - expected.alert_type = IncidentGrade（正規化為 true_positive / benign_positive / false_positive）
  - alert.category      = GUIDE Category（**輸入特徵，不是答案**）

⚠️ 為何不用 Category 當答案：若 expected.alert_type 直接抄 alert.category，
RuleBasedClassifier（回傳 alert.category）就能不勞而獲拿滿分，整張消融表變成假數字。
改用 IncidentGrade 後任務才非退化——規則式與雲端零樣本都得真的研判。

嚴重度：GUIDE 沒有乾淨的嚴重度真值。若原始資料無嚴重度欄，severity 只當輸入欄，
**不寫進 expected**；stats.json 的 `severity_is_ground_truth` 只有在「每一筆留存記錄
都有」嚴重度真值時才為 true（與 run_ablation 的 severity 評估條件一致）。

只讀 *train* CSV（不讀 GUIDE_test.csv，避免測試集洩漏進 train/holdout）。
抽樣在「轉換+過濾+去重之後」才做，故 --limit 得到的是合法標籤記錄的均勻隨機樣本。

輸出：data/triage/train.jsonl, holdout.jsonl, stats.json。離線前處理，絕不進 pytest。

用法：
    uv run python scripts/data/curate_guide.py            # 用全部 *train* 資料（GUIDE 很大，慎用）
    uv run python scripts/data/curate_guide.py --limit N  # 均勻隨機抽 N 筆合法記錄（蓄水池抽樣）
    uv run python scripts/data/curate_guide.py --input data/triage/raw/GUIDE_train.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

RAW = Path("data/triage/raw")
OUT = Path("data/triage")
DEFAULT_GLOB = "*train*.csv"  # 刻意排除 GUIDE_test.csv
SEVERITY = {"low", "medium", "high", "critical"}

# 監督標籤：GUIDE 的 IncidentGrade（TP/BP/FP）。
GRADE_KEYS = ("IncidentGrade", "incidentgrade", "Grade")
GRADE_MAP = {
    "truepositive": "true_positive",
    "benignpositive": "benign_positive",
    "falsepositive": "false_positive",
    "tp": "true_positive",
    "bp": "benign_positive",
    "fp": "false_positive",
}
# 輸入特徵（非答案）。欄名候選依 GUIDE 實際 header 調整；第一個命中者勝出。
CATEGORY_KEYS = ("Category", "category")
MESSAGE_KEYS = ("AlertTitle", "Title", "title")
SEVERITY_KEYS = ("Severity", "AlertSeverity", "IncidentSeverity", "severity")
INDICATOR_KEYS = ("IpAddress", "Url", "Sha256", "DeviceName", "AccountName")

# GUIDE CSV 巨大，放寬 csv 欄位大小上限。
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def _first(row: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = row.get(k)
        if v not in (None, "", "nan", "NaN"):
            return str(v).strip()
    return ""


def normalize_severity(v: str) -> str:
    v = (v or "").strip().lower()
    return v if v in SEVERITY else "medium"


def normalize_grade(v: str) -> str:
    return GRADE_MAP.get((v or "").strip().lower().replace(" ", ""), "")


def to_record(row: dict) -> dict | None:
    """GUIDE 一列 → {'alert': {...}, 'expected': {...}}；無標籤或無訊息則回 None。"""
    grade = normalize_grade(_first(row, GRADE_KEYS))
    message = _first(row, MESSAGE_KEYS)
    if not grade or not message:  # 沒有監督標籤或訊息 → 丟棄
        return None
    severity_raw = _first(row, SEVERITY_KEYS)
    indicators = [v for k in INDICATOR_KEYS if (v := _first(row, (k,)))]
    alert = {
        "source": "guide",
        "timestamp": _first(row, ("Timestamp", "timestamp")) or "t",
        "category": _first(row, CATEGORY_KEYS).lower(),
        "severity": normalize_severity(severity_raw),
        "message": message,
        "indicators": indicators,
        "raw": {},
    }
    expected = {"alert_type": grade}
    if severity_raw:  # 只有 GUIDE 真有嚴重度欄時才當評估目標
        expected["severity"] = normalize_severity(severity_raw)
    return {"alert": alert, "expected": expected}


def curate(inputs: list[Path], limit: int | None) -> tuple[list[dict], int, int]:
    """轉換→過濾→去重→（可選）均勻隨機抽樣。回傳 (記錄, 掃描列數, 合法去重後總數)。"""
    rng = random.Random(42)
    reservoir: list[dict] = []
    scanned = 0
    valid = 0
    seen_keys: set[tuple[str, str]] = set()
    for src in inputs:
        with open(src, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                scanned += 1
                rec = to_record(row)
                if rec is None:
                    continue
                key = (rec["expected"]["alert_type"], rec["alert"]["message"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                valid += 1
                if limit is None or len(reservoir) < limit:
                    reservoir.append(rec)
                else:
                    j = rng.randint(0, valid - 1)  # 對「合法記錄」做蓄水池抽樣
                    if j < limit:
                        reservoir[j] = rec
    return reservoir, scanned, valid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="均勻隨機抽樣 N 筆合法記錄")
    ap.add_argument("--input", default=None, help="指定單一 CSV；預設讀 raw 下 *train*.csv")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if args.input:
        inputs = [Path(args.input)]
    else:
        inputs = sorted(RAW.glob(DEFAULT_GLOB))
    if not inputs:
        raise SystemExit(
            f"在 {RAW}/ 找不到 {DEFAULT_GLOB}（避免誤用 GUIDE_test.csv）。"
            " 請放入 GUIDE_train.csv 或用 --input 指定。"
        )

    records, scanned, valid = curate(inputs, args.limit)
    random.Random(42).shuffle(records)
    split = int(len(records) * 0.8)
    train, holdout = records[:split], records[split:]

    for name, recs in (("train", train), ("holdout", holdout)):
        with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    sev_count = sum(1 for r in records if "severity" in r["expected"])
    severity_is_truth = bool(records) and sev_count == len(records)
    stats = {
        "input_files": [p.name for p in inputs],
        "scanned_rows": scanned,
        "valid_unique": valid,
        "kept": len(records),
        "train": len(train),
        "holdout": len(holdout),
        "alert_type_dist": dict(Counter(r["expected"]["alert_type"] for r in records)),
        "severity_dist": dict(Counter(r["alert"]["severity"] for r in records)),
        "severity_expected_count": sev_count,
        "severity_is_ground_truth": severity_is_truth,
        "note": (
            "severity 來自 GUIDE 欄位且每筆皆有，可作為評估目標"
            if severity_is_truth
            else "severity 非每筆都有真值：run_ablation 會略過 severity；報告 §6.3 請註明限制"
        ),
    }
    (OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
