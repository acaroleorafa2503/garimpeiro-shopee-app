from forecast_engine import build_realistic_forecast
from ads_brain_engine import build_ads_brain
from investigation_engine import investigate_existing_opportunity
from persistence_store import configured as persistence_configured, healthcheck as persistence_healthcheck, save_products as persist_products, load_latest_products as load_persisted_products
from competitor_engine import analyze_market, strategy_from_market
from seasonality_engine import apply_seasonality_to_rows, detect_seasonality
from selfcheck import run_selfcheck
from auto_discovery import CATEGORY_SEEDS, discovery_plan, merge_discovery_results, rank_discovered, estimated_calls, discovery_run_summary, top_candidates, filter_by_category_relevance, build_commercial_clusters
from scale_radar import save_snapshot, scale_signal, competitor_vulnerability, forecast_from_signal, build_alerts
from landed_cost import landed_cost_brazil, profitability
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
from nexscope_shopee import search_products, as_structured_shopee_rows, ORDER_LABELS, enabled as nexscope_enabled


def _get_nexscope_product_by_name(name):
    result = st.session_state.get("nexscope_result") or {}
    products = result.get("products", []) if isinstance(result, dict) else []
    for p in products:
        if p.get("produto") == name:
            return p
    return None

def _merge_nexscope_into_investigation(product_name, investigation):
    """
    Injects already-fetched structured Shopee evidence into the legacy investigator
    so the investigator does not forget the real Shopee record.
    """
    p = _get_nexscope_product_by_name(product_name)
    if not p or not isinstance(investigation, dict):
        return investigation

    investigation = dict(investigation)

    # Strong structured Shopee evidence from the exact selected product.
    investigation["evidencias_shopee"] = max(int(investigation.get("evidencias_shopee") or 0), 1)
    investigation["shopee_evidencias"] = max(int(investigation.get("shopee_evidencias") or 0), 1)

    # Preserve/raise confidence because the exact item came from a structured Shopee result.
    old_score = int(investigation.get("score_investigacao") or 0)
    structured_score = int(p.get("score_shopee") or 0)
    investigation["score_investigacao"] = max(old_score, structured_score)

    if structured_score >= 75:
        investigation["confianca"] = "Alta"
    elif structured_score >= 60 and investigation.get("confianca") in (None, "", "Baixa"):
        investigation["confianca"] = "Média"

    # Structured Shopee price.
    price = p.get("preco")
    if isinstance(price, (int, float)) and price > 0:
        investigation["preco_shopee"] = {
            "median": float(price),
            "min": float(p.get("preco_min") or price),
            "max": float(p.get("preco_max") or price),
            "source": "Shopee via Nexscope"
        }

    # Detailed structured evidence for UI/debugging and later financial evaluator.
    investigation["nexscope_shopee"] = {
        "produto": p.get("produto"),
        "preco": p.get("preco"),
        "vendidos_30d": p.get("vendidos_30d"),
        "vendidos_historicos": p.get("vendidos_historicos"),
        "faturamento_30d": p.get("faturamento_30d"),
        "avaliacao": p.get("avaliacao"),
        "qtd_avaliacoes": p.get("qtd_avaliacoes"),
        "estoque": p.get("estoque"),
        "loja": p.get("loja"),
        "url": p.get("url"),
        "source": "Shopee via Nexscope",
    }

    # Never force supplier confirmation. Supplier side remains independent.
    suppliers = int(investigation.get("fornecedores") or 0)
    if suppliers > 0:
        investigation["decisao"] = investigation.get("decisao") or "AVANÇAR PARA COTAÇÃO REAL"
        investigation["decisao_preliminar"] = "🟢 DEMANDA SHOPEE CONFIRMADA — VALIDAR MARGEM"
    else:
        investigation["decisao"] = "PROCURAR / VALIDAR FORNECEDOR"
        investigation["decisao_preliminar"] = "🟡 DEMANDA SHOPEE CONFIRMADA — PROCURAR FORNECEDOR"

    return investigation

from deep_investigator import investigate_product
from supplier_hunter import hunt_suppliers
from nexscope_1688 import search_1688, suggest_chinese_keyword, SORT_LABELS as SORT_1688_LABELS
from final_evaluator import evaluate_product
from price_intelligence import analyze_price_cost
from product_identity import extract_identity
from data_connectors import read_csv_file, combine_structured_data, SHOPEE_REQUIRED, SUPPLIER_REQUIRED
from auto_collector import refresh_registry, merge_rows

st.set_page_config(page_title="Garimpeiro OS V20",layout="wide")
init_db()

# V17: carrega produtos persistidos uma vez por sessão.
if "persistent_bootstrap_done" not in st.session_state:
    st.session_state["persistent_bootstrap_done"]=True
    if persistence_configured():
        try:
            _persisted=load_persisted_products(limit=2000)
            if _persisted.get("ok") and _persisted.get("products"):
                _pp=_persisted["products"]
                st.session_state["auto_discovery_products"]=_pp
                st.session_state["auto_discovery_ranked"]=rank_discovered(_pp)
                try:
                    st.session_state["auto_discovery_clusters"]=apply_seasonality_to_rows(build_commercial_clusters(_pp))
                except Exception:
                    pass
                st.session_state["persistence_loaded_count"]=len(_pp)
            elif not _persisted.get("ok"):
                st.session_state["persistence_error"]=_persisted.get("error")
        except Exception as _persist_err:
            st.session_state["persistence_error"]=str(_persist_err)

st.title("🚀 Garimpeiro Shopee — V21 Previsão Realista")

