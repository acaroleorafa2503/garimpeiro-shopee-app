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
from final_evaluator import evaluate_product
from price_intelligence import analyze_price_cost
from product_identity import extract_identity
from data_connectors import read_csv_file, combine_structured_data, SHOPEE_REQUIRED, SUPPLIER_REQUIRED
from auto_collector import refresh_registry, merge_rows

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
                cols_h=["status_fornecedor","fornecedor","compatibilidade_produto","confianca","evidencias","acao_sugerida","fonte","score_fornecedor","precos_encontrados","moq_estimado","descricao","url"]
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





st.divider()

st.divider()
st.subheader("⚙️ Coletor Automático de Fontes")
st.caption("Atualiza feeds CSV/JSON e APIs autorizadas cadastradas em data_sources.json. Não faz scraping de páginas da Shopee.")

if st.button("🔄 Atualizar fontes", key="refresh_sources"):
    try:
        refreshed=refresh_registry("data_sources.json")
        st.session_state["auto_sources_refresh"]=refreshed
        auto_shopee,prov_shopee=merge_rows(refreshed,"shopee")
        auto_supplier,prov_supplier=merge_rows(refreshed,"supplier")
        if auto_shopee:
            st.session_state["structured_shopee_rows"]=auto_shopee
        if auto_supplier:
            st.session_state["structured_supplier_rows"]=auto_supplier
        st.session_state["auto_sources_prov_shopee"]=prov_shopee
        st.session_state["auto_sources_prov_supplier"]=prov_supplier
    except Exception as exc:
        st.error(f"Falha ao atualizar fontes: {exc}")

refreshed=st.session_state.get("auto_sources_refresh",[])
if refreshed:
    status_rows=[]
    for r in refreshed:
        status_rows.append({
            "fonte":r.get("name"),
            "tipo":r.get("kind"),
            "status":"OK" if r.get("ok") else "ERRO",
            "registros":r.get("count",0),
            "atualizado_em":r.get("fetched_at"),
            "erro":r.get("error",""),
        })
    st.dataframe(pd.DataFrame(status_rows),use_container_width=True,hide_index=True)

auto_count_sh=len(st.session_state.get("structured_shopee_rows",[]))
auto_count_su=len(st.session_state.get("structured_supplier_rows",[]))
m1,m2=st.columns(2)
m1.metric("Registros Shopee estruturados",auto_count_sh)
m2.metric("Registros de fornecedores",auto_count_su)

st.subheader("🔌 Conector de Dados Shopee + Fornecedores")
st.caption("Importe CSVs estruturados para alimentar preço, vendidos, avaliações, custo, MOQ e frete. O Garimpeiro cruza os dados com a identidade do produto e ignora itens incompatíveis.")

c1,c2=st.columns(2)
shopee_file=c1.file_uploader("CSV Shopee",type=["csv"],key="csv_shopee")
supplier_file=c2.file_uploader("CSV Fornecedores",type=["csv"],key="csv_suppliers")

if shopee_file is not None:
    sh_rows,sh_missing=read_csv_file(shopee_file,SHOPEE_REQUIRED)
    if sh_missing:
        st.error("CSV Shopee sem colunas obrigatórias: "+", ".join(sh_missing))
    else:
        st.session_state["structured_shopee_rows"]=sh_rows
        st.success(f"CSV Shopee carregado: {len(sh_rows)} linhas.")

if supplier_file is not None:
    su_rows,su_missing=read_csv_file(supplier_file,SUPPLIER_REQUIRED)
    if su_missing:
        st.error("CSV Fornecedores sem colunas obrigatórias: "+", ".join(su_missing))
    else:
        st.session_state["structured_supplier_rows"]=su_rows
        st.success(f"CSV Fornecedores carregado: {len(su_rows)} linhas.")

