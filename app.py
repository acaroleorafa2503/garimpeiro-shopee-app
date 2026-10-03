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
from deep_investigator import investigate_product
from supplier_hunter import hunt_suppliers

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
    st.write("O Radar é Shopee‑First: procura evidências ligadas à Shopee primeiro e usa fornecedores, Google e outros marketplaces apenas como confirmação. O Score Radar é um filtro inicial — não é autorização automática para comprar estoque.")
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
                show=["score_radar","classificacao","oportunidade","evidencia_shopee","fontes_confirmando","confirmacoes_secundarias","fornecedores_sinal","fontes","por_que_agora","descricao","url"]

                # Compatibilidade com resultados guardados por versões anteriores do Radar.
                defaults = {
                    "score_radar": 0,
                    "classificacao": "⚪ Reprocessar",
                    "oportunidade": "",
                    "evidencia_shopee": "—",
                    "fontes_confirmando": 1,
                    "confirmacoes_secundarias": 0,
                    "fornecedores_sinal": 0,
                    "fontes": "",
                    "por_que_agora": "",
                    "descricao": "",
                    "url": "",
                }
                missing_cols = [c for c in show if c not in df.columns]
                for c in missing_cols:
                    df[c] = defaults[c]

                if missing_cols:
                    st.warning("Este resultado foi gerado por uma versão anterior do Radar. Rode um novo garimpo para aplicar a lógica Shopee‑First e a consolidação de fontes.")

                st.dataframe(df[show],use_container_width=True,hide_index=True,
                    column_config={"url":st.column_config.LinkColumn("Abrir fonte")})
                st.download_button(
                    "Baixar resultados CSV",
                    df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="radar_oportunidades.csv",
                    mime="text/csv"
                )
                st.info("Regra Shopee‑First: candidatos sem evidência Shopee não recebem Prioridade Alta. Depois, valide fornecedor, custo, margem, concorrência, logística e sazonalidade antes do teste real.")
                supplier_rows=result.get("suppliers",[])
                if supplier_rows:
                    with st.expander(f"Fornecedores encontrados ({len(supplier_rows)})"):
                        st.dataframe(pd.DataFrame(supplier_rows),use_container_width=True,hide_index=True,
                            column_config={"url":st.column_config.LinkColumn("Abrir fornecedor")})

st.divider()
st.subheader("🧪 Investigador Automático de Produto")
st.caption("Selecione um candidato do Radar. A investigação usa novas buscas da API para reunir evidência Shopee, fornecedores, preços públicos e confirmações externas.")

radar_result_for_investigator = st.session_state.get("radar_result") or {}
investigator_rows = radar_result_for_investigator.get("rows", []) if isinstance(radar_result_for_investigator, dict) else []

candidate_names=[
    x.get("oportunidade","")
    for x in investigator_rows
    if isinstance(x, dict) and x.get("oportunidade")
]
candidate_names=list(dict.fromkeys(candidate_names))

if not candidate_names:
    st.info("Primeiro rode o Radar e gere pelo menos um produto candidato. Depois o Investigador será liberado.")
else:
    i1,i2=st.columns([3,1])
    selected_product=i1.selectbox("Produto para investigar",candidate_names,key="investigator_product")
    inv_queries=i2.selectbox("Buscas da investigação",[3,4,5,6],index=1,key="investigator_queries")
    st.caption(f"A investigação consumirá no máximo {inv_queries} solicitações adicionais da Brave Search API.")

    if st.button("🔬 Investigar produto",key="run_investigator"):
        with st.spinner(f"Investigando {selected_product}..."):
            inv=investigate_product(selected_product,inv_queries,8)
            st.session_state["investigation_result"]=inv

    inv=st.session_state.get("investigation_result")
    if inv and inv.get("product")==selected_product:
        if not inv.get("enabled"):
            st.error(inv.get("message"))
        else:
            st.markdown(f"### {inv.get('decisao_preliminar')}")
            j1,j2,j3,j4,j5=st.columns(5)
            j1.metric("Score investigação",inv.get("score_investigacao",0))
            j2.metric("Evidências Shopee",inv.get("shopee_evidencias",0))
            j3.metric("Fornecedores",inv.get("fornecedores_encontrados",0))
            j4.metric("Confirmações externas",inv.get("confirmacoes_secundarias",0))
            j5.metric("Confiança",inv.get("confianca","Baixa"))

            ps=inv.get("preco_shopee",{})
            pf=inv.get("preco_fornecedor",{})
            p1,p2,p3=st.columns(3)
            p1.metric("Preço Shopee mediano", f"R$ {ps['median']:.2f}" if ps.get("median") else "Sem dado")
            p2.metric("Menor preço fornecedor", f"R$ {pf['min']:.2f}" if pf.get("min") else "Sem dado")
            spread=inv.get("spread_bruto_pct")
            p3.metric("Spread bruto preliminar", f"{spread:.1f}%" if spread is not None else "Sem dado")

            if inv.get("motivos"):
                st.write("**Sinais encontrados:** " + " • ".join(inv["motivos"]))
            st.warning(inv.get("warning",""))

            evidence=inv.get("rows",[])
            if evidence:
                edf=pd.DataFrame(evidence)
                cols_show=["tipo","titulo","fonte","precos_encontrados","descricao","url"]
                for col in cols_show:
                    if col not in edf.columns:
                        edf[col]=""
                st.dataframe(edf[cols_show],use_container_width=True,hide_index=True,
                    column_config={"url":st.column_config.LinkColumn("Abrir fonte")})

            if inv.get("errors"):
                with st.expander("Erros de algumas consultas da investigação"):
                    st.write(inv["errors"])
            else:
                st.warning("Nenhum resultado foi retornado nesta rodada.")
            if result.get("errors"):
                with st.expander("Erros de algumas consultas"):
                    st.write(result["errors"])


