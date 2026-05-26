"""Stub 節點：確定性、無 LLM、無網路。計畫 A–D 各自替換對應節點。"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from soc_agent.classifier import Classifier, RuleBasedClassifier
from soc_agent.state import Alert, IncidentState

# triage 的預設分類器：確定性、離線。正式環境由 build_graph 注入 Ollama 後端。
_DEFAULT_CLASSIFIER = RuleBasedClassifier()

# 關鍵字 → MITRE ATT&CK 技術 ID 的最小對應表。計畫 B 會換成檢索式
# STIX/MITRE 對應；此處刻意保持確定性與離線。
_TECHNIQUE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("brute force", "failed login", "failed password", "authentication"), "T1110"),
    (("valid account", "successful login", "compromised credential"), "T1078"),
    (("powershell", "command", "script", "/bin/sh", "cmd.exe"), "T1059"),
    (("malware", "trojan", "virus", "ransomware"), "T1204"),
)
# 無任何規則命中時的保底技術（Valid Accounts）。
_DEFAULT_TECHNIQUE = "T1078"

# 離線 IOC 萃取：從告警訊息抽取 IP / domain / hash。順序決定去重時的優先呈現。
# domain 正則用「有界標籤」寫法（每段 ≤63 字、首尾為英數），避免巢狀量詞造成
# catastrophic backtracking（ReDoS）；message 是不可信輸入，務必保持線性。
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HASH_RE = re.compile(r"\b[a-fA-F0-9]{32,64}\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}\b")

# 防禦縱深：不可信 message 在做 regex 前先截斷，限制最壞情況工作量。
_MAX_MESSAGE_LEN = 16384


def _extract_iocs(message: str) -> list[str]:
    """從訊息抽取 IP / hash / domain。確定性、離線、依正則順序回傳。"""
    message = message[:_MAX_MESSAGE_LEN]
    found: list[str] = []
    for pattern in (_IPV4_RE, _HASH_RE, _DOMAIN_RE):
        found.extend(pattern.findall(message))
    return found


def _looks_like_ip(value: str) -> bool:
    """判斷字串是否為合法 IPv4/IPv6 位址。"""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def ingest(state: IncidentState) -> dict[str, Any]:
    """驗證並正規化原始告警，合併欄位 IOC 與訊息中萃取的 IOC（去重）。"""
    alert = Alert.model_validate(state["alert"])
    iocs = list(alert.indicators)
    for ioc in _extract_iocs(alert.message):
        if ioc not in iocs:
            iocs.append(ioc)
    return {"alert": alert.model_dump(), "iocs": iocs}


def triage(state: IncidentState, *, classifier: Classifier | None = None) -> dict[str, Any]:
    """由分類器推導告警類型與嚴重度。計畫 A：預設規則式，正式環境注入微調模型。"""
    classifier = classifier or _DEFAULT_CLASSIFIER
    result = classifier.classify(state["alert"])
    return {"alert_type": result.alert_type, "severity": result.severity}


def enrich(state: IncidentState) -> dict[str, Any]:
    """STUB：為每個 IOC 產生一筆威脅情資。計畫 B 換成真實工具呼叫。

    確定性、離線：依 IOC 是否為 IP 位址挑選對應的模擬供應商回應，並以
    `state["iocs"]` 為鍵建立 `enrichment`。計畫 B 會改成呼叫
    AbuseIPDB / VirusTotal 等服務。
    """
    print("--- NODE: ENRICH ---")
    iocs = state.get("iocs", [])

    enrichment: dict[str, Any] = {}
    for ioc in iocs:
        if _looks_like_ip(ioc):
            enrichment[ioc] = {"vendor": "AbuseIPDB", "score": 85, "reports": 12}
        else:
            enrichment[ioc] = {"vendor": "VirusTotal", "positives": 5}

    print(f"[*] Enriched IOCs: {list(enrichment)}")

    # 只回傳本節點負責更新的鍵（iocs 由 ingest 決定，這裡不覆寫）。
    return {"enrichment": enrichment}


def investigate(state: IncidentState) -> dict[str, Any]:
    """STUB：判定真偽。計畫 C 換成 LLM 研判。"""
    severity = state.get("severity", "medium")
    verdict = "true_positive" if severity in ("high", "critical") else "unknown"
    return {"verdict": verdict, "confidence": 0.5}


def attack_mapping(state: IncidentState) -> dict[str, Any]:
    """STUB：依告警內容對應 MITRE ATT&CK 技術。計畫 B 換成檢索式對應。

    確定性、離線：把告警類型、訊息與 IOC 串成一段文字，比對
    `_TECHNIQUE_RULES` 關鍵字，回傳命中的技術 ID（依規則順序去重）。
    無命中時回傳 `_DEFAULT_TECHNIQUE`。計畫 B 會換成本地 STIX/MITRE 檢索。
    """
    print("--- NODE: ATT&CK MAPPING ---")

    alert = state.get("alert", {})
    haystack = " ".join(
        str(part)
        for part in (
            state.get("alert_type", ""),
            alert.get("category", ""),
            alert.get("message", ""),
            *state.get("iocs", []),
        )
    ).lower()

    techniques: list[str] = []
    for keywords, technique in _TECHNIQUE_RULES:
        if any(keyword in haystack for keyword in keywords) and technique not in techniques:
            techniques.append(technique)

    if not techniques:
        techniques.append(_DEFAULT_TECHNIQUE)

    print(f"[*] Mapped Techniques: {techniques}")

    # 只回傳本節點負責更新的鍵。
    return {"attack_techniques": techniques}


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


# 看你們需不需要這部分的給助教看 mockup，不需要的話就 comment 或刪掉謝謝
if __name__ == "__main__":
    # Initialize a fake state passed from the previous node (Triage)
    print("MOCKUP TEST PREVIEW")

    test_state: IncidentState = {
        "alert": {
            "raw_message": (
                "Suspicious login from 192.168.1.100 and connection to malicious-domain.com"
            )
        },
        "alert_type": "Credential Access",
        "severity": "high",
        "iocs": [],
        "enrichment": {},
        "attack_techniques": [],
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
