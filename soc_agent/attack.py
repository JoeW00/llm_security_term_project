"""ATT&CK 對應邊界：可注入的 MITRE 技術對應契約與離線預設實作。

`attack_mapping` 節點透過 `AttackMapper` 介面取得裸技術 ID 清單（如 "T1110"）。
預設為確定性關鍵字對應 `KeywordAttackMapper`；正式環境可注入 BM25 檢索式
`RetrievalAttackMapper`（見 soc_agent/attack_mappers/retrieval.py）。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# 關鍵字 → MITRE ATT&CK 技術 ID 的最小對應表（沿用骨架 stub 規則）。
_TECHNIQUE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("brute force", "failed login", "failed password", "authentication"), "T1110"),
    (("valid account", "successful login", "compromised credential"), "T1078"),
    (("powershell", "command", "script", "/bin/sh", "cmd.exe"), "T1059"),
    (("malware", "trojan", "virus", "ransomware"), "T1204"),
)
# 無任何規則命中時的保底技術（Valid Accounts）。
_DEFAULT_TECHNIQUE = "T1078"


@runtime_checkable
class AttackMapper(Protocol):
    """結構型介面：吃一段查詢文字，回傳裸 MITRE 技術 ID 清單。"""

    def map(self, query: str) -> list[str]: ...


class KeywordAttackMapper:
    """確定性、離線的預設對應：比對關鍵字規則，無命中時回保底技術。"""

    def map(self, query: str) -> list[str]:
        haystack = query.lower()
        techniques: list[str] = []
        for keywords, technique in _TECHNIQUE_RULES:
            if any(keyword in haystack for keyword in keywords) and technique not in techniques:
                techniques.append(technique)
        if not techniques:
            techniques.append(_DEFAULT_TECHNIQUE)
        return techniques
