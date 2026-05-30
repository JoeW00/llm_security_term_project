"""情資增強邊界：可注入的威脅情資契約與離線預設實作。

`enrich` 節點透過 `Enricher` 介面取得每個 IOC 的 `EnrichmentResult`。預設為確定性
離線的 `StaticEnricher`；正式環境注入查 abuse.ch 等真實情資的後端（見
soc_agent/enrichers/）。外部回應在進入 IncidentState 前一律以 EnrichmentResult 驗證。
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

IocType = Literal["ip", "domain", "hash", "url", "unknown"]

_HASH_RE = re.compile(r"[a-fA-F0-9]{32,64}")


def classify_ioc(ioc: str) -> IocType:
    """確定性判斷 IOC 型別（離線）。"""
    try:
        ipaddress.ip_address(ioc)
        return "ip"
    except ValueError:
        pass
    if ioc.startswith(("http://", "https://")):
        return "url"
    if _HASH_RE.fullmatch(ioc):
        return "hash"
    if "." in ioc:
        return "domain"
    return "unknown"


class EnrichmentResult(BaseModel):
    """單一 IOC 的情資結果；進入 IncidentState 前的唯一（已驗證）型別。"""

    ioc: str
    ioc_type: IocType = "unknown"
    source: str
    malicious: bool = False
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    references: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Enricher(Protocol):
    """結構型介面：吃 IOC 清單，回傳 {ioc: EnrichmentResult}。"""

    def enrich(self, iocs: list[str]) -> dict[str, EnrichmentResult]: ...


class StaticEnricher:
    """確定性、離線預設：沿用骨架 mock 行為，回傳已驗證的 EnrichmentResult。"""

    def enrich(self, iocs: list[str]) -> dict[str, EnrichmentResult]:
        out: dict[str, EnrichmentResult] = {}
        for ioc in iocs:
            kind = classify_ioc(ioc)
            if kind == "ip":
                out[ioc] = EnrichmentResult(
                    ioc=ioc,
                    ioc_type=kind,
                    source="AbuseIPDB",
                    malicious=True,
                    score=0.85,
                    references=12,
                    raw={"vendor": "AbuseIPDB", "score": 85, "reports": 12},
                )
            else:
                out[ioc] = EnrichmentResult(
                    ioc=ioc,
                    ioc_type=kind,
                    source="VirusTotal",
                    malicious=True,
                    score=0.5,
                    references=5,
                    raw={"vendor": "VirusTotal", "positives": 5},
                )
        return out