conn_radar=st.session_state.get("radar_result") or {}
conn_candidates=[x.get("oportunidade","") for x in conn_radar.get("rows",[]) if isinstance(x,dict) and x.get("oportunidade")] if isinstance(conn_radar,dict) else []
conn_candidates=list(dict.fromkeys(conn_candidates))

if conn_candidates:
    connector_product=st.selectbox("Produto para cruzar dados",conn_candidates,key="connector_product")
    structured=combine_structured_data(connector_product,st.session_state.get("structured_shopee_rows",[]),st.session_state.get("structured_supplier_rows",[]))
    st.session_state["structured_result"]=structured
    a,b,c,d=st.columns(4)
    a.metric("Anúncios Shopee compatíveis",structured["shopee"]["count"])
    b.metric("Preço Shopee mediano",f"R$ {structured['auto_sale_price']:.2f}" if structured.get("auto_sale_price") else "Sem dado")
    c.metric("Fornecedores compatíveis",structured["suppliers"]["count"])
    d.metric("Menor custo",f"R$ {structured['auto_cost_price']:.2f}" if structured.get("auto_cost_price") else "Sem dado")
    if structured["shopee"]["matches"]:
        with st.expander("Dados Shopee compatíveis"):
            st.dataframe(pd.DataFrame(structured["shopee"]["matches"]),use_container_width=True,hide_index=True,column_config={"link":st.column_config.LinkColumn("Abrir")})
    if structured["suppliers"]["matches"]:
        with st.expander("Fornecedores compatíveis"):
            st.dataframe(pd.DataFrame(structured["suppliers"]["matches"]),use_container_width=True,hide_index=True,column_config={"link":st.column_config.LinkColumn("Abrir")})
else:
    st.info("Depois que o Radar encontrar um produto, os CSVs serão cruzados automaticamente com ele.")

st.divider()
st.subheader("💰 Inteligência de Preço e Custo")
st.caption("Busca faixas públicas de preço na Shopee, fornecedores e outros marketplaces. Preços de kit/lote são separados para evitar tratar total de caixa como custo unitário.")

price_radar = st.session_state.get("radar_result") or {}
price_candidates = [
    x.get("oportunidade","") for x in price_radar.get("rows",[])
    if isinstance(x,dict) and x.get("oportunidade")
] if isinstance(price_radar,dict) else []
price_candidates=list(dict.fromkeys(price_candidates))

if not price_candidates:
    st.info("Primeiro rode o Radar e gere pelo menos um produto candidato.")
else:
    pc1,pc2=st.columns([3,1])
    price_product=pc1.selectbox("Produto para analisar preço/custo",price_candidates,key="price_product")
    identity = extract_identity(price_product)
    if identity.get("generic"):
        st.warning("O nome do produto ainda está genérico. O sistema exigirá correspondência mais específica antes de aceitar preço ou custo.")
    else:
        st.caption("Identidade usada para validar preços: " + identity.get("canonical",""))
    price_queries=pc2.selectbox("Buscas de preço/custo",[4,6,8,10],index=1,key="price_queries")
    st.caption(f"Esta etapa consumirá no máximo {price_queries} solicitações adicionais da Brave Search API.")

    if st.button("💰 Buscar preço e custo",key="run_price_intel"):
        with st.spinner(f"Buscando preços e custos para {price_product}..."):
            pr=analyze_price_cost(price_product,price_queries,8)
            st.session_state["price_intel_result"]=pr

    pr=st.session_state.get("price_intel_result")
    if pr and pr.get("product")==price_product:
        if not pr.get("enabled"):
            st.error(pr.get("message"))
        else:
            sh=pr.get("shopee_stats",{})
            su=pr.get("supplier_stats",{})
            se=pr.get("secondary_stats",{})

            a1,a2,a3,a4=st.columns(4)
            a1.metric("Preço Shopee mediano",f"R$ {sh['median']:.2f}" if sh.get("median") else "Sem dado")
            a2.metric("Custo fornecedor mínimo",f"R$ {su['min']:.2f}" if su.get("min") else "Sem dado")
            a3.metric("Confiança preço",pr.get("sale_confidence","Baixa"))
            a4.metric("Confiança custo",pr.get("cost_confidence","Baixa"))

            b1,b2,b3=st.columns(3)
            b1.metric("Evidências Shopee",sh.get("count",0))
            b2.metric("Evidências fornecedor",su.get("count",0))
            b3.metric("Confirmações externas",se.get("count",0))

            price_rows=pr.get("rows",[])
            if price_rows:
                pdf=pd.DataFrame(price_rows)
                cols=["tipo","titulo","compatibilidade","fonte","precos_brutos","quantidade_lote","preco_unitario_derivado","confianca","descricao","url"]
                for c in cols:
                    if c not in pdf.columns:
                        pdf[c]=""
                st.dataframe(pdf[cols],use_container_width=True,hide_index=True,
                    column_config={"url":st.column_config.LinkColumn("Abrir fonte")})

            st.caption("O robô só usa automaticamente preço/custo quando há evidência pública. Valores podem refletir promoções ou variações e devem ser conferidos antes da compra.")