with st.expander("🧪 Diagnóstico da versão"):
    _sc=run_selfcheck()
    if _sc.get("ok"):
        st.success("Estrutura principal carregada corretamente.")
    else:
        st.error("Há falha estrutural nesta versão.")
    st.json(_sc)
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


    st.subheader("🤖 Garimpo Automático — Descoberta")
    st.caption("Modo principal: o robô percorre categorias sozinho, encontra produtos reais da Shopee e monta um ranking geral.")
    _pc1,_pc2=st.columns([1,3])
    if persistence_configured():
        _loaded=int(st.session_state.get("persistence_loaded_count") or 0)
        _pc1.success("💾 Banco persistente ativo")
        _pc2.caption(f"{_loaded} produtos restaurados do banco nesta sessão." if _loaded else "Banco persistente configurado. Novas coletas serão salvas.")
    else:
        _pc1.warning("💾 Banco persistente não configurado")
        _pc2.caption("Configure SUPABASE_URL e SUPABASE_KEY nos Secrets para não perder coletas após deploy.")
    if st.session_state.get("persistence_error"):
        st.warning("Persistência: "+str(st.session_state.get("persistence_error")))


    _auto_cats=st.multiselect(
        "Categorias para varrer",
        list(CATEGORY_SEEDS.keys()),
        default=list(CATEGORY_SEEDS.keys()),
        key="auto_discovery_categories"
    )

    _a1,_a2,_a3=st.columns(3)
    _auto_depth=_a1.selectbox("Profundidade",["Rápido","Normal","Profundo"],index=0,key="auto_discovery_depth")
    _auto_results=_a2.selectbox("Produtos por busca",[10,20,30],index=0,key="auto_discovery_results")
    _auto_sort=_a3.selectbox("Priorizar",["Mais vendidos (30 dias)","Mais avaliações","Melhor avaliação"],index=0,key="auto_discovery_sort")

    _plan=discovery_plan(_auto_cats,_auto_depth)
    st.caption(f"Esta rodada fará até {estimated_calls(_auto_cats,_auto_depth)} chamadas Nexscope. Confira seus créditos antes de iniciar.")

    if st.button("🤖 Iniciar Garimpo Automático",type="primary",key="auto_discovery_run"):
        if not _auto_cats:
            st.warning("Selecione pelo menos uma categoria.")
        else:
            _batches=[]
            _errors=[]
            _progress=st.progress(0)
            _status=st.empty()
            _sort_map={"Mais vendidos (30 dias)":"sold","Mais avaliações":"ratings","Melhor avaliação":"rating"}

            for _i,_job in enumerate(_plan,start=1):
                _status.write(f"Buscando {_job['category']} → {_job['keyword']} ({_i}/{len(_plan)})")
                try:
                    _res=search_products(
                        keyword=_job["keyword"],
                        station="BR",
                        page=1,
                        page_size=int(_auto_results),
                        keyword_type=2,
                        order_by=_sort_map[_auto_sort],
                        order_by_type="DESC",
                    )
                    if _res.get("ok"):
                        _products=_res.get("products",[])
                        try:
                            save_snapshot(_products)
                        except Exception:
                            pass
                        _batches.append({"category":_job["category"],"keyword":_job["keyword"],"products":_products})
                    else:
                        _err_text=str(_res.get("error","erro"))
                        _errors.append(f"{_job['keyword']}: {_err_text}")
                        if "not enough credits" in _err_text.lower() or "insufficient credit" in _err_text.lower():
                            st.session_state["nexscope_credit_blocked"]=True
                            _status.warning("Nexscope sem créditos. A varredura foi interrompida na primeira falha para evitar tentativas desnecessárias.")
                            _progress.progress(_i/max(1,len(_plan)))
                            break
                except Exception as _e:
                    _errors.append(f"{_job['keyword']}: {_e}")
                _progress.progress(_i/max(1,len(_plan)))

            _merged=merge_discovery_results(_batches)
            _ranked=rank_discovered(_merged)
            st.session_state["auto_discovery_products"]=_merged
            st.session_state["auto_discovery_ranked"]=_ranked
            st.session_state["auto_discovery_errors"]=_errors
            st.session_state["auto_discovery_summary"]=discovery_run_summary(_ranked,_errors)

            if _merged:
                try:
                    _clusters=apply_seasonality_to_rows(build_commercial_clusters(_merged))
                    st.session_state["auto_discovery_clusters"]=_clusters
                except Exception as _cluster_save_err:
                    st.session_state["persistence_error"]="Ranking local: "+str(_cluster_save_err)

                if persistence_configured():
                    try:
                        _save_p=persist_products(_merged,source="auto_discovery")
                        if _save_p.get("ok"):
                            st.session_state["persistence_last_saved"]=_save_p.get("saved",0)
                            st.session_state["persistence_loaded_count"]=len(_merged)
                        else:
                            st.session_state["persistence_error"]=_save_p.get("error")
                    except Exception as _persist_save_err:
                        st.session_state["persistence_error"]=str(_persist_save_err)

            if not st.session_state.get("nexscope_credit_blocked"):
                _status.empty()

    _auto_ranked=st.session_state.get("auto_discovery_ranked") or []
    _auto_errors=st.session_state.get("auto_discovery_errors") or []
    _clusters_auto=st.session_state.get("auto_discovery_clusters") or []

    # Rebuild clusters locally from already-collected products/ranked rows when possible.
    if not _clusters_auto:
        _existing_products=st.session_state.get("auto_discovery_products") or []
        if not _existing_products and _auto_ranked:
            _existing_products=[
                r.get("_product")
                for r in _auto_ranked
                if isinstance(r,dict) and r.get("_product")
            ]
        if _existing_products:
            try:
                _clusters_auto=apply_seasonality_to_rows(build_commercial_clusters(_existing_products))
                st.session_state["auto_discovery_clusters"]=_clusters_auto
            except Exception as _cluster_err:
                st.warning(f"Não foi possível reconstruir o ranking local: {_cluster_err}")

    if _clusters_auto and "evento_sazonal" not in _clusters_auto[0]:
        _clusters_auto=apply_seasonality_to_rows(_clusters_auto)
        st.session_state["auto_discovery_clusters"]=_clusters_auto

    if _auto_ranked:
        _m1,_m2,_m3,_m4=st.columns(4)
        _m1.metric("Produtos únicos",len(_auto_ranked))
        _m2.metric("Prioridade alta",len([r for r in _auto_ranked if r["score_oportunidade"]>=80]))
        _m3.metric("Para investigar",len([r for r in _auto_ranked if 65<=r["score_oportunidade"]<80]))
        _m4.metric("Com histórico",len([r for r in _auto_ranked if r["snapshots"]>=2]))


        st.markdown("#### 🏆 Oportunidades comerciais encontradas")
        if "_clusters_auto" not in locals():
            _clusters_auto=st.session_state.get("auto_discovery_clusters") or []
        st.caption("♻️ Se já existirem produtos coletados na sessão, o ranking é reconstruído localmente sem consumir novos créditos Nexscope.")
    
        if _clusters_auto:
            _dfc=pd.DataFrame(_clusters_auto)
            _cols=[
                "acao","score_oportunidade_hoje","score_aceleracao","momento","snapshots",
                "produto","anuncios_similares","preco_representante","preco_mediano_cluster",
                "vendidos_30d","avaliacao","qtd_avaliacoes","loja","risco","por_que","url"
            ]
            st.dataframe(_dfc[_cols],use_container_width=True,hide_index=True,column_config={"url":st.column_config.LinkColumn("Abrir na Shopee")})

            _invest=[r for r in _clusters_auto if r["acao"] in ("🟢 INVESTIGAR AGORA","🚀 PRIORIDADE MÁXIMA")]
            _monitor=[r for r in _clusters_auto if r["acao"]=="🟡 MONITORAR + INVESTIGAR"]
            _risk=[r for r in _clusters_auto if r["acao"]=="🔴 REVISAR RISCO"]
            c1,c2,c3,c4=st.columns(4)
            c1.metric("Clusters de produto",len(_clusters_auto))
            c2.metric("Investigar agora",len(_invest))
            c3.metric("Monitorar",len(_monitor))
            c4.metric("Revisar risco",len(_risk))

            _names=[r["produto"] for r in _clusters_auto[:60]]
            _sel=st.selectbox("Oportunidade para aprofundar",_names,key="auto_discovery_selected_cluster")
            _chosen=next((r for r in _clusters_auto if r["produto"]==_sel),None)

            if _chosen:
                st.info(
                    f"Ação: {_chosen['acao']} | Oportunidade hoje: {_chosen['score_oportunidade_hoje']} | "
                    f"Aceleração: {_chosen['score_aceleracao']} | Anúncios similares: {_chosen['anuncios_similares']} | "
                    f"Risco: {_chosen['risco']} | Por quê: {_chosen['por_que']}"
                )
                if st.button("➡️ Enviar oportunidade para investigação",key="auto_send_investigation_v15"):
                    _p=_chosen["_product"]
                    _row={
                        "score_radar":_chosen["score_oportunidade_hoje"],
                        "classificacao":_chosen["acao"],
                        "oportunidade":_p.get("produto",""),
                        "evidencia_shopee":"✅ Sim",
                        "fontes_confirmando":1,
                        "confirmacoes_secundarias":0,
                        "fornecedores_sinal":0,
                        "fontes":"Descoberta automática + cluster comercial + Shopee via Nexscope",
                        "por_que_agora":_chosen["por_que"],
                        "descricao":f"Preço R$ {_p.get('preco')} | Vendidos 30d {_p.get('vendidos_30d')} | Avaliação {_p.get('avaliacao')}",
                        "url":_p.get("url",""),
                    }
                    _cur=st.session_state.get("radar_result") or {}
                    _rows=_cur.get("rows",[]) if isinstance(_cur,dict) else []
                    _rows=[x for x in _rows if x.get("oportunidade")!=_row["oportunidade"]]
                    _rows.insert(0,_row)
                    st.session_state["radar_result"]={
                        "enabled":True,"message":"Oportunidade automática enviada para investigação.",
                        "queries_used":0,"results_found":len(_rows),"rows":_rows,
                        "suppliers":_cur.get("suppliers",[]) if isinstance(_cur,dict) else [],
                    }
                    st.session_state["nexscope_result"]={
                        "ok":True,
                        "products":[r["_product"] for r in _clusters_auto],
                        "summary":{"total_size":len(_clusters_auto),"source_type":"auto_discovery_clusters"}
                    }
                    st.success("Oportunidade enviada para o Investigador com dados estruturados preservados.")

        _rej=st.session_state.get("auto_discovery_rejected") or []
        if _rej:
            with st.expander(f"🧹 {len(_rej)} resultados fora da categoria foram filtrados"):
                _show=[]
                for x in _rej[:30]:
                    p=x.get("product",{})
                    _show.append({
                        "categoria":x.get("category"),"termo":x.get("keyword"),
                        "produto":p.get("produto"),"relevancia":p.get("relevancia_categoria"),
                        "motivo":p.get("relevancia_motivo"),
                    })
                st.dataframe(pd.DataFrame(_show),use_container_width=True,hide_index=True)


    if persistence_configured():
        _ps1,_ps2=st.columns([1,3])
        if _ps1.button("♻️ Recarregar banco salvo",key="reload_persistent_products"):
            try:
                _reload=load_persisted_products(limit=2000)
                if _reload.get("ok"):
                    _rprod=_reload.get("products") or []
                    st.session_state["auto_discovery_products"]=_rprod
                    st.session_state["auto_discovery_ranked"]=rank_discovered(_rprod)
                    st.session_state["auto_discovery_clusters"]=apply_seasonality_to_rows(build_commercial_clusters(_rprod)) if _rprod else []
                    st.session_state["persistence_loaded_count"]=len(_rprod)
                    st.success(f"{len(_rprod)} produtos restaurados do banco persistente.")
                    st.rerun()
                else:
                    st.error("Falha ao ler banco persistente: "+str(_reload.get("error")))
            except Exception as _reload_err:
                st.error("Falha ao ler banco persistente: "+str(_reload_err))
        _last_saved=st.session_state.get("persistence_last_saved")
        if _last_saved is not None:
            _ps2.caption(f"Último salvamento persistente: {_last_saved} produtos.")

    if _auto_errors:
        with st.expander(f"⚠️ {len(_auto_errors)} buscas tiveram erro"):
            for _err in _auto_errors:
                st.write(_err)

    st.divider()

    st.markdown("#### ✅ Status do Garimpeiro Automático")
    _status_clusters=st.session_state.get("auto_discovery_clusters") or []
    if _status_clusters and "evento_sazonal" not in _status_clusters[0]:
        _status_clusters=apply_seasonality_to_rows(_status_clusters)
        st.session_state["auto_discovery_clusters"]=_status_clusters
    if not _status_clusters:
        _status_products=st.session_state.get("auto_discovery_products") or []
        if _status_products:
            try:
                _status_clusters=build_commercial_clusters(_status_products)
                st.session_state["auto_discovery_clusters"]=_status_clusters
            except Exception:
                _status_clusters=[]

    _summary_auto=st.session_state.get("auto_discovery_summary")
    if not _summary_auto and st.session_state.get("auto_discovery_ranked"):
        _summary_auto=discovery_run_summary(
            st.session_state.get("auto_discovery_ranked") or [],
            st.session_state.get("auto_discovery_errors") or []
        )
    _run_at=st.session_state.get("auto_discovery_run_at")
    if _status_clusters:
        _s1,_s2,_s3,_s4,_s5=st.columns(5)
        _s1.metric("Oportunidades agrupadas",len(_status_clusters))
        _s2.metric("Prioridade máxima",len([r for r in _status_clusters if r.get("acao")=="🚀 PRIORIDADE MÁXIMA"]))
        _s3.metric("Investigar agora",len([r for r in _status_clusters if r.get("acao")=="🟢 INVESTIGAR AGORA"]))
        _s4.metric("Monitorar",len([r for r in _status_clusters if r.get("acao")=="🟡 MONITORAR + INVESTIGAR"]))
        _s5.metric("Revisar risco",len([r for r in _status_clusters if r.get("acao")=="🔴 REVISAR RISCO"]))
        if _run_at:
            st.caption(f"Última varredura registrada: {_run_at}")
        st.caption("Ranking comercial reconstruído localmente quando possível — sem nova chamada Nexscope.")
        _active_season=[r for r in _status_clusters if r.get("janela_sazonal") in ("🟢 Momento ideal","🟡 Atenção")]
        if _active_season:
            st.info(f"📅 Janela sazonal ativa: {len(_active_season)} oportunidades em Momento ideal ou Atenção.")

    elif _summary_auto:
        _s1,_s2,_s3,_s4,_s5=st.columns(5)
        _s1.metric("Produtos únicos",_summary_auto.get("unique_products",0))
        _s2.metric("Prioridade alta",_summary_auto.get("priority_high",0))
        _s3.metric("Investigar",_summary_auto.get("investigate",0))
        _s4.metric("Com histórico",_summary_auto.get("with_history",0))
        _s5.metric("Erros",_summary_auto.get("errors",0))
    else:
        st.caption("Nenhuma varredura automática executada nesta sessão.")

    st.caption("O modo manual abaixo fica apenas para uma investigação específica; o fluxo principal é o Garimpo Automático.")
    st.divider()

    st.subheader("🎯 Concorrentes Vulneráveis")
    st.caption("Analisa os produtos já coletados. Não consome créditos Nexscope.")

    _comp_products=st.session_state.get("auto_discovery_products") or []
    if not _comp_products:
        _ranked_old=st.session_state.get("auto_discovery_ranked") or []
        _comp_products=[r.get("_product") for r in _ranked_old if isinstance(r,dict) and r.get("_product")]

    if not _comp_products:
        st.info("Ainda não há produtos disponíveis para analisar concorrentes. Se o banco persistente estiver configurado, use “Recarregar banco salvo”.")
    else:
        _analysis=analyze_market(_comp_products)
        _rows_comp=_analysis.get("rows",[])
        _strategy=strategy_from_market(_analysis)

        if _rows_comp:
            _ctx=_analysis.get("context",{})
            c1,c2,c3,c4=st.columns(4)
            c1.metric("Concorrentes analisados",len(_rows_comp))
            c2.metric("Preço mediano",f"R$ {_ctx.get('median_price',0):.2f}")
            c3.metric("Avaliação mediana",f"{_ctx.get('median_rating',0):.2f}")
            c4.metric("Vendas medianas 30d",int(_ctx.get("median_sales",0)))

            st.markdown("#### 🧨 Onde existem brechas")
            _df_comp=pd.DataFrame(_rows_comp)
            _comp_cols=[
                "vulnerabilidade","status_concorrente","loja","produto","preco",
                "vendidos_30d","avaliacao","qtd_avaliacoes","brechas","forcas",
                "como_atacar","url"
            ]
            st.dataframe(
                _df_comp[_comp_cols],
                use_container_width=True,
                hide_index=True,
                column_config={"url":st.column_config.LinkColumn("Abrir anúncio")}
            )

            _top_comp=_analysis.get("top_vulnerable")
            if _top_comp:
                st.markdown("#### 🥊 Melhor brecha competitiva encontrada")
                st.success(
                    f"{_top_comp['status_concorrente']} | Loja: {_top_comp['loja'] or '—'} | "
                    f"Vulnerabilidade: {_top_comp['vulnerabilidade']} | "
                    f"Vendas 30d: {_top_comp['vendidos_30d']} | "
                    f"Brechas: {_top_comp['brechas']}"
                )

            st.markdown("#### 🧠 Como entrar contra esse mercado")
            st.write("**Leitura:**",_strategy["headline"])
            st.write("**Preço:**",_strategy["price_strategy"])
            st.write("**Prova social:**",_strategy["social_strategy"])
            st.write("**Oferta:**",_strategy["offer_strategy"])
            st.write("**Criativo/listagem:**",_strategy["creative_strategy"])


    st.divider()
    st.markdown("### 🧭 Fluxo Oficial do Garimpeiro")
    _has_products=bool(st.session_state.get("auto_discovery_products"))
    _has_clusters=bool(st.session_state.get("auto_discovery_clusters"))
    _ads_ready=bool(st.session_state.get("ads_brain_candidate")) or bool(st.session_state.get("ads_brain_ready"))
    _f1,_f2,_f3,_f4,_f5,_f6,_f7=st.columns(7)
    if _has_products:
        _f1.success("1. Descoberta")
    else:
        _f1.info("1. Descoberta")

    if _has_clusters:
        _f2.success("2. Oportunidade")
    else:
        _f2.info("2. Oportunidade")

    if _has_clusters:
        _f3.success("3. Sazonalidade")
    else:
        _f3.info("3. Sazonalidade")

    if _has_products:
        _f4.success("4. Aceleração")
    else:
        _f4.info("4. Aceleração")

    if _has_products:
        _f5.success("5. Concorrentes")
    else:
        _f5.info("5. Concorrentes")

    if _has_clusters:
        _f6.success("6. Investigação")
    else:
        _f6.info("6. Investigação")

    if _ads_ready:
        _f7.success("7. Cérebro Ads")
    else:
        _f7.info("7. Cérebro Ads")
    st.caption("Esta é a rota fixa do projeto. Ferramentas antigas/técnicas ficam recolhidas e não alteram o fluxo principal.")
    st.subheader("🔬 Investigação Aprofundada")
    st.caption("Consolida os dados já coletados. Não faz nova chamada Nexscope e não procura fornecedor nesta etapa.")

    _inv_clusters=st.session_state.get("auto_discovery_clusters") or []
    _inv_products=st.session_state.get("auto_discovery_products") or []

    if not _inv_clusters:
        st.info("Ainda não há oportunidades salvas para investigar. Quando houver coleta persistida, este módulo será preenchido automaticamente.")
    else:
        _inv_labels=[]
        _inv_map={}
        for _ix,_r in enumerate(_inv_clusters):
            _label=f"{_r.get('acao','')} | {_r.get('produto','')[:95]} | Score {_r.get('score_oportunidade_hoje',0)}"
            if _label in _inv_map:
                _label=f"{_label} #{_ix+1}"
            _inv_labels.append(_label)
            _inv_map[_label]=_r

        _inv_choice=st.selectbox(
            "Escolha a oportunidade para investigação completa",
            _inv_labels,
            key="deep_investigation_choice"
        )
        _inv_row=_inv_map[_inv_choice]
        _inv=investigate_existing_opportunity(_inv_row,_inv_products)

        _i1,_i2,_i3,_i4,_i5=st.columns(5)
        _i1.metric("Oportunidade hoje",_inv["score_oportunidade_hoje"])
        _i2.metric("Aceleração",_inv["score_aceleracao"])
        _i3.metric("Confiança",f"{_inv['confianca']} ({_inv['confianca_score']})")
        _i4.metric("Concorrentes similares",_inv["concorrentes_semelhantes"])
        _i5.metric("Vendas 30d",_inv["vendidos_30d"])

        if _inv["gate"]=="ads":
            st.success(_inv["veredito"])
        elif _inv["gate"]=="risco":
            st.error(_inv["veredito"])
        elif _inv["gate"]=="monitor":
            st.warning(_inv["veredito"])
        else:
            st.info(_inv["veredito"])

        st.markdown("#### 📌 Leitura consolidada")
        _detail_rows=[
            {"Sinal":"Produto","Leitura":_inv["produto"]},
            {"Sinal":"Preço atual","Leitura":f"R$ {_inv['preco']:.2f}" if _inv["preco"] else "—"},
            {"Sinal":"Avaliação","Leitura":f"{_inv['avaliacao']:.2f} ({_inv['qtd_avaliacoes']} avaliações)" if _inv["avaliacao"] else "—"},
            {"Sinal":"Sazonalidade","Leitura":f"{_inv['evento_sazonal']} | {_inv['janela_sazonal']} | pico em {_inv['dias_ate_pico']} dias" if _inv["dias_ate_pico"] is not None else f"{_inv['evento_sazonal']} | {_inv['janela_sazonal']}"},
            {"Sinal":"Risco de encalhe","Leitura":_inv["risco_encalhe"]},
            {"Sinal":"Histórico","Leitura":f"{_inv['snapshots']} snapshots"},
            {"Sinal":"Riscos especiais","Leitura":", ".join(_inv["riscos"]) if _inv["riscos"] else "Nenhum sinal especial nos dados atuais"},
        ]
        st.dataframe(pd.DataFrame(_detail_rows),use_container_width=True,hide_index=True)

        _c1,_c2=st.columns(2)
        with _c1:
            st.markdown("#### ✅ Pontos fortes")
            if _inv["pontos_fortes"]:
                for _x in _inv["pontos_fortes"]:
                    st.write("•",_x)
            else:
                st.write("• Nenhum ponto forte decisivo confirmado.")
        with _c2:
            st.markdown("#### ⚠️ Alertas")
            if _inv["alertas"]:
                for _x in _inv["alertas"]:
                    st.write("•",_x)
            else:
                st.write("• Nenhum alerta relevante nos campos atuais.")

        st.markdown("#### ⏱️ Por que agora?")
        for _x in _inv["por_que_agora"]:
            st.write("•",_x)

        _top_gap=_inv.get("top_brecha")
        if _top_gap:
            st.markdown("#### 🎯 Principal brecha entre concorrentes semelhantes")
            st.write(
                f"**{_top_gap.get('status_concorrente','')} — Vulnerabilidade {_top_gap.get('vulnerabilidade',0)}**  "
                f"| {_top_gap.get('produto','')}"
            )
            st.write("**Brechas:**",_top_gap.get("brechas",""))
            st.write("**Como atacar:**",_top_gap.get("como_atacar",""))

        if _inv["concorrentes"]:
            with st.expander(f"Ver {len(_inv['concorrentes'])} concorrentes semelhantes analisados"):
                _df_inv_comp=pd.DataFrame(_inv["concorrentes"])
                st.dataframe(
                    _df_inv_comp,
                    use_container_width=True,
                    hide_index=True,
                    column_config={"url":st.column_config.LinkColumn("Abrir anúncio")}
                )

        st.markdown("#### 🧾 Confiança da investigação")
        st.write(f"**{_inv['confianca']} ({_inv['confianca_score']}/100)** — {_inv['confianca_motivo']}")

        st.markdown("#### 🔒 O que ainda falta antes de colocar dinheiro")
        for _x in _inv["faltando"]:
            st.write("•",_x)

        if _inv["gate"]=="ads":
            if st.button("🧠 Preparar para o Cérebro de Anúncios",type="primary",key="send_to_ads_brain"):
                st.session_state["ads_brain_candidate"]=_inv
                st.success("Produto aprovado e separado para a próxima etapa: Cérebro de Anúncios.")

