"""ATT&CK 對應評估：top-k 是否涵蓋預期技術（coverage），並列消融 Keyword vs Retrieval。

對任一符合 AttackMapper 介面的物件計分；指標純 Python、可離線測試。真實大規模
評估（用 data/enterprise-attack.json 建 RetrievalAttackMapper）為手動腳本，不進 pytest。
"""

from __future__ import annotations

from typing import Any

from soc_agent.attack import AttackMapper


def coverage(mapper: AttackMapper, records: list[dict[str, Any]]) -> float:
    """命中率：mapper.map(query) 是否包含 expected 技術，取平均。"""
    if not records:
        return 0.0
    hits = sum(1 for r in records if r["expected"] in mapper.map(r["query"]))
    return hits / len(records)


def mapping_ablation(
    mappers: dict[str, AttackMapper], records: list[dict[str, Any]]
) -> dict[str, float]:
    """對每個具名 mapper 算 coverage，回傳並列結果。"""
    return {name: coverage(m, records) for name, m in mappers.items()}
