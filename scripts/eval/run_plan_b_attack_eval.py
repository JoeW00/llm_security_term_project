"""計畫 B：ATT&CK 對應消融（KeywordAttackMapper vs RetrievalAttackMapper/BM25）。

純本地、無金鑰：對一組標註樣本（SOC 告警描述 → 預期 MITRE 技術），比較規則式
關鍵字對應與 BM25 檢索式對應的 top-1 / top-3 覆蓋率。RetrievalAttackMapper 以真實
`data/enterprise-attack.json`（697 技術，父技術歸併）建索引。

執行：`uv run python scripts/eval/run_plan_b_attack_eval.py`
產出：`results/W15-B-attack-mapping-ablation.{md,json}`
"""

from __future__ import annotations

import json
from pathlib import Path

from soc_agent.attack import KeywordAttackMapper
from soc_agent.attack_mappers.retrieval import RetrievalAttackMapper

ROOT = Path(__file__).resolve().parents[2]
STIX = ROOT / "data" / "enterprise-attack.json"

# 標註樣本：真實 SOC 告警語句 → 預期父技術 ID。涵蓋 12 種戰術／技術。
SAMPLES: list[dict[str, str]] = [
    {"query": "multiple failed SSH login attempts, brute force from single host", "expected": "T1110"},
    {"query": "powershell encoded command downloaded and executed a payload", "expected": "T1059"},
    {"query": "ransomware encrypted files across the host and dropped a ransom note", "expected": "T1486"},
    {"query": "scheduled task created to run a binary at logon for persistence", "expected": "T1053"},
    {"query": "credential dumping observed reading lsass process memory", "expected": "T1003"},
    {"query": "phishing email with malicious attachment opened by the user", "expected": "T1566"},
    {"query": "lateral movement using remote desktop protocol rdp to another server", "expected": "T1021"},
    {"query": "registry run key modified to autostart malware at boot", "expected": "T1547"},
    {"query": "valid account login from an unusual foreign geolocation", "expected": "T1078"},
    {"query": "code injected into explorer.exe via process injection", "expected": "T1055"},
    {"query": "windows defender antivirus was disabled to impair defenses", "expected": "T1562"},
    {"query": "data exfiltrated over dns tunneling to external server", "expected": "T1048"},
]


def _coverage(mapper, k: int) -> tuple[float, list[dict]]:
    """top-k 覆蓋率：mapper.map(query) 前 k 個是否含 expected。回傳 (覆蓋率, 逐筆明細)。"""
    detail = []
    hits = 0
    for s in SAMPLES:
        got = mapper.map(s["query"])[:k]
        hit = s["expected"] in got
        hits += hit
        detail.append({"expected": s["expected"], "got": got, "hit": hit, "query": s["query"]})
    return hits / len(SAMPLES), detail


def main() -> None:
    keyword = KeywordAttackMapper()
    retrieval = RetrievalAttackMapper.from_stix(STIX, top_k=3)
    n_tech = len(retrieval._docs)

    kw1, kw1d = _coverage(keyword, 1)
    kw3, _ = _coverage(keyword, 3)
    rt1, rt1d = _coverage(retrieval, 1)
    rt3, rt3d = _coverage(retrieval, 3)

    payload = {
        "n_samples": len(SAMPLES),
        "n_techniques_indexed": n_tech,
        "arms": {
            "keyword": {"top1_coverage": kw1, "top3_coverage": kw3},
            "retrieval_bm25": {"top1_coverage": rt1, "top3_coverage": rt3},
        },
        "retrieval_detail": rt3d,
        "keyword_detail": kw1d,
    }
    (ROOT / "results" / "W15-B-attack-mapping-ablation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# W15-B ATT&CK 對應消融：規則式關鍵字 vs BM25 檢索",
        "",
        "> 來源：`scripts/eval/run_plan_b_attack_eval.py`（純本地、無金鑰）。",
        f"> 檢索語料：`data/enterprise-attack.json`（**{n_tech} 技術**，父技術歸併）。",
        f"> 標註樣本 {len(SAMPLES)} 筆（SOC 告警語句 → 預期 MITRE 父技術）。產生時間：2026-05-30。",
        "",
        "## 覆蓋率（預期技術是否落在 top-k）",
        "",
        "| 對應器 | top-1 | top-3 |",
        "|---|---|---|",
        f"| KeywordAttackMapper（4 規則） | {kw1:.3f} | {kw3:.3f} |",
        f"| RetrievalAttackMapper（BM25） | **{rt1:.3f}** | **{rt3:.3f}** |",
        "",
        "> 關鍵字僅有 4 條規則（T1110/T1078/T1059/T1204），多數技術無法觸及，且 ransomware",
        "> 被誤對應到 T1204（User Execution）而非正解 T1486。BM25 對 697 技術全語料檢索，",
        "> 大幅提升覆蓋率與正確性。",
        "",
        "## BM25 逐筆（top-3）",
        "",
        "| 預期 | BM25 top-3 | 命中 | 告警語句 |",
        "|---|---|---|---|",
    ]
    for d in rt3d:
        mark = "✅" if d["hit"] else "❌"
        lines.append(f"| {d['expected']} | {', '.join(d['got'])} | {mark} | {d['query']} |")
    (ROOT / "results" / "W15-B-attack-mapping-ablation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(f"techniques indexed: {n_tech}")
    print(f"keyword   top-1/top-3: {kw1:.3f} / {kw3:.3f}")
    print(f"retrieval top-1/top-3: {rt1:.3f} / {rt3:.3f}")
    print("written: results/W15-B-attack-mapping-ablation.{md,json}")


if __name__ == "__main__":
    main()
