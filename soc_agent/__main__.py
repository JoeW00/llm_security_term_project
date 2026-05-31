"""CLI 入口：uv run python -m soc_agent run <alert.json>。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING, Any

from soc_agent.graph import build_graph

if TYPE_CHECKING:
    from soc_agent.enrichment import Enricher


def _load_dotenv() -> None:
    """若安裝了 python-dotenv（intel 群組），載入專案 .env 的環境變數。

    缺套件則靜默跳過（離線/核心路徑不依賴它）；`override=False` 不覆蓋既有環境變數，
    故 `export` 或 `uv run --env-file` 仍優先。
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)


def run(
    alert_path: str,
    *,
    use_llm: bool = False,
    model: str = "claude-sonnet-4-6",
    live_intel: bool = False,
    enricher: Enricher | None = None,
) -> dict[str, Any]:
    """讀取單筆告警 JSON，跑完整圖，回傳 final_report。

    use_llm=True 時注入 Anthropic-backed 推理器（需 ANTHROPIC_API_KEY + `--group llm`）。
    live_intel=True 時 enrich 改用 live abuse.ch ThreatFox（需 `--group intel`；金鑰讀自
    ABUSE_CH_AUTH_KEY，缺金鑰查詢得 401 並安全中性降級）。
    enricher 不為 None 時直接注入，優先於 live_intel（供測試與程式化使用）。
    """
    with open(alert_path, encoding="utf-8") as f:
        alert = json.load(f)

    graph_kwargs: dict[str, Any] = {}
    if use_llm:
        from soc_agent.reasoners.factory import anthropic_llm_client, llm_reasoners

        graph_kwargs.update(llm_reasoners(anthropic_llm_client(model)))
    if enricher is not None:
        graph_kwargs["enricher"] = enricher
    elif live_intel:
        from soc_agent.enrichers.factory import abuse_ch_enricher

        graph_kwargs["enricher"] = abuse_ch_enricher()

    graph = build_graph(**graph_kwargs)
    result = graph.invoke({"alert": alert, "critique_iterations": 0})
    return result["final_report"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soc_agent")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="Run the agent on a single alert JSON file")
    run_p.add_argument("alert", help="Path to an alert JSON file")
    run_p.add_argument("--llm", action="store_true", help="Use the Anthropic LLM reasoners")
    run_p.add_argument(
        "--model", default="claude-sonnet-4-6", help="Anthropic model id (with --llm)"
    )
    run_p.add_argument(
        "--live-intel",
        action="store_true",
        help="enrich 改用 live abuse.ch ThreatFox（需 --group intel + ABUSE_CH_AUTH_KEY）",
    )
    args = parser.parse_args(argv)

    if args.command == "run":
        _load_dotenv()
        if args.live_intel:
            print(
                "live-intel：enrich 查 abuse.ch ThreatFox"
                "（金鑰讀自 ABUSE_CH_AUTH_KEY；缺金鑰將 401 並中性降級）",
                file=sys.stderr,
            )
        report = run(args.alert, use_llm=args.llm, model=args.model, live_intel=args.live_intel)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