st.divider()
st.subheader("🏭 Caçador de Fornecedores e Preços")
st.caption("Procura atacadistas, distribuidores e fabricantes usando nomes alternativos do produto. Esta etapa faz novas buscas da API.")

radar_result_for_hunter = st.session_state.get("radar_result") or {}
hunter_rows = radar_result_for_hunter.get("rows", []) if isinstance(radar_result_for_hunter, dict) else []
hunter_candidates = [
    x.get("oportunidade","")
    for x in hunter_rows
    if isinstance(x, dict) and x.get("oportunidade")
]
hunter_candidates = list(dict.fromkeys(hunter_candidates))

if not hunter_candidates:
    st.info("Primeiro rode o Radar e gere pelo menos um produto candidato. Depois o Caçador de Fornecedores será liberado.")
else:
    default_product = st.session_state.get("investigator_product")
    if default_product not in hunter_candidates:
        default_product = hunter_candidates[0]

    h1,h2=st.columns([3,1])
    hunter_product=h1.selectbox(
        "Produto para caçar fornecedores",
        hunter_candidates,
        index=hunter_candidates.index(default_product),
        key="hunter_product_select"
    )
    hunter_queries=h2.selectbox("Buscas de fornecedores",[4,5,6,8,10],index=2,key="hunter_queries")
    st.caption(f"Esta busca consumirá no máximo {hunter_queries} solicitações adicionais da Brave Search API.")

    if st.button("🏭 Caçar fornecedores",key="run_supplier_hunter"):
        with st.spinner(f"Procurando fornecedores para {hunter_product}..."):
            hunt=hunt_suppliers(hunter_product,hunter_queries,8)
            st.session_state["supplier_hunt_result"]=hunt

    hunt=st.session_state.get("supplier_hunt_result")
    if hunt and hunt.get("product")==hunter_product:
        if not hunt.get("enabled"):
            st.error(hunt.get("message"))
        else:
            hA,hB,hC,hD=st.columns(4)
            hA.metric("Fornecedores encontrados",hunt.get("suppliers_found",0))
            hB.metric("Confirmados",hunt.get("suppliers_confirmed",0))
            hC.metric("Possíveis",hunt.get("suppliers_possible",0))
            hD.metric("Buscas usadas",hunt.get("queries_used",0))

            ps_h=hunt.get("price_stats",{})
            hp1,hp2=st.columns(2)
            hp1.metric("Menor preço público",f"R$ {ps_h['min']:.2f}" if ps_h.get("min") else "Sem dado")
            hp2.metric("Preço mediano fornecedor",f"R$ {ps_h['median']:.2f}" if ps_h.get("median") else "Sem dado")

            variants=hunt.get("variants",[])
            if variants:
                st.write("**Nomes usados na procura:** " + " • ".join(variants))

            rows_h=hunt.get("rows",[])
            if rows_h:
                hdf=pd.DataFrame(rows_h)
                cols_h=["status_fornecedor","fornecedor","confianca","evidencias","acao_sugerida","fonte","score_fornecedor","precos_encontrados","moq_estimado","descricao","url"]
                for c in cols_h:
                    if c not in hdf.columns:
                        hdf[c]=""
                st.dataframe(hdf[cols_h],use_container_width=True,hide_index=True,
                    column_config={"url":st.column_config.LinkColumn("Abrir fornecedor")})
            else:
                st.warning("Nenhum fornecedor confiável foi encontrado nesta rodada. Tente aumentar as buscas ou ajustar o nome do produto.")

            if hunt.get("errors"):
                with st.expander("Erros de algumas consultas de fornecedor"):
                    st.write(hunt["errors"])

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
