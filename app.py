
import streamlit as st
import pandas as pd
from db import (
    init_db,latest_snapshots,automation_events,orchestrator_tasks,action_drafts,
    inventory,performance,suppliers,scenario_runs,decision_log,scheduled_jobs,experiments
)
from executive_summary import build_executive_summary
from forecast import forecast_all
from portfolio_optimizer import optimize
from scenario_simulator import compare_scenarios
from automation_center import run_alert_center
from orchestrator import run_orchestrator
from executor_assistido import generate_drafts
from scheduler import run_due
from backup_audit import backup,integrity_check

st.set_page_config(page_title="Garimpeiro OS V20",layout="wide")
init_db()
st.title("🚀 Garimpeiro Shopee V20 — Garimpeiro OS")
st.caption("Sistema integrado de garimpo, decisão, caixa, estoque, Ads, sazonalidade e execução assistida.")

s=build_executive_summary(); k=s["kpis"]
cols=st.columns(8)
labels=[
    ("Pedidos",k["orders"]),("Faturamento",f"R$ {k['revenue']:.2f}"),
    ("Ads",f"R$ {k['ad_spend']:.2f}"),("ROAS",k["roas"]),
    ("Lucro",f"R$ {k['profit']:.2f}"),("Margem",f"{k['margin_pct']}%"),
    ("Estoque",f"R$ {k['stock_value']:.2f}"),("Alertas",k["critical_alerts"])
]
for c,(lab,val) in zip(cols,labels): c.metric(lab,val)

a,b,c,d,e=st.columns(5)
if a.button("Rodar alertas"): st.success(run_alert_center())
if b.button("Gerar tarefas"): st.success(run_orchestrator())
if c.button("Gerar rascunhos"): st.success(generate_drafts())
if d.button("Rodar agenda"): st.success(run_due())
if e.button("Backup agora"): st.success(f"Backup: {backup().name} | DB: {integrity_check()}")

tabs=st.tabs([
    "Resumo","Ranking","Previsão","Portfólio","Cenários","Alertas","Orquestrador",
    "Rascunhos","Estoque","Desempenho","Fornecedores","Experimentos","Auditoria"
])

with tabs[0]:
    st.dataframe(pd.DataFrame(s["top_products"]),use_container_width=True,hide_index=True)

with tabs[1]:
    r=latest_snapshots()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[2]:
    st.dataframe(pd.DataFrame(forecast_all(30)),use_container_width=True,hide_index=True)

with tabs[3]:
    st.dataframe(pd.DataFrame(optimize(20)),use_container_width=True,hide_index=True)

with tabs[4]:
    rows=compare_scenarios(30)
    st.dataframe(pd.DataFrame([{
        "cenario":x["scenario"],"pedidos":x["orders"],"faturamento":x["revenue"],
        "ads":x["ads"],"roas":x["roas"],"lucro":x["profit"],"margem":x["margin_pct"],
        "estoque_extra":x["stock_cash_needed"]
    } for x in rows]),use_container_width=True,hide_index=True)

with tabs[5]:
    r=automation_events(limit=500)
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[6]:
    r=orchestrator_tasks(limit=500)
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[7]:
    r=action_drafts(limit=500)
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[8]:
    r=inventory()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[9]:
    r=performance()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[10]:
    r=suppliers()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[11]:
    r=experiments()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[12]:
    st.write("Integridade do banco:",integrity_check())
    st.dataframe(pd.DataFrame(decision_log(limit=300)),use_container_width=True,hide_index=True)
