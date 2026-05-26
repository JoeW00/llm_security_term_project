"""端到端執行指標：延遲與反思迭代次數（P4 端到端評估）。"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


def end_to_end_metrics(
    runner: Callable[[dict[str, Any]], dict[str, Any]],
    alert: dict[str, Any],
) -> dict[str, Any]:
    """跑 runner 計時，回傳 {latency_seconds, critique_iterations}。

    `runner` 應回傳完整結果 state（含 `critique_iterations`），例如
    `lambda a: build_graph(...).invoke({"alert": a, "critique_iterations": 0})`。
    """
    start = time.perf_counter()
    result = runner(alert)
    latency = time.perf_counter() - start
    return {
        "latency_seconds": latency,
        "critique_iterations": result.get("critique_iterations", 0),
    }
