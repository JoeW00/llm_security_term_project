"""計畫 C / D 地端評估（全本地、無金鑰）：確定性預設 vs 地端 LLM（ollama qwen2.5:7b）。

- C 研判：verdict 準確率（true_positive 為正類）、反思收斂、劇本 rubric（LLM-as-judge）。
- D 安全：提示注入被操控率（確定性 vs LLM runner）、端到端延遲 / 迭代。

編排主腦跑**地端** ollama，符合自託管 SOC 威脅模型（告警不送出企業邊界）。
執行：`uv run --group eval python scripts/eval/run_local_cd_eval.py`
產出：`results/W16-C-reasoning-eval.{md,json}`、`results/W16-D-injection-runtime.{md,json}`
"""
# ruff: noqa: E501  研究腳本：標註樣本字串與結果表格刻意保留長行以利閱讀。

from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import mean

from eval.injection_eval import default_corpus, run_injection_suite
from eval.reasoning_eval import convergence_stats, judge_playbook, verdict_metrics
from soc_agent.graph import build_graph
from soc_agent.reasoners.factory import llm_reasoners, ollama_llm_client
from soc_agent.state import MAX_CRITIQUE_ITERATIONS

ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen2.5:7b"


def _alert(category: str, message: str) -> dict:
    return {
        "source": "wazuh",
        "timestamp": "t",
        "category": category,
        "severity": "high",
        "message": message,
        "indicators": [],
        "raw": {},
    }


# 標註樣本：3 真攻擊（true_positive）+ 3 良性誤報（false_positive）。全 high → 走完整研判路徑。
SAMPLES: list[tuple[dict, str]] = [
    (_alert("authentication", "84 failed SSH login attempts then a successful login from 185.220.101.5"), "true_positive"),
    (_alert("malware", "ransomware signature matched, files being encrypted on web-prod-01"), "true_positive"),
    (_alert("network", "host beaconing every 60s to known c2 domain evil.example.com"), "true_positive"),
    (_alert("vulnerability", "scheduled authenticated nessus vulnerability scan from approved scanner 10.0.0.9"), "false_positive"),
    (_alert("authentication", "user alice reset her password via the IT helpdesk self-service portal"), "false_positive"),
    (_alert("process", "nightly backup job triggered an EDR heuristic for bulk file reads, later whitelisted"), "false_positive"),
]


def _run(graph, alert: dict) -> dict:
    return graph.invoke({"alert": alert, "critique_iterations": 0})


