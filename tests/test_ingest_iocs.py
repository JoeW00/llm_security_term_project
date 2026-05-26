from soc_agent import nodes

ALERT = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "malware",
    "severity": "high",
    # message carries an IP, a domain, and a sha256 hash not present in indicators
    "message": (
        "host beaconing to evil.example.com (185.220.101.5), "
        "dropped payload sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "indicators": ["203.0.113.45"],
    "raw": {},
}


def test_ingest_merges_message_iocs_with_indicators():
    out = nodes.ingest({"alert": ALERT})
    iocs = out["iocs"]
    assert "203.0.113.45" in iocs  # original indicator kept
    assert "185.220.101.5" in iocs  # IP from message
    assert "evil.example.com" in iocs  # domain from message
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in iocs  # hash


def test_ingest_dedupes_iocs():
    alert = dict(ALERT, message="repeat 203.0.113.45 and 203.0.113.45", indicators=["203.0.113.45"])
    out = nodes.ingest({"alert": alert})
    assert out["iocs"].count("203.0.113.45") == 1


def test_ingest_no_message_iocs_keeps_indicators_only():
    alert = dict(ALERT, message="nothing useful here", indicators=["root"])
    out = nodes.ingest({"alert": alert})
    assert out["iocs"] == ["root"]


def test_extract_iocs_no_redos_on_adversarial_message():
    # 對抗性輸入：大量不以合法 TLD 結尾的標籤序列。舊的巢狀量詞正則會 catastrophic
    # backtracking 卡住數十秒（DoS）；線性正則應瞬間完成且不誤判為 domain。
    payload = "a-" * 50000
    iocs = nodes._extract_iocs(payload)
    assert iocs == []  # 無合法 domain，且不掛住


def test_extract_iocs_caps_message_length():
    # 防禦縱深：超過長度上限的訊息會被截斷後才做 regex；上限之後的 IOC 不應被抽出。
    domain = "late.example.com"
    padded = ("x " * nodes._MAX_MESSAGE_LEN) + domain
    assert domain not in nodes._extract_iocs(padded)
    assert "early.example.com" in nodes._extract_iocs("early.example.com then padding")
