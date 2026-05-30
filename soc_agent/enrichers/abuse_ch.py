"""AbuseChEnricher：查 abuse.ch（ThreatFox）威脅情資。

以可注入的 HTTP client 建構（測試 mock、正式注入 httpx）。資安：IOC 外送前過濾
私有/保留 IP（避免內網位址外洩與 SSRF）；外部回應一律以 EnrichmentResult 驗證；
任何失敗（網路/解析/驗證）退回 StaticEnricher 的保守結果，絕不崩潰或污染狀態。
查詢結果可由呼叫端提供的 cache（dict）落地以利重現。
"""

from __future__ import annotations

import ipaddress
from typing import Any, Protocol

from soc_agent.enrichment import (
    Enricher,
    EnrichmentResult,
    StaticEnricher,
    classify_ioc,
)

_THREATFOX_URL = "https://threatfox-api.abuse.ch/api/v1/"


class HttpClient(Protocol):
    """最小 HTTP 介面：POST json，回傳已解析的 dict。"""

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]: ...


def _is_sendable(ioc: str) -> bool:
    """非 IP 的 IOC 一律可送；IP 則排除私有/保留/loopback 等不可外送位址。"""
    try:
        ip = ipaddress.ip_address(ioc)
    except ValueError:
        return True
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


class AbuseChEnricher:
    """查 abuse.ch ThreatFox；輸出經驗證，失敗或不可外送 IOC 退回確定性保守結果。"""

    def __init__(
        self,
        client: HttpClient,
        *,
        fallback: Enricher | None = None,
        cache: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._fallback = fallback or StaticEnricher()
        self._cache = cache if cache is not None else {}

    def enrich(self, iocs: list[str]) -> dict[str, EnrichmentResult]:
        out: dict[str, EnrichmentResult] = {}
        for ioc in iocs:
            if not _is_sendable(ioc):
                out[ioc] = self._fallback.enrich([ioc])[ioc]
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
                # 任何失敗（網路/解析/驗證）→ 安全退回，絕不污染狀態。
                out[ioc] = self._fallback.enrich([ioc])[ioc]
        return out

    def _parse(self, ioc: str, resp: dict[str, Any]) -> EnrichmentResult:
        data = resp.get("data") or []
        entry = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
        if resp.get("query_status") == "ok" and entry:
            family = entry.get("malware_printable") or entry.get("threat_type")
            raw_tags = entry.get("tags") or []
            tags = [t for t in ([family] if family else []) + list(raw_tags) if isinstance(t, str)]
            return EnrichmentResult(
                ioc=ioc,
                ioc_type=classify_ioc(ioc),
                source="abuse.ch/ThreatFox",
                malicious=True,
                score=1.0,
                references=1,
                tags=tags,
                raw=entry,
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
