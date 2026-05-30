# W15-B 情資增強 live 紀錄：abuse.ch ThreatFox

> 來源：`soc_agent/enrichers/abuse_ch.py` + `factory.py`，`uv run --group intel`。
> 實測時間：2026-05-30。

## 重點發現：abuse.ch 已改為需要免費 Auth-Key

實測 ThreatFox API（`POST https://threatfox-api.abuse.ch/api/v1/`）：

```
HTTP 401  {"error": "Unauthorized"}
```

abuse.ch 自 2024 起政策變更，**所有 API 查詢需附免費 Auth-Key**（於
<https://auth.abuse.ch> 註冊免費帳號取得），經 `Auth-Key` 標頭送出。原「免金鑰」
假設已過時。網路本身可達（取得真實 HTTP 回應，非連線錯誤）。

## 安全邊界對「真實未授權回應」正確降級（端到端實證）

無金鑰下對兩個 IOC 跑 `abuse_ch_enricher().enrich([...])`：

| IOC | 結果 source | malicious | 路徑 |
|---|---|---|---|
| `139.180.203.104`（公網） | `abuse.ch/unavailable` | `False` | 送出 → 401 → `lookup_failed` 中性退回 |
| `192.168.1.1`（私有） | `abuse.ch/unavailable` | `False` | **IOC 外送過濾，未送出** |

驗證了三件事：(1) 真實 401 被安全吸收、**不崩潰**；(2) 退回**不謊稱惡意**
（`malicious=False`，對照修補前會誤報 `malicious=True`）；(3) 私有 IP **未離開邊界**。

## 程式碼已就緒（拿到免費金鑰即可跑真實情資）

`factory.py` 已支援 `Auth-Key`：

```bash
# 1. 於 https://auth.abuse.ch 免費註冊取金鑰
export ABUSE_CH_AUTH_KEY=...
# 2. 直接跑（CLI/Demo 注入 abuse_ch_enricher() 即可出真實命中）
uv run --group intel python -c "
from soc_agent.enrichers.factory import abuse_ch_enricher
enr = abuse_ch_enricher()  # 自動讀 ABUSE_CH_AUTH_KEY
print(enr.enrich(['<已知惡意 IOC>']))
"
```

金鑰僅存在於 httpx client 的 `Auth-Key` 標頭，**不寫入 log/報告**。

## 離線基線（無金鑰、確定性）

`StaticEnricher`（預設）對任一 IOC 依型別回確定性 mock（IP→AbuseIPDB 風格、
其餘→VirusTotal 風格），供離線 Demo 與測試；真實命中需上述金鑰。

## 待辦（供第 16 週團隊報告）

- 取免費 `ABUSE_CH_AUTH_KEY` 後，對一組已知惡意 IOC 跑 `eval/enrich_eval.py`，
  產出「真實情資命中 vs StaticEnricher mock」對照。
- 可選：設金鑰加 AbuseIPDB / VirusTotal 來源（介面已就緒）。