st.divider()
st.subheader("🧮 Decisão Final e Plano de Teste")
st.caption("Use os dados encontrados pelo robô e complete apenas o que não estiver disponível publicamente. Taxas e custos ficam como entradas editáveis para evitar suposições incorretas.")

radar_res = st.session_state.get("radar_result") or {}
inv_res = st.session_state.get("investigation_result") or {}
hunt_res = st.session_state.get("supplier_hunt_result") or {}

final_candidates = [
    x.get("oportunidade","") for x in radar_res.get("rows",[])
    if isinstance(x,dict) and x.get("oportunidade")
] if isinstance(radar_res,dict) else []
final_candidates=list(dict.fromkeys(final_candidates))

if not final_candidates:
    st.info("O cálculo final será liberado depois que o Radar encontrar pelo menos um produto.")
else:
    selected_final = st.selectbox("Produto para decisão final", final_candidates, key="final_product")

    radar_row = next((x for x in radar_res.get("rows",[]) if x.get("oportunidade")==selected_final), {})
    inv_current = inv_res if isinstance(inv_res,dict) and inv_res.get("product")==selected_final else {}
    hunt_current = hunt_res if isinstance(hunt_res,dict) and hunt_res.get("product")==selected_final else {}

    structured_current=st.session_state.get("structured_result") or {}
    if not isinstance(structured_current,dict) or structured_current.get("product")!=selected_final:
        structured_current={}
    price_current=st.session_state.get("price_intel_result") or {}
    if not isinstance(price_current,dict) or price_current.get("product")!=selected_final:
        price_current={}
    auto_sale=(structured_current.get("auto_sale_price") or price_current.get("auto_sale_price") or ((inv_current.get("preco_shopee") or {}).get("median") or 0))
    auto_cost=(structured_current.get("auto_cost_price") or price_current.get("auto_cost_price") or ((hunt_current.get("price_stats") or {}).get("min") or (inv_current.get("preco_fornecedor") or {}).get("min") or 0))
    auto_moq=int(structured_current.get("auto_moq") or 0)
    if not auto_moq:
        for rr in hunt_current.get("rows",[]) if isinstance(hunt_current,dict) else []:
            if rr.get("moq_estimado"):
                auto_moq=rr["moq_estimado"]
                break

    confirmed_supplier = (hunt_current.get("suppliers_confirmed",0) or 0) > 0
    shopee_evidence = str(radar_row.get("evidencia_shopee","")).startswith("✅") or inv_current.get("shopee_evidencias",0)>0

    if auto_sale <= 0:
        st.warning("O robô não encontrou preço Shopee confiável em trecho público. Informe um preço de venda para simular.")
    if auto_cost <= 0:
        st.warning("O robô não encontrou custo público confiável. Informe uma cotação/custo para concluir a margem.")

    f1,f2,f3,f4=st.columns(4)
    sale_price=f1.number_input("Preço de venda (R$)",min_value=0.0,value=float(auto_sale),step=1.0,key="final_sale")
    product_cost=f2.number_input("Custo produto (R$)",min_value=0.0,value=float(auto_cost),step=1.0,key="final_cost")
    auto_inbound=float(structured_current.get("auto_inbound_freight") or 0)
    inbound=f3.number_input("Frete de entrada/unidade (R$)",min_value=0.0,value=auto_inbound,step=0.5,key="final_inbound")
    packaging=f4.number_input("Embalagem/unidade (R$)",min_value=0.0,value=1.5,step=0.5,key="final_pack")

    p1,p2,p3,p4=st.columns(4)
    marketplace_fee=p1.number_input("Taxas marketplace (%)",min_value=0.0,max_value=100.0,value=0.0,step=0.5,key="final_fee")
    tax_pct=p2.number_input("Impostos (%)",min_value=0.0,max_value=100.0,value=0.0,step=0.5,key="final_tax")
    ad_pct=p3.number_input("Ads previsto (% da venda)",min_value=0.0,max_value=100.0,value=10.0,step=1.0,key="final_ads")
    loss_pct=p4.number_input("Devoluções/perdas (%)",min_value=0.0,max_value=100.0,value=2.0,step=0.5,key="final_loss")

    q1,q2,q3=st.columns(3)
    fixed_fee=q1.number_input("Tarifa fixa/unidade (R$)",min_value=0.0,value=0.0,step=0.5,key="final_fixed")
    target_margin=q2.number_input("Meta de margem líquida (%)",min_value=0.0,max_value=100.0,value=15.0,step=1.0,key="final_target_margin")
    test_budget=q3.number_input("Capital máximo para teste (R$)",min_value=50.0,value=500.0,step=50.0,key="final_budget")

    final = evaluate_product(
        sale_price=sale_price,
        product_cost=product_cost,
        inbound_freight=inbound,
        packaging=packaging,
        marketplace_fee_pct=marketplace_fee,
        fixed_fee=fixed_fee,
        tax_pct=tax_pct,
        ad_pct=ad_pct,
        return_loss_pct=loss_pct,
        target_margin_pct=target_margin,
        supplier_confirmed=confirmed_supplier,
        shopee_evidence=shopee_evidence,
        investigation_score=inv_current.get("score_investigacao",0),
        radar_score=radar_row.get("score_radar",0),
        moq=auto_moq,
        test_budget=test_budget,
    )

    st.markdown(f"### {final.get('decision')}")
    if not final.get("ready"):
        st.warning("Faltam: " + ", ".join(final.get("missing",[])))
    else:
        z1,z2,z3,z4,z5=st.columns(5)
        z1.metric("Lucro/unidade",f"R$ {final['profit_per_unit']:.2f}")
        z2.metric("Margem líquida",f"{final['margin_pct']:.1f}%")
        z3.metric("CAC máximo",f"R$ {final['cac_target']:.2f}")
        z4.metric("ROAS alvo",f"{final['roas_target']:.2f}" if final.get("roas_target") else "Sem dado")
        z5.metric("Unidades teste",final["test_units"])

        y1,y2,y3=st.columns(3)
        y1.metric("Capital do teste",f"R$ {final['test_capital']:.2f}")
        y2.metric("Lucro esperado/lote",f"R$ {final['expected_test_profit']:.2f}")
        y3.metric("CAC break-even",f"R$ {final['cac_break_even']:.2f}")

        if final.get("reasons"):
            st.write("**Pontos de atenção:** " + " • ".join(final["reasons"]))

        st.caption("A decisão é uma triagem operacional baseada nos dados disponíveis e nas premissas preenchidas. Confirme cotação, taxas aplicáveis e condições reais antes de comprar estoque.")

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
