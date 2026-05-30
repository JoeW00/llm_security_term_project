from soc_agent.enrichers.abuse_ch import AbuseChEnricher

# 185.220.101.5 是真實可路由公網 IP；203.0.113.x 為 TEST-NET-3，Python 3.12 視為 private。
PUBLIC_IP = "185.220.101.5"
OK_RESP = {
    "query_status": "ok",
    "data": [{"malware_printable": "Cobalt Strike", "tags": ["botnet"]}],
}
NONE_RESP = {"query_status": "no_result", "data": []}


class FakeClient:
    def __init__(self, resp=None, raises=False):
        self._resp = resp
        self._raises = raises
        self.calls = []

    def post_json(self, url, payload):
        self.calls.append(payload)
        if self._raises:
            raise RuntimeError("network down")
        return self._resp


def test_ok_response_is_malicious():
    out = AbuseChEnricher(FakeClient(OK_RESP)).enrich([PUBLIC_IP])
    r = out[PUBLIC_IP]
    assert r.malicious is True
    assert r.source == "abuse.ch/ThreatFox"
    assert "Cobalt Strike" in r.tags


def test_no_result_is_not_malicious():
    out = AbuseChEnricher(FakeClient(NONE_RESP)).enrich([PUBLIC_IP])
    assert out[PUBLIC_IP].malicious is False


def test_private_ip_is_not_sent():
    client = FakeClient(OK_RESP)
    out = AbuseChEnricher(client).enrich(["192.168.1.10"])
    assert client.calls == []  # never left the boundary
    # 中性退回：不謊稱惡意、來源標示為 unavailable
    assert out["192.168.1.10"].source == "abuse.ch/unavailable"
    assert out["192.168.1.10"].malicious is False


def test_cgnat_ip_is_not_sent():
    client = FakeClient(OK_RESP)
    out = AbuseChEnricher(client).enrich(["100.64.0.1"])  # RFC 6598 CGNAT
    assert client.calls == []
    assert out["100.64.0.1"].source == "abuse.ch/unavailable"


def test_client_failure_falls_back():
    out = AbuseChEnricher(FakeClient(raises=True)).enrich([PUBLIC_IP])
    assert out[PUBLIC_IP].source == "abuse.ch/unavailable"  # neutral, not crash
    assert out[PUBLIC_IP].malicious is False


def test_cache_hit_avoids_second_call():
    client = FakeClient(OK_RESP)
    enr = AbuseChEnricher(client, cache={})
    enr.enrich([PUBLIC_IP])
    enr.enrich([PUBLIC_IP])
    assert len(client.calls) == 1


def test_raw_is_allowlisted_and_capped():
    noisy = {
        "query_status": "ok",
        "data": [
            {
                "malware_printable": "Cobalt Strike",
                "threat_type": "botnet_cc",
                "untrusted_blob": "x" * 9999,  # 不在白名單，應被丟棄
                "tags": ["t" * 999] + [f"tag{i}" for i in range(50)],  # 過長/過多，應被截斷
            }
        ],
    }
    r = AbuseChEnricher(FakeClient(noisy)).enrich([PUBLIC_IP])[PUBLIC_IP]
    assert "untrusted_blob" not in r.raw  # 非白名單欄位被丟棄
    assert set(r.raw).issubset(
        {"malware_printable", "threat_type", "confidence_level", "first_seen"}
    )
    assert len(r.tags) <= 20  # 筆數上限
    assert all(len(t) <= 64 for t in r.tags)  # 單一 tag 長度上限