st.divider()
st.subheader("🧠 Cérebro de Anúncios")
st.caption("Transforma somente produtos aprovados pela Investigação em plano de teste. Não usa nova chamada Nexscope.")

_ads_candidate=st.session_state.get("ads_brain_candidate")
_ads_market=st.session_state.get("auto_discovery_products") or []

if not _ads_candidate:
    st.info("Aguardando um produto ser aprovado na Investigação Aprofundada.")
else:
    _ads_plan=build_ads_brain(_ads_candidate,_ads_market)
    st.session_state["ads_brain_plan"]=_ads_plan

    if _ads_plan["status_execucao"].startswith("🟢"):
        st.success(_ads_plan["status_execucao"])
    else:
        st.warning(_ads_plan["status_execucao"])

    _a1,_a2,_a3,_a4=st.columns(4)
    _a1.metric("Preço atual",f"R$ {_ads_plan['preco_atual']:.2f}" if _ads_plan["preco_atual"] else "—")
    _a2.metric("Preço entrada",f"R$ {_ads_plan['preco_entrada_sugerido']:.2f}" if _ads_plan["preco_entrada_sugerido"] else "—")
    _a3.metric("Orçamento teste/dia",f"R$ {_ads_plan['orcamento_diario_teste']:.2f}")
    _a4.metric("Teste inicial",f"{_ads_plan['dias_teste']} dias")

    st.markdown("#### 💵 Estratégia de preço e oferta")
    st.write("**Oferta:**",_ads_plan["tipo_oferta"])
    st.write("**Kit:**",_ads_plan["estrategia_kit"])
    if _ads_plan["preco_mediano_mercado"] > 0:
        st.write("**Preço mediano da amostra:**",f"R$ {_ads_plan['preco_mediano_mercado']:.2f}")
    st.caption("Preço sugerido é ponto de teste comercial, não decisão final de margem.")

    st.markdown("#### 🎯 Posicionamento e diferenciação")
    for _d in _ads_plan["diferenciais"]:
        st.write("•",_d)

    st.markdown("#### 🏷️ Título sugerido")
    st.code(_ads_plan["titulo_sugerido"],language=None)

    st.markdown("#### 🖼️ Plano de imagens")
    for _img in _ads_plan["plano_imagem"]:
        st.write("•",_img)

    st.markdown("#### 📣 Plano inicial de Ads")
    st.write(_ads_plan["regra_teste"])
    st.write(
        f"**Orçamento total aproximado do teste:** R$ {_ads_plan['orcamento_total_teste']:.2f}"
    )
    st.caption("Esse orçamento é uma referência de teste operacional. Não é previsão de lucro ou vendas.")

    _ac1,_ac2=st.columns(2)
    with _ac1:
        st.markdown("#### ✂️ Regras de corte")
        for _r in _ads_plan["regras_corte"]:
            st.write("•",_r)
    with _ac2:
        st.markdown("#### 📈 Regras de escala")
        for _r in _ads_plan["regras_escala"]:
            st.write("•",_r)

    if _ads_plan["bloqueios"]:
        st.markdown("#### 🚧 Bloqueios antes de escalar")
        for _b in _ads_plan["bloqueios"]:
            st.write("•",_b)

    st.markdown("#### 🔒 Financeiro ainda pendente")
    st.caption("O Garimpeiro não vai fingir margem sem custo real.")
    for _f in _ads_plan["financeiro_pendente"]:
        st.write("•",_f)

    st.session_state["ads_brain_ready"]=True

