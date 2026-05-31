"""CLI 的 --live-intel 開關與 .env 載入：全離線、確定性（不碰網路/httpx）。"""

from __future__ import annotations

from typing import Any

import soc_agent.__main__ as cli

_ALERT = "data/sample_alerts/ssh_bruteforce.json"


class _StubEnricher:
    """測試替身：滿足 Enricher 介面但不連網。"""

    def enrich(self, iocs: list[str]) -> list[Any]:
        return []


class _FakeGraph:
    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"final_report": {"ok": True}}


def _capture_build_graph(captured: dict[str, Any]):
    def fake_build_graph(**kwargs: Any) -> _FakeGraph:
        captured.update(kwargs)
        return _FakeGraph()

    return fake_build_graph


def test_run_injects_provided_enricher(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(cli, "build_graph", _capture_build_graph(captured))
    sentinel = _StubEnricher()
    out = cli.run(_ALERT, enricher=sentinel)
    assert captured["enricher"] is sentinel
    assert out == {"ok": True}


def test_live_intel_builds_abuse_ch_enricher(monkeypatch):
    captured: dict[str, Any] = {}
    sentinel = _StubEnricher()
    monkeypatch.setattr(cli, "build_graph", _capture_build_graph(captured))
    # patch lazy-import 目標，避免真的建 httpx client / 連網
    import soc_agent.enrichers.factory as factory

    monkeypatch.setattr(factory, "abuse_ch_enricher", lambda: sentinel)
    cli.run(_ALERT, live_intel=True)
    assert captured["enricher"] is sentinel


def test_explicit_enricher_overrides_live_intel(monkeypatch):
    # 顯式 enricher 優先於 live_intel，且不應觸發 abuse_ch_enricher（不需 httpx）
    captured: dict[str, Any] = {}
    monkeypatch.setattr(cli, "build_graph", _capture_build_graph(captured))
    import soc_agent.enrichers.factory as factory

    def _boom() -> Any:
        raise AssertionError("不應呼叫 abuse_ch_enricher")

    monkeypatch.setattr(factory, "abuse_ch_enricher", _boom)
    sentinel = _StubEnricher()
    cli.run(_ALERT, live_intel=True, enricher=sentinel)
    assert captured["enricher"] is sentinel


def test_no_intel_flags_means_no_enricher_kwarg(monkeypatch):
    # 不帶旗標時不注入 enricher（沿用節點預設）
    captured: dict[str, Any] = {}
    monkeypatch.setattr(cli, "build_graph", _capture_build_graph(captured))
    cli.run(_ALERT)
    assert "enricher" not in captured


def test_cli_parses_live_intel_flag(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_run(alert: str, **kwargs: Any) -> dict[str, Any]:
        captured["alert"] = alert
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(cli, "run", fake_run)
    rc = cli.main(["run", _ALERT, "--live-intel"])
    assert rc == 0
    assert captured["alert"] == _ALERT
    assert captured["live_intel"] is True


def test_cli_live_intel_defaults_false(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_run(alert: str, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(cli, "run", fake_run)
    cli.main(["run", _ALERT])
    assert captured["live_intel"] is False


def test_load_dotenv_is_graceful():
    # 不論 python-dotenv 是否安裝，呼叫都不應拋例外
    cli._load_dotenv()
