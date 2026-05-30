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
    assert out["192.168.1.10"].source == "AbuseIPDB"  # offline fallback (StaticEnricher)


def test_client_failure_falls_back():
    out = AbuseChEnricher(FakeClient(raises=True)).enrich([PUBLIC_IP])
    assert out[PUBLIC_IP].source == "AbuseIPDB"  # fallback, not crash


def test_cache_hit_avoids_second_call():
    client = FakeClient(OK_RESP)
    enr = AbuseChEnricher(client, cache={})
    enr.enrich([PUBLIC_IP])
    enr.enrich([PUBLIC_IP])
    assert len(client.calls) == 1
