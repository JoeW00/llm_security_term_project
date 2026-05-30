"""AbuseChEnricher：查 abuse.ch（ThreatFox）威脅情資。

以可注入的 HTTP client 建構（測試 mock、正式注入 httpx）。資安：
- IOC 外送前過濾私有/保留/CGNAT 等不可路由位址（避免內網位址外洩與 SSRF）。
- 外部回應一律以 EnrichmentResult 驗證；只保留白名單欄位並截斷長度，縮小注入面。
- 任何失敗（網路/解析/驗證）或不可外送 IOC，退回「中性 unavailable」結果（不謊稱
  惡意），絕不崩潰或污染狀態。可注入 fallback Enricher 串接其他來源。
查詢結果可由呼叫端提供的 cache（dict）落地以利重現。
"""

from __future__ import annotations

import ipaddress
from typing import Any, Protocol

from soc_agent.enrichment import Enricher, EnrichmentResult, classify_ioc

_THREATFOX_URL = "https://threatfox-api.abuse.ch/api/v1/"

# RFC 6598 共享位址空間（CGNAT）：Python 的 is_private 不涵蓋，明確阻擋外送。
_CGNAT = ipaddress.ip_network("100.64.0.0/10")

# 只從外部回應保留這些欄位進 raw，避免把不受控的整包 blob 帶進下游 LLM prompt。
_RAW_FIELDS = ("malware_printable", "threat_type", "confidence_level", "first_seen")
_MAX_STR = 256  # 單一字串值截斷長度
_MAX_TAGS = 20  # tags 最多保留筆數
_MAX_TAG_LEN = 64  # 單一 tag 截斷長度


class HttpClient(Protocol):
    """最小 HTTP 介面：POST json，回傳已解析的 dict。"""

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]: ...


def _is_sendable(ioc: str) -> bool:
    """非 IP 的 IOC 一律可送；IP 則排除私有/保留/loopback/CGNAT 等不可外送位址。"""
    try:
        ip = ipaddress.ip_address(ioc)
    except ValueError:
        return True
    if ip.version == 4 and ip in _CGNAT:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _clip(value: Any) -> Any:
    """字串值截斷以限制 raw 大小；非字串原樣保留。"""
    return value[:_MAX_STR] if isinstance(value, str) else value


class AbuseChEnricher:
    """查 abuse.ch ThreatFox；輸出經驗證，失敗或不可外送 IOC 退回中性結果。"""

    def __init__(
        self,
        client: HttpClient,
        *,
        fallback: Enricher | None = None,
        cache: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._fallback = fallback
        self._cache = cache if cache is not None else {}

    def enrich(self, iocs: list[str]) -> dict[str, EnrichmentResult]:
        out: dict[str, EnrichmentResult] = {}
        for ioc in iocs:
            if not _is_sendable(ioc):
                out[ioc] = self._degraded(ioc, "not_sendable")
                continue
            try:
                if ioc in self._cache:
                    resp = self._cache[ioc]
                else:
                    resp = self._client.post_json(
                        _THREATFOX_URL, {"query": "search_ioc", "search_term": ioc}
                    )
                    self._cache[ioc] = resp
                out[ioc] = self._parse(ioc, resp)
            except Exception:
                # 任何失敗（網路/解析/驗證）→ 中性退回，絕不污染狀態。
                out[ioc] = self._degraded(ioc, "lookup_failed")
        return out

    def _degraded(self, ioc: str, reason: str) -> EnrichmentResult:
        """不可外送或查詢失敗時的中性結果；不謊稱惡意。可委派給注入的 fallback。"""
        if self._fallback is not None:
            return self._fallback.enrich([ioc])[ioc]
        return EnrichmentResult(
            ioc=ioc,
            ioc_type=classify_ioc(ioc),
            source="abuse.ch/unavailable",
            malicious=False,
            score=0.0,
            references=0,
            raw={"fallback": reason},
        )

    def _parse(self, ioc: str, resp: dict[str, Any]) -> EnrichmentResult:
        data = resp.get("data") or []
        entry = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
        if resp.get("query_status") == "ok" and entry:
            family = entry.get("malware_printable") or entry.get("threat_type")
            raw_tags = entry.get("tags") or []
            tags = [t for t in ([family] if family else []) + list(raw_tags) if isinstance(t, str)]
            tags = [t[:_MAX_TAG_LEN] for t in tags[:_MAX_TAGS]]
            raw = {k: _clip(entry[k]) for k in _RAW_FIELDS if k in entry}
            return EnrichmentResult(
                ioc=ioc,
                ioc_type=classify_ioc(ioc),
                source="abuse.ch/ThreatFox",
                malicious=True,
                score=1.0,
                references=1,
                tags=tags,
                raw=raw,
            )
        return EnrichmentResult(
            ioc=ioc,
            ioc_type=classify_ioc(ioc),
            source="abuse.ch/ThreatFox",
            malicious=False,
            score=0.0,
            references=0,
            raw={"query_status": resp.get("query_status")},
        )
