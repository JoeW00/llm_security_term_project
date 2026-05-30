from soc_agent.attack import AttackMapper, KeywordAttackMapper


def test_keyword_maps_authentication_to_t1110():
    assert "T1110" in KeywordAttackMapper().map("84 failed login brute force attempts")


def test_keyword_maps_malware_to_t1204():
    assert "T1204" in KeywordAttackMapper().map("ransomware signature match")


def test_keyword_empty_query_returns_default_technique():
    assert KeywordAttackMapper().map("") == ["T1078"]


def test_keyword_dedupes_techniques():
    out = KeywordAttackMapper().map("brute force and more brute force authentication")
    assert out.count("T1110") == 1


def test_keyword_satisfies_protocol():
    assert isinstance(KeywordAttackMapper(), AttackMapper)
