# W15-B ATT&CK 對應消融：規則式關鍵字 vs BM25 檢索

> 來源：`scripts/eval/run_plan_b_attack_eval.py`（純本地、無金鑰）。
> 檢索語料：`data/enterprise-attack.json`（**697 技術**，父技術歸併）。
> 標註樣本 12 筆（SOC 告警語句 → 預期 MITRE 父技術）。產生時間：2026-05-30。

## 覆蓋率（預期技術是否落在 top-k）

| 對應器 | top-1 | top-3 |
|---|---|---|
| KeywordAttackMapper（4 規則） | 0.250 | 0.250 |
| RetrievalAttackMapper（BM25） | **0.667** | **0.750** |

> 關鍵字僅有 4 條規則（T1110/T1078/T1059/T1204），多數技術無法觸及，且 ransomware
> 被誤對應到 T1204（User Execution）而非正解 T1486。BM25 對 697 技術全語料檢索，
> 大幅提升覆蓋率與正確性。

## BM25 逐筆（top-3）

| 預期 | BM25 top-3 | 命中 | 告警語句 |
|---|---|---|---|
| T1110 | T1110, T1021, T1552 | ✅ | multiple failed SSH login attempts, brute force from single host |
| T1059 | T1027, T1059, T1546 | ✅ | powershell encoded command downloaded and executed a payload |
| T1486 | T1486, T1679, T1070 | ✅ | ransomware encrypted files across the host and dropped a ransom note |
| T1053 | T1053, T1037, T1547 | ✅ | scheduled task created to run a binary at logon for persistence |
| T1003 | T1003, T1555, T1547 | ✅ | credential dumping observed reading lsass process memory |
| T1566 | T1566, T1204, T1036 | ✅ | phishing email with malicious attachment opened by the user |
| T1021 | T1021, T1563, T1570 | ✅ | lateral movement using remote desktop protocol rdp to another server |
| T1547 | T1547, T1546, T1037 | ✅ | registry run key modified to autostart malware at boot |
| T1078 | T1614, T1110, T1555 | ❌ | valid account login from an unusual foreign geolocation |
| T1055 | T1055, T1218, T1134 | ✅ | code injected into explorer.exe via process injection |
| T1562 | T1685, T1546, T1556 | ❌ | windows defender antivirus was disabled to impair defenses |
| T1048 | T1071, T1572, T1583 | ❌ | data exfiltrated over dns tunneling to external server |