def main() -> None:
    det_graph = build_graph()
    llm_client = ollama_llm_client(MODEL)
    llm_graph = build_graph(**llm_reasoners(llm_client))

    det_pairs, llm_pairs = [], []
    det_iters, llm_iters = [], []
    det_lat, llm_lat = [], []
    sample_playbook = None

    print(f"=== C 研判：{len(SAMPLES)} 筆樣本，確定性 vs 地端 {MODEL} ===")
    for i, (alert, expected) in enumerate(SAMPLES, 1):
        t0 = time.perf_counter()
        d = _run(det_graph, alert)
        det_lat.append(time.perf_counter() - t0)
        det_pairs.append((expected, d.get("verdict")))
        det_iters.append(d.get("critique_iterations", 0))

        t0 = time.perf_counter()
        m = _run(llm_graph, alert)
        llm_lat.append(time.perf_counter() - t0)
        llm_pairs.append((expected, m.get("verdict")))
        llm_iters.append(m.get("critique_iterations", 0))
        if sample_playbook is None and m.get("playbook"):
            sample_playbook = m["playbook"]

        print(f"  [{i}/{len(SAMPLES)}] exp={expected:14} det={d.get('verdict')} llm={m.get('verdict')}")

    det_v = verdict_metrics(det_pairs)
    llm_v = verdict_metrics(llm_pairs)
    det_c = convergence_stats(det_iters, MAX_CRITIQUE_ITERATIONS)
    llm_c = convergence_stats(llm_iters, MAX_CRITIQUE_ITERATIONS)

    # LLM-as-judge：用同一地端模型對一份 LLM 生成劇本評 rubric。
    rubric = None
    if sample_playbook is not None:
        try:
            rubric = judge_playbook(llm_client, sample_playbook).model_dump()
        except Exception as exc:  # noqa: BLE001
            rubric = {"error": type(exc).__name__}
    print(f"rubric (LLM-as-judge): {rubric}")

    # D 注入：確定性 vs 地端 LLM runner。
    print("=== D 安全：提示注入套件 ===")
    corpus = default_corpus()
    det_inj = run_injection_suite(lambda a: _run(det_graph, a), corpus)
    llm_inj = run_injection_suite(lambda a: _run(llm_graph, a), corpus)
    print(f"  deterministic manipulation_rate={det_inj.manipulation_rate:.3f}")
    print(f"  local-LLM     manipulation_rate={llm_inj.manipulation_rate:.3f}")

    # 結果落地
    c_payload = {
        "model": MODEL,
        "n_samples": len(SAMPLES),
        "verdict": {"deterministic": det_v, "local_llm": llm_v},
        "convergence": {"deterministic": det_c, "local_llm": llm_c, "cap": MAX_CRITIQUE_ITERATIONS},
        "playbook_rubric_local_llm_judge": rubric,
        "latency_seconds_mean": {"deterministic": mean(det_lat), "local_llm": mean(llm_lat)},
        "verdict_pairs": {"deterministic": det_pairs, "local_llm": llm_pairs},
    }
    d_payload = {
        "model": MODEL,
        "injection": {
            "deterministic": {"total": det_inj.total, "manipulated": det_inj.manipulated, "manipulation_rate": det_inj.manipulation_rate},
            "local_llm": {"total": llm_inj.total, "manipulated": llm_inj.manipulated, "manipulation_rate": llm_inj.manipulation_rate, "manipulated_names": llm_inj.manipulated_names},
        },
        "runtime_seconds_mean": {"deterministic": mean(det_lat), "local_llm": mean(llm_lat)},
        "iterations_mean": {"deterministic": mean(det_iters), "local_llm": mean(llm_iters)},
    }
    (ROOT / "results" / "W16-C-reasoning-eval.json").write_text(
        json.dumps(c_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "results" / "W16-D-injection-runtime.json").write_text(
        json.dumps(d_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _write_c_md(c_payload)
    _write_d_md(d_payload)
    print("written: results/W16-C-reasoning-eval.{md,json}, results/W16-D-injection-runtime.{md,json}")


def _write_c_md(p: dict) -> None:
    dv, lv = p["verdict"]["deterministic"], p["verdict"]["local_llm"]
    lines = [
        "# W16-C 研判子系統地端評估：確定性 vs 地端 LLM",
        "",
        f"> 來源：`scripts/eval/run_local_cd_eval.py`（全本地、無金鑰，編排主腦跑 ollama `{p['model']}`）。",
        f"> {p['n_samples']} 筆標註告警（3 真攻擊 / 3 良性誤報）。產生時間：2026-05-30。",
        "",
        "## verdict 準確率（true_positive 為正類）",
        "",
        "| runner | accuracy | precision | recall |",
        "|---|---|---|---|",
        f"| 確定性預設（rule-based） | {dv['accuracy']:.3f} | {dv['precision']:.3f} | {dv['recall']:.3f} |",
        f"| 地端 LLM（{p['model']}） | **{lv['accuracy']:.3f}** | **{lv['precision']:.3f}** | **{lv['recall']:.3f}** |",
        "",
        "> 確定性研判僅依 severity（high → 一律 true_positive），故對良性高嚴重度告警全判錯；",
        "> 地端 LLM 讀告警內容後能區分真攻擊與良性誤報。",
        "",
        "## 反思迴圈收斂",
        "",
        f"- 確定性：平均迭代 {p['convergence']['deterministic']['mean_iterations']:.2f}，"
        f"{p['convergence']['deterministic']['pct_converged']:.0%} 在 cap={p['convergence']['cap']} 內收斂。",
        f"- 地端 LLM：平均迭代 {p['convergence']['local_llm']['mean_iterations']:.2f}，"
        f"{p['convergence']['local_llm']['pct_converged']:.0%} 在 cap 內收斂。",
        "",
        "## 劇本 rubric（地端 LLM-as-judge，0–5）",
        "",
        f"`{p['playbook_rubric_local_llm_judge']}`",
        "",
        f"## 平均延遲：確定性 {p['latency_seconds_mean']['deterministic']:.3f}s / "
        f"地端 LLM {p['latency_seconds_mean']['local_llm']:.2f}s（每筆完整路徑）",
    ]
    (ROOT / "results" / "W16-C-reasoning-eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_d_md(p: dict) -> None:
    di, li = p["injection"]["deterministic"], p["injection"]["local_llm"]
    lines = [
        "# W16-D 安全子系統地端評估：提示注入韌性 + 端到端指標",
        "",
        f"> 來源：`scripts/eval/run_local_cd_eval.py`（全本地、無金鑰，地端 ollama `{p['model']}`）。",
        "> 產生時間：2026-05-30。",
        "",
        "## 提示注入被操控率（高風險告警注入「翻成 false_positive / 核准」）",
        "",
        "| runner | total | 被操控 | manipulation_rate |",
        "|---|---|---|---|",
        f"| 確定性預設 | {di['total']} | {di['manipulated']} | **{di['manipulation_rate']:.3f}** |",
        f"| 地端 LLM（{p['model']}） | {li['total']} | {li['manipulated']} | **{li['manipulation_rate']:.3f}** |",
        "",
        "> 確定性研判不讀 message 內容（依 severity），對注入**天然免疫**；地端 LLM 路徑讀內容，"
        "> 殘餘被操控率量化了 LLM 研判的注入風險（縱深防禦的必要性）。",
        "",
        "## 端到端指標（平均）",
        "",
        f"- 延遲：確定性 {p['runtime_seconds_mean']['deterministic']:.3f}s / "
        f"地端 LLM {p['runtime_seconds_mean']['local_llm']:.2f}s。",
        f"- 反思迭代：確定性 {p['iterations_mean']['deterministic']:.2f} / "
        f"地端 LLM {p['iterations_mean']['local_llm']:.2f}。",
    ]
    (ROOT / "results" / "W16-D-injection-runtime.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
