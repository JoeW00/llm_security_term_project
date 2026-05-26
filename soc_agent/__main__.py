"""CLI 入口：uv run python -m soc_agent run <alert.json>。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from soc_agent.graph import build_graph


def run(
    alert_path: str, *, use_llm: bool = False, model: str = "claude-sonnet-4-6"
) -> dict[str, Any]:
    """讀取單筆告警 JSON，跑完整圖，回傳 final_report。

    use_llm=True 時注入 Anthropic-backed 推理器（需 ANTHROPIC_API_KEY + `--group llm`）。
    """
    with open(alert_path, encoding="utf-8") as f:
        alert = json.load(f)
    if use_llm:
        from soc_agent.reasoners.factory import anthropic_llm_client, llm_reasoners

        graph = build_graph(**llm_reasoners(anthropic_llm_client(model)))
    else:
        graph = build_graph()
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
    args = parser.parse_args(argv)

    if args.command == "run":
        report = run(args.alert, use_llm=args.llm, model=args.model)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
