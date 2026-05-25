from soc_agent.graph import build_graph

HIGH = {
    "source": "wazuh", "timestamp": "t", "category": "authentication",
    "severity": "high", "message": "brute force", "indicators": ["203.0.113.45"], "raw": {},
}
LOW = {
    "source": "wazuh", "timestamp": "t", "category": "system",
    "severity": "low", "message": "heartbeat", "indicators": [], "raw": {},
}


def test_graph_compiles():
    assert build_graph() is not None


def test_full_path_produces_report_and_loops_once():
    graph = build_graph()
    result = graph.invoke({"alert": HIGH, "critique_iterations": 0})
    assert result["final_report"]["verdict"] == "true_positive"
    # critique 強制回頭重生剛好一次：0 -> 1(不完整) -> 2(完整)
    assert result["critique_iterations"] == 2
    assert result["enrichment"]  # 完整調查路徑有跑到 enrich


def test_low_severity_bypasses_investigation():
    graph = build_graph()
    result = graph.invoke({"alert": LOW, "critique_iterations": 0})
    assert result["final_report"]["approved"] is True
    assert "enrichment" not in result  # 旁路跳過了 enrich
