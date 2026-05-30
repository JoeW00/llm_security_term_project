"""建構 live enricher 的工廠：用 httpx 接 abuse.ch（免金鑰）。

httpx 為延遲 import（僅在建構時），核心測試無需安裝 intel 群組。AbuseIPDB /
VirusTotal 為設環境金鑰才加入的可選來源（介面就緒，本工廠先接 abuse.ch）。
"""

from __future__ import annotations

from typing import Any

from soc_agent.enrichers.abuse_ch import AbuseChEnricher


class _HttpxClient:
    """以 httpx 實作 HttpClient.post_json（延遲 import）。"""

    def __init__(self, timeout: float = 10.0) -> None:
        import httpx

        self._client = httpx.Client(timeout=timeout)

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


def abuse_ch_enricher(
    *, timeout: float = 10.0, cache: dict[str, Any] | None = None
) -> AbuseChEnricher:
    """建一個查 abuse.ch ThreatFox 的 enricher（免金鑰）。缺 httpx 時丟清楚 RuntimeError。"""
    try:
        import httpx  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("未安裝 httpx；live 情資需要它（uv run --group intel ...）。") from exc
    return AbuseChEnricher(_HttpxClient(timeout=timeout), cache=cache)
