"""Stub 節點：確定性、無 LLM、無網路。計畫 A–D 各自替換對應節點。"""

from __future__ import annotations

from typing import Any

from soc_agent.state import Alert, IncidentState


def ingest(state: IncidentState) -> dict[str, Any]:
    """驗證並正規化原始告警，萃取初始 IOC 清單。"""
    alert = Alert.model_validate(state["alert"])
    return {"alert": alert.model_dump(), "iocs": list(alert.indicators)}


def triage(state: IncidentState) -> dict[str, Any]:
    """STUB：由正規化告警推導類型與嚴重度。計畫 A 換成微調本地分類器。"""
    alert = state["alert"]
    return {
        "alert_type": alert.get("category", "unknown"),
        "severity": alert.get("severity", "medium"),
    }


def enrich(state: IncidentState) -> dict[str, Any]:
    """STUB：假裝查詢每個 IOC 的威脅情資。計畫 B 換成真實工具呼叫。"""
    enrichment = {ioc: {"reputation": "unknown"} for ioc in state.get("iocs", [])}
    return {"enrichment": enrichment}


def investigate(state: IncidentState) -> dict[str, Any]:
    """STUB：判定真偽。計畫 C 換成 LLM 研判。"""
    severity = state.get("severity", "medium")
    verdict = "true_positive" if severity in ("high", "critical") else "unknown"
    return {"verdict": verdict, "confidence": 0.5}


def attack_mapping(state: IncidentState) -> dict[str, Any]:
    """STUB：對應 MITRE ATT&CK 技術。計畫 B 換成檢索式對應。"""
    return {"attack_techniques": ["T1110"]}  # T1110 = Brute Force（佔位）


def playbook(state: IncidentState) -> dict[str, Any]:
    """STUB：產生三階段處置劇本。計畫 C 換成 LLM 生成。"""
    return {
        "playbook": {
            "containment": ["isolate affected host"],
            "eradication": ["reset compromised credentials"],
            "recovery": ["restore service and monitor"],
        }
    }


def critique(state: IncidentState) -> dict[str, Any]:
    """STUB：反思劇本完整性。

    骨架階段刻意確定性：第一輪標記為不完整（強制回頭重生一次），之後標記
    完整。計畫 C 換成真實 LLM 批判。
    """
    iterations = state.get("critique_iterations", 0) + 1
    complete = iterations >= 2
    return {
        "critique_iterations": iterations,
        "critique": {
            "complete": complete,
            "notes": "ok" if complete else "needs containment detail",
        },
    }


def human_approval(state: IncidentState) -> dict[str, Any]:
    """STUB：自動核准。計畫 D 換成 LangGraph interrupt 人工關卡。"""
    return {"approved": True}


def report(state: IncidentState) -> dict[str, Any]:
    """彙整最終結構化事件報告。"""
    return {
        "final_report": {
            "alert_type": state.get("alert_type"),
            "severity": state.get("severity"),
            "verdict": state.get("verdict"),
            "attack_techniques": state.get("attack_techniques", []),
            "playbook": state.get("playbook", {}),
            "approved": state.get("approved", False),
        }
    }
