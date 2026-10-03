def _int(v, default=0):
    try:
        if v in (None, ""):
            return default
        return int(float(v))
    except Exception:
        return default

def _num(v, default=0.0):
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default

def build_executive_summary(products=None, clusters=None, investigation=None, ads_plan=None, forecast=None, alerts=None):
    products = products or []
    clusters = clusters or []
    investigation = investigation or {}
    ads_plan = ads_plan or {}
    forecast = forecast or {}
    alerts = alerts or {}

    top = None
    if clusters:
        top = sorted(
            clusters,
            key=lambda r:(
                _int(r.get("score_oportunidade_hoje")),
                _int(r.get("score_aceleracao")),
                _int(r.get("vendidos_30d")),
            ),
            reverse=True
        )[0]

    product_name = (
        investigation.get("produto")
        or (top.get("produto") if top else "")
        or ads_plan.get("produto")
        or ""
    )

    opportunity = (
        investigation.get("score_oportunidade_hoje")
        or (top.get("score_oportunidade_hoje") if top else 0)
        or 0
    )
    acceleration = (
        investigation.get("score_aceleracao")
        or (top.get("score_aceleracao") if top else 0)
        or 0
    )
    season_event = (
        investigation.get("evento_sazonal")
        or (top.get("evento_sazonal") if top else "")
        or "Perene / sem evento claro"
    )
    season_window = (
        investigation.get("janela_sazonal")
        or (top.get("janela_sazonal") if top else "")
        or "🟢 Perene"
    )
    confidence = (
        investigation.get("confianca")
        or forecast.get("confianca")
        or "—"
    )

    reason = ""
    if investigation.get("por_que_agora"):
        reason = "; ".join(investigation.get("por_que_agora") or [])
    elif top:
        reason = str(top.get("por_que") or "")
    if not reason:
        reason = "Ainda não há evidência suficiente para explicar uma prioridade."

    gap = ""
    top_gap = investigation.get("top_brecha")
    if top_gap:
        gap = str(top_gap.get("brechas") or "")
    elif top:
        gap = str(top.get("por_que") or "")

    risk = ""
    risks = investigation.get("riscos") or []
    if risks:
        risk = ", ".join(str(x) for x in risks)
    elif top:
        risk = str(top.get("risco") or "Baixo")
    else:
        risk = "Sem dados"

    next_action = "Aguardar nova coleta persistida."
    if investigation:
        gate = investigation.get("gate")
        if gate == "ads":
            next_action = "Executar o plano inicial do Cérebro de Anúncios."
        elif gate == "monitor":
            next_action = "Monitorar novo snapshot antes de escalar decisão."
        elif gate == "risco":
            next_action = "Revisar risco antes de qualquer avanço."
        elif gate == "low":
            next_action = "Não priorizar agora."
    elif top:
        action = str(top.get("acao") or "")
        if "INVESTIGAR" in action.upper():
            next_action = "Levar o produto para Investigação Aprofundada."
        elif "PRIORIDADE" in action.upper():
            next_action = "Investigar imediatamente e validar o plano de Ads."

    alert_summary = alerts.get("summary") or {}
    high_alerts = _int(alert_summary.get("alta"))

    final_status = "⚪ AGUARDANDO DADOS"
    if investigation:
        verdict = str(investigation.get("veredito") or "")
        if "APROVADO" in verdict:
            final_status = "🟢 CANDIDATO APROVADO PARA TESTE"
        elif "REVISAR RISCO" in verdict:
            final_status = "🔴 BLOQUEADO POR RISCO"
        elif "MONITORAR" in verdict:
            final_status = "🟡 MONITORAR ANTES DE AVANÇAR"
        elif "NÃO PRIORIZAR" in verdict or "NAO PRIORIZAR" in verdict.upper():
            final_status = "⚪ NÃO PRIORIZAR AGORA"
    elif top:
        score = _int(opportunity)
        if score >= 80:
            final_status = "🟢 FORTE OPORTUNIDADE PARA INVESTIGAÇÃO"
        elif score >= 65:
            final_status = "🟡 OPORTUNIDADE A INVESTIGAR"
        else:
            final_status = "⚪ BAIXA PRIORIDADE"

    return {
        "status_final": final_status,
        "produto": product_name or "Nenhum produto disponível",
        "oportunidade": _int(opportunity),
        "aceleracao": _int(acceleration),
        "sazonalidade": f"{season_event} | {season_window}",
        "confianca": str(confidence),
        "por_que": reason,
        "principal_brecha": gap or "Nenhuma brecha forte confirmada",
        "risco": risk,
        "proxima_acao": next_action,
        "alertas_alta": high_alerts,
        "previsao": forecast.get("conclusao") or "Sem previsão confiável ainda",
        "plano_ads": ads_plan.get("status_execucao") or "Sem plano liberado",
        "tem_dados": bool(products or clusters or investigation),
    }
