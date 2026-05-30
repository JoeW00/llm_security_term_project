"""情資增強評估：對一組 IOC 跑任一 Enricher，彙總命中與來源分布。

真實 abuse.ch 查詢（結果落地快取）為手動腳本；本模組的彙總純 Python、可離線測試。
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from soc_agent.enrichment import Enricher


def enrich_summary(enricher: Enricher, iocs: list[str]) -> dict[str, Any]:
    """彙總：總數、判惡意數、各來源計數。"""
    results = enricher.enrich(iocs)
    by_source: Counter[str] = Counter(r.source for r in results.values())
    malicious = sum(1 for r in results.values() if r.malicious)
    return {"total": len(results), "malicious": malicious, "by_source": dict(by_source)}
