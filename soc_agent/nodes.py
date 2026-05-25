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
    """STUB：假裝查詢每個 IOC 的威脅情資。計畫 B 換成真實工具呼叫。Stub for nodes.enrich: Extracts IOCs and calls threat intelligence tools."""
    print("--- NODE: ENRICH ---")
    
    # TODO (Week 15): Parse state["alert"] for real IPs/Domains 
    # and call AbuseIPDB / VirusTotal APIs.
    
    # Mocking the extraction and API response for the Week 14 prototype
    mocked_iocs = ["192.168.1.100", "malicious-domain.com"]
    mocked_enrichment_data = {
        "192.168.1.100": {"vendor": "AbuseIPDB", "score": 85, "reports": 12},
        "malicious-domain.com": {"vendor": "VirusTotal", "positives": 5}
    }
    
    print(f"[*] Extracted IOCs: {mocked_iocs}")
    print(f"[*] Retrieved Enrichment: {mocked_enrichment_data}")
    
    # Return ONLY the keys we are responsible for updating
    return {
        "iocs": mocked_iocs,
        "enrichment": mocked_enrichment_data
    }


def investigate(state: IncidentState) -> dict[str, Any]:
    """STUB：判定真偽。計畫 C 換成 LLM 研判。"""
    severity = state.get("severity", "medium")
    verdict = "true_positive" if severity in ("high", "critical") else "unknown"
    return {"verdict": verdict, "confidence": 0.5}


def attack_mapping(state: IncidentState) -> dict[str, Any]:
    """STUB：對應 MITRE ATT&CK 技術。計畫 B 換成檢索式對應。Stub for nodes.attack_mapping: Maps findings to MITRE ATT&CK."""
    print("--- NODE: ATT&CK MAPPING ---")
    
    # TODO (Week 15): Map the enrichment findings to local STIX/MITRE data.
    
    # Mocking the MITRE mapping based on our fake enrichment data
    mocked_techniques = [
        "T1078 - Valid Accounts", 
        "T1059 - Command and Scripting Interpreter"
    ]
    
    print(f"[*] Mapped Techniques: {mocked_techniques}")
    
    # Return ONLY the keys we are responsible for updating
    return {
        "attack_techniques": mocked_techniques
    }


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

#看你們需不需要這部分的給助教看 mockup，不需要的話就 comment 或刪掉謝謝
if __name__ == "__main__":
    # Initialize a fake state passed from the previous node (Triage) 
    print("MOCKUP TEST PREVIEW")

    test_state: IncidentState = {
        "alert": {"raw_message": "Suspicious login from 192.168.1.100 and connection to malicious-domain.com"},
        "alert_type": "Credential Access",
        "severity": "high",
        "iocs": [],
        "enrichment": {},
        "attack_techniques": []
    }
    
    # Run the enrich stub
    updated_state_1 = enrich(test_state)
    
    # Simulate LangGraph merging the state using dictionary updates
    test_state.update(updated_state_1)
    
    # Run the mapping stub
    updated_state_2 = attack_mapping(test_state)
    
    # Simulate LangGraph merging the state again
    test_state.update(updated_state_2)
    
    print("\n--- TEST COMPLETE ---")
    print("If you see this, your node skeletons are working perfectly with TypedDict.")