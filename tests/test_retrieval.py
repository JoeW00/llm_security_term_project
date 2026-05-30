from pathlib import Path

from soc_agent.attack import AttackMapper
from soc_agent.attack_mappers.retrieval import (
    RetrievalAttackMapper,
    TechniqueDoc,
    load_attack_patterns,
)

DOCS = [
    TechniqueDoc(
        "T1110",
        "Brute Force",
        "Brute Force adversaries may guess passwords; repeated failed login attempts",
    ),
    TechniqueDoc(
        "T1059",
        "Command and Scripting Interpreter",
        "powershell command line script interpreter execution",
    ),
    TechniqueDoc("T1204", "User Execution", "malware trojan ransomware relies on user execution"),
    # 兩個子技術都歸併到父技術 T1055
    TechniqueDoc("T1055", "Process Injection", "process injection inject code into processes"),
    TechniqueDoc("T1055", "Process Injection", "extra window memory injection technique"),
]


def test_retrieval_ranks_brute_force_first():
    out = RetrievalAttackMapper(DOCS, top_k=2).map("repeated failed login brute force")
    assert out[0] == "T1110"


def test_retrieval_finds_powershell():
    assert "T1059" in RetrievalAttackMapper(DOCS, top_k=3).map("attacker ran a powershell script")


def test_retrieval_dedupes_parent_technique():
    out = RetrievalAttackMapper(DOCS, top_k=5).map("process injection into memory")
    assert out.count("T1055") == 1


def test_retrieval_no_match_returns_empty():
    assert RetrievalAttackMapper(DOCS, top_k=3).map("zzz qqq nothing relevant") == []


def test_retrieval_is_deterministic():
    m = RetrievalAttackMapper(DOCS, top_k=3)
    assert m.map("failed login brute force") == m.map("failed login brute force")


def test_retrieval_satisfies_protocol():
    assert isinstance(RetrievalAttackMapper(DOCS), AttackMapper)


def test_load_attack_patterns_parses_and_normalizes_subtechniques():
    path = Path(__file__).parent / "fixtures" / "mini_attack.json"
    docs = load_attack_patterns(path)
    ids = {d.technique_id for d in docs}
    assert "T1110" in ids
    assert "T1055" in ids  # T1055.011 normalized to parent
    assert "T1059" in ids
    # revoked / deprecated entries are dropped
    assert "T9999" not in ids
