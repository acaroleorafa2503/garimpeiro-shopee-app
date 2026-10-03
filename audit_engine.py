from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).isoformat()

def _safe(v, default=""):
    return default if v is None else v

def build_audit_snapshot(state):
    """
    Gera uma trilha auditável do estado atual do Garimpeiro sem fazer chamadas externas.
    """
    events=[]

    products = state.get("products") or []
    clusters = state.get("clusters") or []
    investigation = state.get("investigation") or {}
    ads_plan = state.get("ads_plan") or {}
    forecast = state.get("forecast") or {}
    alerts = state.get("alerts") or {}
    persistence_active = bool(state.get("persistence_active"))
    credit_blocked = bool(state.get("credit_blocked"))

    if persistence_active:
        events.append({
            "timestamp":_now(),
            "etapa":"Persistência",
            "decisao":"Banco ativo",
            "assunto":"Supabase",
            "motivo":"Persistência externa configurada para preservar coletas.",
            "confianca":"Alta",
            "fonte":"Supabase / Streamlit Secrets",
        })

    if products:
        events.append({
            "timestamp":_now(),
            "etapa":"Descoberta",
            "decisao":"Dados disponíveis",
            "assunto":f"{len(products)} produtos",
            "motivo":"Há produtos coletados disponíveis para análise.",
            "confianca":"Alta",
            "fonte":"Nexscope + banco persistente",
        })
    else:
        events.append({
            "timestamp":_now(),
            "etapa":"Descoberta",
            "decisao":"Aguardando coleta",
            "assunto":"Sem produtos disponíveis",
            "motivo":"Nenhuma coleta persistida está carregada nesta sessão.",
            "confianca":"Alta",
            "fonte":"Estado do sistema",
        })

    if credit_blocked:
        events.append({
            "timestamp":_now(),
            "etapa":"Descoberta",
            "decisao":"Bloqueado",
            "assunto":"Nexscope",
            "motivo":"Créditos insuficientes detectados; novas chamadas foram interrompidas.",
            "confianca":"Alta",
            "fonte":"Resposta Nexscope",
        })

    if clusters:
        top=max(clusters,key=lambda r:int(r.get("score_oportunidade_hoje") or 0))
        events.append({
            "timestamp":_now(),
            "etapa":"Oportunidade",
            "decisao":str(top.get("acao") or "Ranking disponível"),
            "assunto":str(top.get("produto") or ""),
            "motivo":str(top.get("por_que") or "Produto melhor posicionado no ranking atual."),
            "confianca":"Média/Alta conforme dados disponíveis",
            "fonte":"Opportunity Engine + Sazonalidade",
        })

    if investigation:
        events.append({
            "timestamp":_now(),
            "etapa":"Investigação",
            "decisao":str(investigation.get("veredito") or investigation.get("gate") or "Resultado disponível"),
            "assunto":str(investigation.get("produto") or ""),
            "motivo":"; ".join(investigation.get("por_que_agora") or []) or "Investigação consolidada disponível.",
            "confianca":str(investigation.get("confianca") or investigation.get("confianca_score") or "—"),
            "fonte":"Investigação Aprofundada",
        })

    if ads_plan:
        events.append({
            "timestamp":_now(),
            "etapa":"Cérebro de Anúncios",
            "decisao":str(ads_plan.get("status_execucao") or "Plano disponível"),
            "assunto":str(ads_plan.get("produto") or ""),
            "motivo":"Plano de teste gerado com regras de preço, oferta, corte e escala.",
            "confianca":"Condicionada à investigação e ao financeiro real",
            "fonte":"Ads Brain Engine",
        })

    if forecast:
        events.append({
            "timestamp":_now(),
            "etapa":"Previsão",
            "decisao":str(forecast.get("conclusao") or "Cenário disponível"),
            "assunto":"Cenários de 30 dias",
            "motivo":"Cenários separados de dados observados; confiança depende do histórico temporal.",
            "confianca":str(forecast.get("confianca") or "—"),
            "fonte":"Forecast Engine",
        })

    if alerts:
        summary=alerts.get("summary") or {}
        events.append({
            "timestamp":_now(),
            "etapa":"Alertas",
            "decisao":"Alertas avaliados",
            "assunto":f"{summary.get('total',0)} alertas",
            "motivo":f"{summary.get('alta',0)} alta prioridade; {summary.get('media',0)} média; {summary.get('baixa',0)} baixa.",
            "confianca":"Alta para regras determinísticas",
            "fonte":"Alerts Engine",
        })

    return events

def merge_legacy_decisions(audit_events, legacy_rows):
    out=list(audit_events or [])
    for row in legacy_rows or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "timestamp":row.get("created_at") or row.get("timestamp") or "",
            "etapa":row.get("stage") or row.get("module") or "Log legado",
            "decisao":row.get("decision") or row.get("action") or row.get("status") or "",
            "assunto":row.get("product") or row.get("subject") or row.get("entity") or "",
            "motivo":row.get("reason") or row.get("notes") or row.get("message") or "",
            "confianca":row.get("confidence") or "",
            "fonte":row.get("source") or "Decision log legado",
        })
    return out
