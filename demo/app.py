"""Streamlit Demo：互動式 SOC 事件回應 + 人工核准關卡 + 注入韌性面板。

啟動：uv run --group demo streamlit run demo/app.py
"""

from __future__ import annotations

import json
import uuid

import streamlit as st

from demo.controller import (
    IncidentSession,
    injection_report,
    list_sample_alerts,
    load_alert,
)
from soc_agent.reporting import render_markdown

st.set_page_config(page_title="SOC Agent Demo", layout="wide")
st.title("自主式 SOC Tier-1 事件回應代理")

# --- Sidebar：選告警 ---
st.sidebar.header("告警輸入")
samples = list_sample_alerts()
sample_names = [p.name for p in samples]
choice = st.sidebar.selectbox("選擇樣本告警", ["（上傳檔案）", *sample_names])
uploaded = st.sidebar.file_uploader("或上傳告警 JSON", type="json")
use_llm = st.sidebar.checkbox("使用 live LLM（需 ANTHROPIC_API_KEY）")

alert: dict | None = None
if choice != "（上傳檔案）":
    alert = load_alert(samples[sample_names.index(choice)])
elif uploaded is not None:
    try:
        alert = json.load(uploaded)
    except json.JSONDecodeError as exc:
        st.sidebar.error(f"JSON 解析失敗：{exc}")

if st.sidebar.button("Run", disabled=alert is None) and alert is not None:
    reasoners = None
    if use_llm:
        try:
            from soc_agent.reasoners.factory import anthropic_llm_client, llm_reasoners

            reasoners = llm_reasoners(anthropic_llm_client())
        except RuntimeError as exc:
            st.sidebar.error(str(exc))
            st.stop()
    session = IncidentSession(thread_id=str(uuid.uuid4()), reasoners=reasoners)
    st.session_state["pending"] = session.start(alert)
    st.session_state["session"] = session
    st.session_state.pop("final_report", None)

# --- 主區：核准流程 ---
pending = st.session_state.get("pending")
final_report = st.session_state.get("final_report")

if pending is not None and final_report is None:
    st.subheader("報告預覽（待人工核准）")
    st.markdown(render_markdown(pending.state))
    reason = st.text_input("核准／駁回理由", key="reason")
    col_ok, col_no = st.columns(2)
    if col_ok.button("✅ 核准"):
        st.session_state["final_report"] = st.session_state["session"].resume(True, reason)
        st.rerun()
    if col_no.button("❌ 駁回"):
        st.session_state["final_report"] = st.session_state["session"].resume(False, reason)
        st.rerun()

if final_report is not None:
    st.subheader("最終事件報告")
    st.markdown(final_report.get("markdown", ""))
    st.json({k: v for k, v in final_report.items() if k != "markdown"})

# --- 注入韌性面板 ---
with st.expander("提示注入韌性評估"):
    if st.button("Run injection suite"):
        report = injection_report()
        st.metric("Manipulation rate", f"{report.manipulation_rate:.0%}")
        st.write(f"total={report.total}, manipulated={report.manipulated}")
        if report.manipulated_names:
            st.write("被操控案例：", report.manipulated_names)
