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
