def _num(v, default=0.0):
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default

def _int(v, default=0):
    try:
        if v in (None, ""):
            return default
        return int(float(v))
    except Exception:
        return default

def build_realistic_forecast(candidate, snapshots=None):
    candidate = candidate or {}
    snapshots = snapshots or []

    current_sales = _int(candidate.get("vendidos_30d"))
    current_price = _num(candidate.get("preco"))
    opportunity = _int(candidate.get("score_oportunidade_hoje"))
    acceleration = _int(candidate.get("score_aceleracao"))
    confidence = _int(candidate.get("confianca_score"))
    snap_count = _int(candidate.get("snapshots"))
    season_window = str(candidate.get("janela_sazonal") or "🟢 Perene")
    event = str(candidate.get("evento_sazonal") or "Perene / sem evento claro")

    observed = {
        "vendas_30d_atual": current_sales,
        "preco_atual": round(current_price,2) if current_price else 0,
        "score_oportunidade": opportunity,
        "score_aceleracao": acceleration,
        "snapshots": snap_count,
        "sazonalidade": f"{event} | {season_window}",
    }

    # Confidence gating
    if snap_count >= 4 and confidence >= 70:
        forecast_conf = "Alta"
        level = 3
    elif snap_count >= 2 and confidence >= 50:
        forecast_conf = "Média"
        level = 2
    elif snap_count >= 1:
        forecast_conf = "Baixa"
        level = 1
    else:
        forecast_conf = "Insuficiente"
        level = 0

    notes=[]
    if snap_count < 2:
        notes.append("Histórico temporal insuficiente para inferir tendência.")
    if confidence < 50:
        notes.append("Confiança da investigação ainda baixa.")
    if current_sales <= 0:
        notes.append("Vendas 30d indisponíveis ou zeradas.")
    if season_window == "🔴 Atrasado":
        notes.append("Janela sazonal atrasada: qualquer projeção positiva deve ser tratada com cautela.")

    scenarios = []

    # Scenario multipliers are intentionally conservative and labeled as scenario, not forecast fact.
    if current_sales > 0:
        if level == 0:
            multipliers = [("Conservador",0.70),("Base",1.00),("Agressivo",1.20)]
        elif level == 1:
            multipliers = [("Conservador",0.80),("Base",1.00),("Agressivo",1.25)]
        elif level == 2:
            growth_adj = min(0.20, max(-0.10, (acceleration-50)/250))
            multipliers = [
                ("Conservador",max(0.75,0.90+growth_adj/2)),
                ("Base",1.00+growth_adj),
                ("Agressivo",1.20+growth_adj),
            ]
        else:
            growth_adj = min(0.30, max(-0.15, (acceleration-50)/200))
            multipliers = [
                ("Conservador",max(0.70,0.90+growth_adj/2)),
                ("Base",1.00+growth_adj),
                ("Agressivo",1.25+growth_adj),
            ]

        for name,mult in multipliers:
            units = max(0, round(current_sales * mult))
            revenue = round(units * current_price,2) if current_price else None
            scenarios.append({
                "cenario":name,
                "unidades_30d":units,
                "faturamento_bruto":revenue,
                "multiplicador":round(mult,3),
                "tipo":"Cenário, não previsão garantida"
            })

    if level == 0:
        conclusion = "⚪ SEM PREVISÃO CONFIÁVEL"
    elif level == 1:
        conclusion = "🟡 CENÁRIOS PRELIMINARES"
    elif level == 2:
        conclusion = "🟢 PREVISÃO COM CONFIANÇA MÉDIA"
    else:
        conclusion = "🟢 PREVISÃO COM CONFIANÇA ALTA"

    if not scenarios:
        conclusion = "⚪ SEM BASE SUFICIENTE PARA CENÁRIOS"

    next_needed=[]
    if snap_count < 2:
        next_needed.append("coletar pelo menos mais um snapshot em outro momento")
    if snap_count < 4:
        next_needed.append("acumular mais histórico antes de tratar a tendência como forte")
    if current_price <= 0:
        next_needed.append("ter preço válido")
    if current_sales <= 0:
        next_needed.append("ter vendas 30d válidas")

    return {
        "conclusao": conclusion,
        "confianca": forecast_conf,
        "nivel": level,
        "observado": observed,
        "cenarios": scenarios,
        "notas": notes,
        "proximo_para_melhorar": next_needed,
    }
