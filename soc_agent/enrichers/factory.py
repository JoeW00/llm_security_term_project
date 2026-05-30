"""建構 live enricher 的工廠：用 httpx 接 abuse.ch ThreatFox。

httpx 為延遲 import（僅在建構時），核心測試無需安裝 intel 群組。
abuse.ch 自 2024 起需**免費 Auth-Key**（於 https://auth.abuse.ch 註冊取得），
由環境變數 `ABUSE_CH_AUTH_KEY` 提供，經 `Auth-Key` 標頭送出；金鑰只存在於 client
標頭、不寫入 log/報告。缺金鑰仍可建構，但查詢會得 401 → enricher 中性退回。
AbuseIPDB / VirusTotal 為日後設金鑰才加入的可選來源（介面就緒）。
"""

from __future__ import annotations

import os
from typing import Any

from soc_agent.enrichers.abuse_ch import AbuseChEnricher


class _HttpxClient:
    """以 httpx 實作 HttpClient.post_json（延遲 import）。Auth-Key 走標頭，不入 log。"""

    def __init__(self, timeout: float = 10.0, auth_key: str | None = None) -> None:
        import httpx

        headers = {"Auth-Key": auth_key} if auth_key else {}
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


def abuse_ch_enricher(
    *,
    timeout: float = 10.0,
    cache: dict[str, Any] | None = None,
    auth_key: str | None = None,
) -> AbuseChEnricher:
    """建一個查 abuse.ch ThreatFox 的 enricher。

    auth_key 預設讀環境變數 `ABUSE_CH_AUTH_KEY`（abuse.ch 2024 起需免費金鑰）。
    缺 httpx 時丟清楚 RuntimeError；缺金鑰仍可建構（查詢將 401 並中性退回）。
    """
    try:
        import httpx  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("未安裝 httpx；live 情資需要它（uv run --group intel ...）。") from exc
    key = auth_key or os.environ.get("ABUSE_CH_AUTH_KEY")
    return AbuseChEnricher(_HttpxClient(timeout=timeout, auth_key=key), cache=cache)
