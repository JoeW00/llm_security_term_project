"""檢索式 ATT&CK 對應：對 MITRE STIX 語料建 BM25 索引，依告警查詢取 top-k 技術。

純離線、確定性、無外部依賴：自實作精簡 Okapi BM25（不依賴 numpy/rank-bm25）。
`load_attack_patterns` 從 enterprise-attack STIX bundle 抽出技術文件（子技術歸併
到父技術）；`RetrievalAttackMapper` 以文件清單建構，便於用小 fixture 離線測試
——45MB 實檔的載入不進 pytest。
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """小寫英數斷詞（確定性）。"""
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class TechniqueDoc:
    """單一技術的索引文件；technique_id 已歸併為父技術 ID。"""

    technique_id: str
    name: str
    text: str


def _parent_id(external_id: str) -> str:
    """T1055.011 → T1055（父技術歸併）。"""
    return external_id.split(".", 1)[0]


def load_attack_patterns(path: str | Path) -> list[TechniqueDoc]:
    """從 MITRE ATT&CK STIX bundle 抽出 attack-pattern 技術文件（跳過 revoked/deprecated）。"""
    with open(path, encoding="utf-8") as f:
        bundle = json.load(f)
    docs: list[TechniqueDoc] = []
    for obj in bundle.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        ext = next(
            (
                r
                for r in obj.get("external_references", [])
                if r.get("source_name") == "mitre-attack" and r.get("external_id")
            ),
            None,
        )
        if ext is None:
            continue
        name = obj.get("name", "")
        description = obj.get("description", "")
        docs.append(
            TechniqueDoc(
                technique_id=_parent_id(ext["external_id"]),
                name=name,
                text=f"{name} {description}",
            )
        )
    return docs


class _BM25:
    """精簡 Okapi BM25：以 token 化語料建索引，對 query 算每文件分數。"""

    def __init__(self, corpus: list[list[str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._n = len(corpus)
        self._doc_len = [len(d) for d in corpus]
        self._avgdl = (sum(self._doc_len) / self._n) if self._n else 0.0
        self._tf = [Counter(d) for d in corpus]
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        self._idf = {term: math.log(1 + (self._n - n + 0.5) / (n + 0.5)) for term, n in df.items()}

    def scores(self, query_tokens: list[str]) -> list[float]:
        terms = [t for t in query_tokens if t in self._idf]
        out = [0.0] * self._n
        for i in range(self._n):
            length = self._doc_len[i]
            if not length:
                continue
            norm = (
                self._k1 * (1 - self._b + self._b * length / self._avgdl)
                if self._avgdl
                else self._k1
            )
            tf = self._tf[i]
            score = 0.0
            for term in terms:
                f = tf.get(term, 0)
                if f:
                    score += self._idf[term] * (f * (self._k1 + 1)) / (f + norm)
            out[i] = score
        return out


class RetrievalAttackMapper:
    """BM25 檢索式 ATT&CK 對應：取 top-k 命中技術（父技術去重），確定性。"""

    def __init__(
        self,
        documents: list[TechniqueDoc],
        *,
        top_k: int = 3,
        min_score: float = 0.0,
    ) -> None:
        self._docs = list(documents)
        self._top_k = top_k
        self._min_score = min_score
        self._bm25 = _BM25([_tokenize(d.text) for d in self._docs])

    @classmethod
    def from_stix(cls, path: str | Path, **kwargs: Any) -> RetrievalAttackMapper:
        """從 STIX bundle 路徑建構（正式環境用 data/enterprise-attack.json）。"""
        return cls(load_attack_patterns(path), **kwargs)

    def map(self, query: str) -> list[str]:
        if not self._docs:
            return []
        scores = self._bm25.scores(_tokenize(query))
        # 確定性排序：分數高→低，同分以技術 ID、再文件文字 tie-break。
        order = sorted(
            range(len(self._docs)),
            key=lambda i: (-scores[i], self._docs[i].technique_id, self._docs[i].text),
        )
        result: list[str] = []
        for i in order:
            if scores[i] <= self._min_score:
                break
            tid = self._docs[i].technique_id
            if tid not in result:
                result.append(tid)
            if len(result) >= self._top_k:
                break
        return result
