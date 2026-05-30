"""Stub 節點：確定性、無 LLM、無網路。計畫 A–D 各自替換對應節點。"""

from __future__ import annotations

import re
from typing import Any

from soc_agent.approval import ApprovalPolicy, AutoApprovePolicy
from soc_agent.attack import AttackMapper, KeywordAttackMapper
from soc_agent.classifier import Classifier, RuleBasedClassifier
from soc_agent.enrichment import Enricher, StaticEnricher
from soc_agent.reasoners.critic import DeterministicCritic
from soc_agent.reasoners.investigator import RuleBasedInvestigator
from soc_agent.reasoners.playbook import TemplatePlaybookGenerator
from soc_agent.reasoning import Critic, Investigator, PlaybookGenerator
from soc_agent.reporting import render_markdown
from soc_agent.state import Alert, IncidentState

# triage 的預設分類器：確定性、離線。正式環境由 build_graph 注入 Ollama 後端。
_DEFAULT_CLASSIFIER = RuleBasedClassifier()
_DEFAULT_INVESTIGATOR = RuleBasedInvestigator()
_DEFAULT_PLAYBOOK_GENERATOR = TemplatePlaybookGenerator()
_DEFAULT_CRITIC = DeterministicCritic()
_DEFAULT_APPROVAL_POLICY = AutoApprovePolicy()
# attack_mapping 的預設對應器：確定性關鍵字對應。正式環境由 build_graph 注入 BM25 檢索。
_DEFAULT_ATTACK_MAPPER = KeywordAttackMapper()
# enrich 的預設情資增強器：確定性離線。正式環境由 build_graph 注入 abuse.ch 後端。
_DEFAULT_ENRICHER = StaticEnricher()

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


def enrich(state: IncidentState, *, enricher: Enricher | None = None) -> dict[str, Any]:
    """為每個 IOC 取威脅情資。計畫 B：預設離線 StaticEnricher，正式環境注入 abuse.ch。"""
    enricher = enricher or _DEFAULT_ENRICHER
    results = enricher.enrich(state.get("iocs", []))
    # 只回傳本節點負責更新的鍵（iocs 由 ingest 決定，這裡不覆寫）。
    return {"enrichment": {ioc: r.model_dump() for ioc, r in results.items()}}


def investigate(
    state: IncidentState, *, investigator: Investigator | None = None
) -> dict[str, Any]:
    """研判告警真偽。計畫 C：預設規則式，正式環境注入 LLM 研判。"""
    investigator = investigator or _DEFAULT_INVESTIGATOR
    result = investigator.assess(state)
    return {
        "verdict": result.verdict,
        "confidence": result.confidence,
        "rationale": result.rationale,
    }


def _attack_query(state: IncidentState) -> str:
    """把告警類型、類別、訊息與 IOC 串成檢索查詢文字（確定性）。"""
    alert = state.get("alert", {})
    return " ".join(
        str(part)
        for part in (
            state.get("alert_type", ""),
            alert.get("category", ""),
            alert.get("message", ""),
            *state.get("iocs", []),
        )
    )


def attack_mapping(state: IncidentState, *, mapper: AttackMapper | None = None) -> dict[str, Any]:
    """依告警內容對應 MITRE ATT&CK 技術。計畫 B：預設關鍵字，正式環境注入 BM25 檢索。"""
    mapper = mapper or _DEFAULT_ATTACK_MAPPER
    return {"attack_techniques": mapper.map(_attack_query(state))}


def playbook(state: IncidentState, *, generator: PlaybookGenerator | None = None) -> dict[str, Any]:
    """生成三階段處置劇本。計畫 C：預設模板，正式環境注入 LLM 生成。"""
    generator = generator or _DEFAULT_PLAYBOOK_GENERATOR
    return {"playbook": generator.generate(state).model_dump()}


def critique(state: IncidentState, *, critic: Critic | None = None) -> dict[str, Any]:
    """評分式自我批判，驅動反思迴圈。計畫 C：預設確定性，正式環境注入 LLM rubric。"""
    critic = critic or _DEFAULT_CRITIC
    result = critic.review(state)
    iterations = state.get("critique_iterations", 0) + 1
    return {"critique": result.model_dump(), "critique_iterations": iterations}


def human_approval(state: IncidentState, *, policy: ApprovalPolicy | None = None) -> dict[str, Any]:
    """處置動作前的安全閘門。計畫 D：預設自動核准，互動模式注入 interrupt 政策。"""
    policy = policy or _DEFAULT_APPROVAL_POLICY
    decision = policy.decide(state)
    return {"approved": decision.approved, "approval_reason": decision.reason}


def report(state: IncidentState) -> dict[str, Any]:
    """彙整最終結構化事件報告（JSON 結構 + Markdown 渲染）。"""
    data: dict[str, Any] = {
        "alert_type": state.get("alert_type"),
        "severity": state.get("severity"),
        "verdict": state.get("verdict"),
        "rationale": state.get("rationale", ""),
        "attack_techniques": state.get("attack_techniques", []),
        "playbook": state.get("playbook", {}),
        "approved": state.get("approved", False),
        "approval_reason": state.get("approval_reason", ""),
    }
    data["markdown"] = render_markdown(data)
    return {"final_report": data}