st.divider()
st.subheader("📊 Previsão Realista")
st.caption("Separa dado observado de cenário. Não transforma falta de histórico em falsa precisão.")

_forecast_candidate=st.session_state.get("ads_brain_candidate")
if not _forecast_candidate:
    st.info("Aguardando produto aprovado pela Investigação para gerar cenários.")
else:
    _forecast=build_realistic_forecast(_forecast_candidate)
    st.session_state["forecast_result"]=_forecast

    if _forecast["nivel"] >= 2:
        st.success(f"{_forecast['conclusao']} | Confiança: {_forecast['confianca']}")
    elif _forecast["nivel"] == 1:
        st.warning(f"{_forecast['conclusao']} | Confiança: {_forecast['confianca']}")
    else:
        st.info(f"{_forecast['conclusao']} | Confiança: {_forecast['confianca']}")

    st.markdown("#### 🔎 Dados observados")
    _obs=_forecast["observado"]
    _fo1,_fo2,_fo3,_fo4=st.columns(4)
    _fo1.metric("Vendas 30d",_obs["vendas_30d_atual"])
    _fo2.metric("Preço",f"R$ {_obs['preco_atual']:.2f}" if _obs["preco_atual"] else "—")
    _fo3.metric("Snapshots",_obs["snapshots"])
    _fo4.metric("Aceleração",_obs["score_aceleracao"])

    st.write("**Sazonalidade:**",_obs["sazonalidade"])

    if _forecast["cenarios"]:
        st.markdown("#### 📈 Cenários de 30 dias")
        _df_forecast=pd.DataFrame(_forecast["cenarios"])
        st.dataframe(_df_forecast,use_container_width=True,hide_index=True)
        st.caption("Esses valores são cenários derivados do nível atual de vendas; não são garantia de venda futura.")

    if _forecast["notas"]:
        st.markdown("#### ⚠️ Limitações")
        for _n in _forecast["notas"]:
            st.write("•",_n)

    if _forecast["proximo_para_melhorar"]:
        st.markdown("#### 🧪 O que aumenta a confiança da previsão")
        for _n in _forecast["proximo_para_melhorar"]:
            st.write("•",_n)
    st.divider()
    with st.expander("⚙️ Ferramentas técnicas / módulos antigos", expanded=False):
        st.caption(
            "Mantidos para diagnóstico e operações específicas. "
            "Eles não fazem parte da rota principal e não foram apagados."
        )
        st.divider()
        st.subheader("🛒 Shopee Real — Nexscope")
        st.caption("Busca direta de produtos reais da Shopee Brasil. A Brave continua apenas como apoio para fornecedores e contexto.")

        if not nexscope_enabled():
            st.error("NEXSCOPE_API_KEY não encontrada nos Secrets do Streamlit.")
        else:
            ns1,ns2,ns3=st.columns([3,1,1])
            ns_keyword=ns1.text_input("O que procurar na Shopee?",placeholder="Ex.: suporte celular carro",key="ns_keyword")
            ns_page_size=ns2.selectbox("Resultados",[10,20,30,50],index=1,key="ns_page_size")
            ns_page=ns3.number_input("Página",min_value=1,value=1,step=1,key="ns_page")

            ns4,ns5,ns6=st.columns([2,1,1])
            ns_order_label=ns4.selectbox("Ordenar por",list(ORDER_LABELS.keys()),index=0,key="ns_order")
            ns_sold_min=ns5.number_input("Vendas mín. 30d",min_value=0,value=0,step=10,key="ns_sold_min")
            ns_rating_min=ns6.number_input("Avaliação mín.",min_value=0.0,max_value=5.0,value=0.0,step=0.1,key="ns_rating_min")

            ns7,ns8,ns9=st.columns([1,1,1])
            ns_price_min=ns7.number_input("Preço mín. (R$)",min_value=0.0,value=0.0,step=5.0,key="ns_price_min")
            ns_price_max=ns8.number_input("Preço máx. (R$)",min_value=0.0,value=0.0,step=5.0,key="ns_price_max")
            ns_local_only=ns9.checkbox("Somente vendedores locais",value=False,key="ns_local_only")

            st.caption("A Nexscope cobra créditos por chamada; confira o custo vigente no painel da sua conta.")

            if st.button("🛒 Buscar produtos reais na Shopee",type="primary",key="ns_run"):
                if not ns_keyword.strip():
                    st.warning("Digite um produto ou termo para buscar.")
                else:
                    with st.spinner("Consultando Shopee Brasil pela Nexscope..."):
                        ns_result=search_products(
                            keyword=ns_keyword,
                            station="BR",
                            page=int(ns_page),
                            page_size=int(ns_page_size),
                            keyword_type=2,
                            order_by=ORDER_LABELS[ns_order_label],
                            order_by_type="DESC",
                            price_min=ns_price_min if ns_price_min>0 else None,
                            price_max=ns_price_max if ns_price_max>0 else None,
                            sold_min=ns_sold_min if ns_sold_min>0 else None,
                            rating_min=ns_rating_min if ns_rating_min>0 else None,
                            local_only=ns_local_only,
                        )
                        st.session_state["nexscope_result"]=ns_result
                        if ns_result.get("ok"):
                            st.session_state["structured_shopee_rows"]=as_structured_shopee_rows(ns_result)
                            try:
                                save_snapshot(ns_result.get("products", []))
                            except Exception as _scale_err:
                                st.session_state["scale_snapshot_error"] = str(_scale_err)
                            if persistence_configured():
                                try:
                                    _mps=persist_products(ns_result.get("products", []),source="manual_nexscope",keyword=ns_keyword)
                                    if not _mps.get("ok"):
                                        st.session_state["persistence_error"]=_mps.get("error")
                                except Exception as _mperr:
                                    st.session_state["persistence_error"]=str(_mperr)

            ns_result=st.session_state.get("nexscope_result")
            if ns_result:
                if not ns_result.get("ok"):
                    st.error("Falha na busca Shopee: "+str(ns_result.get("error","Erro desconhecido")))
                else:
                    summary=ns_result.get("summary",{})
                    a,b,c,d,e=st.columns(5)
                    a.metric("Produtos retornados",len(ns_result.get("products",[])))
                    b.metric("Resultados disponíveis",summary.get("total_size") or "—")
                    mp=summary.get("median_price")
                    c.metric("Preço mediano",f"R$ {mp:.2f}" if isinstance(mp,(int,float)) else "Sem dado")
                    d.metric("Vendas medianas 30d",summary.get("median_sold_30d",0))
                    mr=summary.get("median_rating")
                    e.metric("Avaliação mediana",f"{mr:.2f}" if isinstance(mr,(int,float)) else "Sem dado")

                    ns_products=ns_result.get("products",[])
                    if ns_products:
                        ns_df=pd.DataFrame(ns_products)
                        ns_cols=[
                            "score_shopee","classificacao","produto","preco","vendidos_30d",
                            "vendidos_historicos","faturamento_30d","avaliacao","qtd_avaliacoes",
                            "estoque","loja","local_loja","oficial","preferida","cross_border","url"
                        ]
                        for col in ns_cols:
                            if col not in ns_df.columns:
                                ns_df[col]=""
                        st.dataframe(
                            ns_df[ns_cols],
                            use_container_width=True,
                            hide_index=True,
                            column_config={"url":st.column_config.LinkColumn("Abrir na Shopee")}
                        )

                        ns_names=[p.get("produto","") for p in ns_products if p.get("produto")]
                        ns_selected=st.selectbox("Produto real da Shopee para investigar",ns_names,key="ns_selected")
                        if st.button("➡️ Enviar produto para investigação",key="ns_send"):
                            chosen=next((p for p in ns_products if p.get("produto")==ns_selected),None)
                            if chosen:
                                row={
                                    "score_radar":chosen.get("score_shopee",0),
                                    "classificacao":chosen.get("classificacao",""),
                                    "oportunidade":chosen.get("produto",""),
                                    "evidencia_shopee":"✅ Sim",
                                    "fontes_confirmando":1,
                                    "confirmacoes_secundarias":0,
                                    "fornecedores_sinal":0,
                                    "fontes":"Shopee via Nexscope",
                                    "por_que_agora":chosen.get("por_que",""),
                                    "descricao":f"Preço R$ {chosen.get('preco')} | Vendidos 30d {chosen.get('vendidos_30d')} | Avaliação {chosen.get('avaliacao')}",
                                    "url":chosen.get("url",""),
                                }
                                current=st.session_state.get("radar_result") or {}
                                rows=current.get("rows",[]) if isinstance(current,dict) else []
                                rows=[r for r in rows if r.get("oportunidade")!=row["oportunidade"]]
                                rows.insert(0,row)
                                st.session_state["radar_result"]={
                                    "enabled":True,
                                    "message":"Produto real da Shopee enviado para investigação.",
                                    "queries_used":0,
                                    "results_found":len(rows),
                                    "rows":rows,
                                    "suppliers":current.get("suppliers",[]) if isinstance(current,dict) else [],
                                }
                                st.success("Produto enviado. Continue no Investigador Automático abaixo.")

        st.divider()
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

                    inv = _merge_nexscope_into_investigation(selected_product, inv)
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

                    ns_ev=inv.get("nexscope_shopee") or {}
                    if ns_ev:
                        st.success("✅ Produto exato confirmado na Shopee via Nexscope")
                        n1,n2,n3,n4=st.columns(4)
                        n1.metric("Vendas 30d", ns_ev.get("vendidos_30d",0))
                        n2.metric("Avaliação", f"{ns_ev.get('avaliacao'):.2f}" if isinstance(ns_ev.get("avaliacao"),(int,float)) else "Sem dado")
                        n3.metric("Qtd. avaliações", ns_ev.get("qtd_avaliacoes",0))
                        n4.metric("Loja", ns_ev.get("loja") or "Sem dado")
                        if ns_ev.get("url"):
                            st.link_button("🔗 Abrir produto na Shopee", ns_ev.get("url"))

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


        st.subheader("🚀 V13 — Radar de Escala")
        st.caption("Separa produto que já vende muito de produto que está realmente acelerando.")
        st.caption("Para tendência real, compare coletas separadas por algumas horas ou dias; duas buscas seguidas não significam aceleração.")

        _ns_v13 = st.session_state.get("nexscope_result") or {}
        _v13_products = _ns_v13.get("products",[]) if isinstance(_ns_v13,dict) else []

        if not _v13_products:
            st.info("Faça primeiro uma busca em Shopee Real — Nexscope. Cada busca válida passa a ser registrada automaticamente como histórico.")
        else:
            _names_v13=[p.get("produto","") for p in _v13_products if p.get("produto")]
            _selected_v13=st.selectbox("Produto para analisar escala",_names_v13,key="v13_selected")
            _prod_v13=next((p for p in _v13_products if p.get("produto")==_selected_v13),None)

            if _prod_v13:
                _sig=scale_signal(_prod_v13)
                _vulns=competitor_vulnerability(_v13_products)
                _forecast=forecast_from_signal(_prod_v13,_sig)
                _alerts=build_alerts(_sig,_vulns)

                v1,v2,v3,v4,v5=st.columns(5)
                v1.metric("Score de escala",_sig.get("score",0))
                v2.metric("Momento",_sig.get("status","—"))
                v3.metric("Snapshots",_sig.get("history_points",0))
                v4.metric("Δ vendas 30d",int(_sig.get("sold30_delta",0)))
                v5.metric("Δ avaliações",int(_sig.get("ratings_delta",0)))

                st.write("**Leitura:**",_sig.get("reason","—"))
                if _sig.get("history_points",0)<2:
                    st.warning("Ainda não há histórico suficiente para afirmar aceleração. Repita a mesma busca mais tarde; o Garimpeiro guardará um novo snapshot.")

                st.markdown("#### 🎯 Concorrentes vulneráveis")
                if _vulns:
                    _dfv=pd.DataFrame(_vulns[:10])
                    st.dataframe(
                        _dfv[["vulnerabilidade","loja","produto","preco","vendidos_30d","avaliacao","qtd_avaliacoes","brechas","url"]],
                        use_container_width=True,hide_index=True,
                        column_config={"url":st.column_config.LinkColumn("Abrir")}
                    )

                st.markdown("#### 🔮 Melhor cenário e previsão")
                f1,f2,f3=st.columns(3)
                f1.metric("Conservador",_forecast.get("conservador",0))
                f2.metric("Base",_forecast.get("base",0))
                f3.metric("Agressivo",_forecast.get("agressivo",0))
                st.caption("Projeções heurísticas a partir do sinal observado; não são garantia de vendas.")

                st.markdown("#### 🚨 Alertas")
                for _a in _alerts:
                    st.write(_a)

                st.markdown("#### 🧾 Auditoria")
                st.json({
                    "fonte":"Shopee via Nexscope",
                    "produto":_prod_v13.get("produto"),
                    "pid":_prod_v13.get("pid"),
                    "preco":_prod_v13.get("preco"),
                    "vendidos_30d":_prod_v13.get("vendidos_30d"),
                    "vendidos_historicos":_prod_v13.get("vendidos_historicos"),
                    "avaliacao":_prod_v13.get("avaliacao"),
                    "avaliacoes":_prod_v13.get("qtd_avaliacoes"),
                    "score_escala":_sig.get("score"),
                    "status":_sig.get("status"),
                    "snapshots":_sig.get("history_points"),
                })

                _top=_vulns[0] if _vulns else {}
                _next="Investigar estratégia de anúncio" if _sig.get("score",0)>=70 else "Continuar coletando histórico"
                st.markdown("#### 📌 Resumo executivo")
                st.success(
                    f"Produto: {_prod_v13.get('produto','')} | Momento: {_sig.get('status','—')} | "
                    f"Score: {_sig.get('score',0)} | Principal brecha: {_top.get('brechas','sem brecha clara')} | "
                    f"Próxima ação: {_next}"
                )

        st.divider()
        st.subheader("🌏 Fornecedores 1688 — Nexscope")
        st.caption("Sourcing estruturado no 1688. O preço abaixo é preço de atacado na moeda informada pela fonte — ainda NÃO é custo final em reais.")

        _candidate_1688 = None
        if "selected_product" in locals():
            _candidate_1688 = selected_product
        elif "candidate_names" in locals() and candidate_names:
            _candidate_1688 = candidate_names[0]

        if not _candidate_1688:
            st.info("Envie primeiro um produto real da Shopee para investigação.")
        else:
            st.write("**Produto de referência:**", _candidate_1688)

            default_zh = suggest_chinese_keyword(_candidate_1688)
            z1,z2,z3 = st.columns([3,1,1])
            keyword_zh = z1.text_input(
                "Termo para buscar no 1688 (chinês simplificado)",
                value=default_zh,
                key="supplier_1688_keyword",
                help="O sistema cria uma sugestão comercial. Você pode ajustar antes de consumir créditos."
            )
            page_size_1688 = z2.selectbox("Resultados 1688",[10,20,30,50],index=1,key="supplier_1688_size")
            search_type_1688 = z3.selectbox("Correspondência",["Ampla","Exata"],index=0,key="supplier_1688_match")

            z4,z5,z6 = st.columns([2,1,1])
            sort_label_1688 = z4.selectbox("Ordenar por",list(SORT_1688_LABELS.keys()),index=0,key="supplier_1688_sort")
            price_min_1688 = z5.number_input("Preço mín. atacado",min_value=0.0,value=0.0,step=1.0,key="supplier_1688_pmin")
            price_max_1688 = z6.number_input("Preço máx. atacado",min_value=0.0,value=0.0,step=1.0,key="supplier_1688_pmax")

            st.caption("Cada busca 1688 consome créditos Nexscope. A documentação atual informa 12 créditos por chamada.")

            if st.button("🌏 Buscar fornecedores reais no 1688", key="run_1688"):
                if not keyword_zh.strip():
                    st.warning("O termo 1688 está vazio.")
                else:
                    with st.spinner("Consultando produtos e fornecedores no 1688..."):
                        r1688 = search_1688(
                            keyword_zh=keyword_zh,
                            page_index=1,
                            page_size=int(page_size_1688),
                            search_type=1 if search_type_1688=="Ampla" else 3,
                            sort_field=SORT_1688_LABELS[sort_label_1688],
                            sort_type="asc" if sort_label_1688 in ("Menor preço","Menor preço dropshipping") else "desc",
                            begin_price=price_min_1688 if price_min_1688>0 else None,
                            end_price=price_max_1688 if price_max_1688>0 else None,
                            cycle="30",
                        )
                        st.session_state["supplier_1688_result"] = r1688
                        st.session_state["supplier_1688_product"] = _candidate_1688

            r1688 = st.session_state.get("supplier_1688_result")
            if r1688 and st.session_state.get("supplier_1688_product")==_candidate_1688:
                if not r1688.get("ok"):
                    st.error("Falha na busca 1688: "+str(r1688.get("error","Erro desconhecido")))
                else:
                    sm = r1688.get("summary",{})
                    x1,x2,x3,x4,x5 = st.columns(5)
                    x1.metric("Resultados", sm.get("returned",0))
                    x2.metric("Compatíveis", sm.get("compatible",0))
                    x3.metric("Possíveis", sm.get("possible",0))
                    med = sm.get("median_wholesale_cny")
                    low = sm.get("min_wholesale_cny")
                    x4.metric("Menor atacado", f"{low:.2f} CNY" if isinstance(low,(int,float)) else "Sem dado")
                    x5.metric("Mediana atacado", f"{med:.2f} CNY" if isinstance(med,(int,float)) else "Sem dado")

                    rows1688 = r1688.get("products",[])
                    if rows1688:
                        df1688 = pd.DataFrame(rows1688)
                        cols1688 = [
                            "status","compatibilidade","titulo_1688","preco_atacado","preco_dropship",
                            "faixa_preco","moq","unidade","moeda","pedidos","unidades_vendidas",
                            "empresa","prazo_entrega","link"
                        ]
                        for c in cols1688:
                            if c not in df1688.columns:
                                df1688[c] = ""
                        st.dataframe(
                            df1688[cols1688],
                            use_container_width=True,
                            hide_index=True,
                            column_config={"link":st.column_config.LinkColumn("Abrir no 1688")}
                        )

                        best_names = [
                            f"{p.get('empresa') or 'Fornecedor'} | {p.get('titulo_1688','')[:70]}"
                            for p in rows1688 if p.get("compatibilidade",0) >= 45
                        ]
                        if best_names:
                            chosen_label = st.selectbox("Fornecedor 1688 para pré-selecionar", best_names, key="chosen_1688")
                            if st.button("✅ Guardar como candidato de fornecedor", key="save_1688_candidate"):
                                for p in rows1688:
                                    label = f"{p.get('empresa') or 'Fornecedor'} | {p.get('titulo_1688','')[:70]}"
                                    if label == chosen_label:
                                        st.session_state["supplier_1688_candidate"] = {
                                            "produto_shopee": _candidate_1688,
                                            **p
                                        }
                                        # Seed landed-cost fields immediately so Streamlit widgets
                                        # receive the selected supplier data on the next rerun.
                                        st.session_state["landed_wholesale"] = float(p.get("preco_atacado") or 0.0)
                                        st.session_state["landed_qty"] = max(int(p.get("moq") or 1), 1)
                                        st.session_state["landed_currency"] = p.get("moeda") or "CNY"
                                        st.session_state["landed_supplier_name"] = p.get("empresa") or "Fornecedor 1688"
                                        st.session_state["landed_product_name"] = p.get("titulo_1688") or ""
                                        st.success("Fornecedor 1688 guardado. Preço e MOQ enviados automaticamente para o Custo Posto no Brasil.")
                                        st.rerun()
                                        break

                    saved1688 = st.session_state.get("supplier_1688_candidate")
                    if saved1688 and saved1688.get("produto_shopee")==_candidate_1688:
                        st.info(
                            "Candidato salvo: "
                            + str(saved1688.get("empresa") or "Fornecedor")
                            + " | Atacado: "
                            + (f"{saved1688.get('preco_atacado'):.2f} {saved1688.get('moeda','CNY')}" if isinstance(saved1688.get("preco_atacado"),(int,float)) else "Sem preço")
                            + " | MOQ: "
                            + str(saved1688.get("moq") or "Sem dado")
                        )

                    st.warning("Não use o preço 1688 diretamente como custo em R$. Ainda faltam câmbio, frete internacional, impostos, despacho e possíveis taxas.")

        st.divider()

        st.subheader("🇧🇷 Custo Posto no Brasil")
        st.caption("Calcula o custo unitário realista do fornecedor 1688 até chegar ao Brasil. Nenhum imposto, frete ou câmbio é inventado: você informa os valores usados no cálculo.")

        saved1688 = st.session_state.get("supplier_1688_candidate")
        if not saved1688:
            st.info("Primeiro escolha um fornecedor 1688 e clique em “Guardar como candidato de fornecedor”.")
        else:
            st.write("**Fornecedor candidato:**", saved1688.get("empresa") or "Fornecedor 1688")
            st.write("**Produto 1688:**", saved1688.get("titulo_1688") or "—")

            wh = saved1688.get("preco_atacado")
            moq = int(saved1688.get("moq") or 1)
            currency = saved1688.get("moeda") or "CNY"

            s1,s2,s3,s4 = st.columns(4)
            s1.metric("Fornecedor", saved1688.get("empresa") or "Fornecedor 1688")
            s2.metric("Preço 1688", f"{float(wh):.2f} {currency}" if isinstance(wh,(int,float)) else "Sem dado")
            s3.metric("MOQ", max(moq,1))
            s4.metric("Compatibilidade", f"{saved1688.get('compatibilidade',0)}%")

            c1,c2,c3 = st.columns(3)
            if "landed_wholesale" not in st.session_state:
                st.session_state["landed_wholesale"] = float(wh or 0)
            if "landed_qty" not in st.session_state:
                st.session_state["landed_qty"] = max(moq, 1)

            # Keep fields synchronized with a newly-selected supplier.
            current_supplier_key = f"{saved1688.get('offer_id','')}|{saved1688.get('empresa','')}|{saved1688.get('preco_atacado','')}|{saved1688.get('moq','')}"
            if st.session_state.get("_landed_supplier_key") != current_supplier_key:
                st.session_state["_landed_supplier_key"] = current_supplier_key
                st.session_state["landed_wholesale"] = float(wh or 0)
                st.session_state["landed_qty"] = max(moq, 1)

            wholesale_cny = c1.number_input(
                f"Preço unitário fornecedor ({currency})",
                min_value=0.0,
                step=0.10,
                key="landed_wholesale"
            )
            qty = c2.number_input(
                "Quantidade do lote",
                min_value=1,
                step=1,
                key="landed_qty"
            )
            fx = c3.number_input(
                "Câmbio CNY → BRL usado no cálculo",
                min_value=0.0,
                value=0.0,
                step=0.01,
                key="landed_fx",
                help="Digite a cotação que você quer usar. O Garimpeiro não inventa uma cotação."
            )

            c4,c5,c6 = st.columns(3)
            intl = c4.number_input("Frete internacional total (R$)",min_value=0.0,value=0.0,step=10.0,key="landed_intl")
            taxes = c5.number_input("Impostos de importação total (R$)",min_value=0.0,value=0.0,step=10.0,key="landed_taxes")
            customs = c6.number_input("Despacho/taxas aduaneiras (R$)",min_value=0.0,value=0.0,step=10.0,key="landed_customs")

            c7,c8,c9 = st.columns(3)
            domestic = c7.number_input("Frete no Brasil total (R$)",min_value=0.0,value=0.0,step=10.0,key="landed_domestic")
            packaging = c8.number_input("Embalagem por unidade (R$)",min_value=0.0,value=0.0,step=0.10,key="landed_pack")
            other_fixed = c9.number_input("Outros custos fixos do lote (R$)",min_value=0.0,value=0.0,step=10.0,key="landed_other_fixed")

            other_unit = st.number_input("Outros custos por unidade (R$)",min_value=0.0,value=0.0,step=0.10,key="landed_other_unit")

            if st.button("🧮 Calcular custo posto no Brasil",key="calc_landed"):
                if fx <= 0:
                    st.warning("Informe o câmbio CNY → BRL antes de calcular.")
                else:
                    lc = landed_cost_brazil(
                        wholesale_cny=wholesale_cny,
                        qty=qty,
                        fx_cny_brl=fx,
                        intl_freight_brl=intl,
                        import_taxes_brl=taxes,
                        customs_brl=customs,
                        domestic_freight_brl=domestic,
                        packaging_brl_per_unit=packaging,
                        other_fixed_brl=other_fixed,
                        other_unit_brl=other_unit,
                    )
                    st.session_state["landed_cost_result"] = lc

            lc = st.session_state.get("landed_cost_result")
            if lc and lc.get("ok"):
                l1,l2,l3,l4 = st.columns(4)
                l1.metric("Produto convertido",f"R$ {lc['product_total_brl']:.2f}")
                l2.metric("Custos fixos lote",f"R$ {lc['fixed_total_brl']:.2f}")
                l3.metric("Custo total posto",f"R$ {lc['landed_total_brl']:.2f}")
                l4.metric("Custo posto / unidade",f"R$ {lc['landed_unit_brl']:.2f}")

                st.markdown("#### 💰 Viabilidade na Shopee")
                ns_prod = _get_nexscope_product_by_name(saved1688.get("produto_shopee"))
                sale_default = float((ns_prod or {}).get("preco") or 0)

                p1,p2,p3,p4 = st.columns(4)
                sale_price = p1.number_input("Preço de venda Shopee (R$)",min_value=0.0,value=sale_default,step=0.10,key="profit_sale")
                fee_pct = p2.number_input("Taxa marketplace (%)",min_value=0.0,value=0.0,step=0.1,key="profit_fee")
                fixed_fee = p3.number_input("Taxa fixa por pedido (R$)",min_value=0.0,value=0.0,step=0.10,key="profit_fixed")
                tax_pct = p4.number_input("Tributos sobre venda (%)",min_value=0.0,value=0.0,step=0.1,key="profit_tax")

                p5,p6,p7 = st.columns(3)
                ads_pct = p5.number_input("Ads (% da venda)",min_value=0.0,value=0.0,step=0.5,key="profit_ads")
                returns_pct = p6.number_input("Perdas/devoluções (%)",min_value=0.0,value=0.0,step=0.5,key="profit_returns")
                target_margin = p7.number_input("Margem-alvo (%)",min_value=0.0,value=20.0,step=1.0,key="profit_target")

                if st.button("📊 Calcular margem e Ads",key="calc_profit"):
                    pr = profitability(
                        sale_price_brl=sale_price,
                        landed_unit_brl=lc["landed_unit_brl"],
                        marketplace_fee_pct=fee_pct,
                        fixed_fee_brl=fixed_fee,
                        tax_pct=tax_pct,
                        ads_pct=ads_pct,
                        returns_pct=returns_pct,
                        target_margin_pct=target_margin,
                    )
                    st.session_state["profitability_result"] = pr

                pr = st.session_state.get("profitability_result")
                if pr and pr.get("ok"):
                    r1,r2,r3,r4 = st.columns(4)
                    r1.metric("Lucro/unidade",f"R$ {pr['profit_brl']:.2f}")
                    r2.metric("Margem líquida",f"{pr['margin_pct']:.2f}%")
                    r3.metric("CAC break-even",f"R$ {pr['cac_break_even_brl']:.2f}")
                    r4.metric("CAC para margem-alvo",f"R$ {pr['cac_target_brl']:.2f}")

                    rr1,rr2 = st.columns(2)
                    rr1.metric("ROAS break-even",f"{pr['roas_break_even']:.2f}" if pr['roas_break_even'] else "—")
                    rr2.metric("ROAS para margem-alvo",f"{pr['roas_target']:.2f}" if pr['roas_target'] else "—")

                    st.subheader(pr["decision"])
                    st.caption("A decisão usa apenas os valores preenchidos nesta simulação. Antes de comprar estoque, confirme câmbio, frete, impostos, taxas e condições do fornecedor.")

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
