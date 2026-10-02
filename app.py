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
from opportunity_radar import run_opportunity_radar, CATEGORY_LABELS, MODE_HINTS

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
    "🔎 Radar","Resumo","Ranking","Previsão","Portfólio","Cenários","Alertas","Orquestrador",
    "Rascunhos","Estoque","Desempenho","Fornecedores","Experimentos","Auditoria"
])

with tabs[0]:
    st.subheader("🔎 Radar de Oportunidades")
    st.write("O robô pesquisa fontes públicas e traz candidatos novos para investigação. O Score Radar é um filtro inicial — não é autorização automática para comprar estoque.")
    c1,c2,c3,c4=st.columns([2,2,1,1])
    category=c1.selectbox("Categoria",list(CATEGORY_LABELS.keys()),index=0)
    mode=c2.selectbox("Tipo de oportunidade",list(MODE_HINTS.keys()),index=0)
    max_queries=c3.selectbox("Buscas por rodada",[3,4,5,6,8,10],index=3)
    per_query=c4.selectbox("Resultados/busca",[5,8,10,15],index=1)
    st.caption(f"Esta rodada consumirá no máximo {max_queries} solicitações da Brave Search API.")

    if st.button("🚀 Iniciar Garimpo",type="primary"):
        with st.spinner("Garimpando fontes públicas..."):
            result=run_opportunity_radar(category,mode,max_queries,per_query)
            st.session_state["radar_result"]=result

    result=st.session_state.get("radar_result")
    if result:
        if not result.get("enabled"):
            st.error(result.get("message"))
        else:
            m1,m2,m3=st.columns(3)
            m1.metric("Buscas usadas",result.get("queries_used",0))
            m2.metric("Resultados únicos",result.get("results_found",0))
            high=sum(1 for x in result.get("rows",[]) if x.get("score_radar",0)>=68)
            m3.metric("Para investigar",high)
            rows=result.get("rows",[])
            if rows:
                df=pd.DataFrame(rows)
                show=["score_radar","classificacao","oportunidade","por_que_agora","fonte","descricao","url"]
                st.dataframe(df[show],use_container_width=True,hide_index=True,
                    column_config={"url":st.column_config.LinkColumn("Abrir fonte")})
                st.download_button(
                    "Baixar resultados CSV",
                    df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="radar_oportunidades.csv",
                    mime="text/csv"
                )
                st.info("Próxima etapa: pegue os candidatos com maior Score Radar e valide fornecedor, custo, margem, concorrência, logística e sazonalidade antes do teste real.")
            else:
                st.warning("Nenhum resultado foi retornado nesta rodada.")
            if result.get("errors"):
                with st.expander("Erros de algumas consultas"):
                    st.write(result["errors"])

with tabs[1]:
    st.dataframe(pd.DataFrame(s["top_products"]),use_container_width=True,hide_index=True)

with tabs[2]:
    r=latest_snapshots()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[3]:
    st.dataframe(pd.DataFrame(forecast_all(30)),use_container_width=True,hide_index=True)

with tabs[4]:
    st.dataframe(pd.DataFrame(optimize(20)),use_container_width=True,hide_index=True)

with tabs[5]:
    rows=compare_scenarios(30)
    st.dataframe(pd.DataFrame([{
        "cenario":x["scenario"],"pedidos":x["orders"],"faturamento":x["revenue"],
        "ads":x["ads"],"roas":x["roas"],"lucro":x["profit"],"margem":x["margin_pct"],
        "estoque_extra":x["stock_cash_needed"]
    } for x in rows]),use_container_width=True,hide_index=True)

with tabs[6]:
    r=automation_events(limit=500)
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[7]:
    r=orchestrator_tasks(limit=500)
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[8]:
    r=action_drafts(limit=500)
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[9]:
    r=inventory()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[10]:
    r=performance()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[11]:
    r=suppliers()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[12]:
    r=experiments()
    if r: st.dataframe(pd.DataFrame(r),use_container_width=True,hide_index=True)

with tabs[13]:
    st.write("Integridade do banco:",integrity_check())
    st.dataframe(pd.DataFrame(decision_log(limit=300)),use_container_width=True,hide_index=True)
