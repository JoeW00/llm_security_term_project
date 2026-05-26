"""最終事件報告的 Markdown 渲染（純函式、確定性）。"""

from __future__ import annotations

from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    """把結構化報告 dict 渲染為 Markdown 字串。"""
    techniques = report.get("attack_techniques") or []
    playbook = report.get("playbook") or {}

    lines = [
        "# SOC 事件回應報告",
        "",
        f"- **告警類型**：{report.get('alert_type')}",
        f"- **嚴重度**：{report.get('severity')}",
        f"- **研判**：{report.get('verdict')}",
        f"- **人工核准**：{report.get('approved')}",
    ]
    if report.get("approval_reason"):
        lines.append(f"- **核准理由**：{report['approval_reason']}")

    lines += ["", "## 研判理由", report.get("rationale") or "（無）"]

    lines += ["", "## MITRE ATT&CK 技術"]
    lines += [f"- {t}" for t in techniques] or ["（無）"]

    lines += ["", "## 處置劇本"]
    for phase in ("containment", "eradication", "recovery"):
        lines.append(f"### {phase}")
        steps = playbook.get(phase) or []
        lines += [f"- {s}" for s in steps] or ["（無）"]

    return "\n".join(lines)
