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

def build_alerts(products=None, clusters=None, forecast=None, investigation=None):
    products = products or []
    clusters = clusters or []
    forecast = forecast or {}
    investigation = investigation or {}

    alerts=[]

    for row in clusters:
        product=row.get("produto","")
        score=_int(row.get("score_oportunidade_hoje"))
        accel=_int(row.get("score_aceleracao"))
        season=row.get("janela_sazonal","")
        event=row.get("evento_sazonal","")
        risk=row.get("risco","")
        snapshots=_int(row.get("snapshots"))

        if score >= 80:
            alerts.append({
                "prioridade":"Alta",
                "tipo":"Oportunidade forte",
                "produto":product,
                "mensagem":f"Score de oportunidade {score}. Vale investigação imediata.",
            })

        if accel >= 70 and snapshots >= 2:
            alerts.append({
                "prioridade":"Alta",
                "tipo":"Aceleração",
                "produto":product,
                "mensagem":f"Aceleração {accel} com histórico disponível.",
            })

        if season == "🟢 Momento ideal":
            alerts.append({
                "prioridade":"Alta",
                "tipo":"Sazonalidade",
                "produto":product,
                "mensagem":f"Janela ideal para {event}.",
            })
        elif season == "🟡 Atenção":
            alerts.append({
                "prioridade":"Média",
                "tipo":"Sazonalidade",
                "produto":product,
                "mensagem":f"Janela curta para {event}; decisão precisa ser rápida.",
            })
        elif season == "🔴 Atrasado":
            alerts.append({
                "prioridade":"Alta",
                "tipo":"Risco sazonal",
                "produto":product,
                "mensagem":f"Janela de {event} praticamente perdida.",
            })

        if risk and str(risk).lower() not in ("baixo","nenhum",""):
            alerts.append({
                "prioridade":"Alta",
                "tipo":"Risco",
                "produto":product,
                "mensagem":f"Risco identificado: {risk}.",
            })

    # Forecast-based alerts
    conf=forecast.get("confianca")
    level=_int(forecast.get("nivel"))
    if level >= 3:
        alerts.append({
            "prioridade":"Média",
            "tipo":"Previsão",
            "produto":investigation.get("produto",""),
            "mensagem":"Previsão atingiu confiança alta.",
        })

    # Investigation gate alerts
    gate=investigation.get("gate")
    if gate == "ads":
        alerts.append({
            "prioridade":"Alta",
            "tipo":"Próxima ação",
            "produto":investigation.get("produto",""),
            "mensagem":"Produto aprovado para o Cérebro de Anúncios.",
        })
    elif gate == "risco":
        alerts.append({
            "prioridade":"Alta",
            "tipo":"Bloqueio",
            "produto":investigation.get("produto",""),
            "mensagem":"Produto bloqueado por risco antes de avançar.",
        })

    # Deduplicate
    unique=[]
    seen=set()
    order={"Alta":3,"Média":2,"Baixa":1}
    for a in alerts:
        key=(a["tipo"],a["produto"],a["mensagem"])
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique.sort(key=lambda a: order.get(a["prioridade"],0), reverse=True)

    summary={
        "total":len(unique),
        "alta":sum(1 for a in unique if a["prioridade"]=="Alta"),
        "media":sum(1 for a in unique if a["prioridade"]=="Média"),
        "baixa":sum(1 for a in unique if a["prioridade"]=="Baixa"),
    }
    return {"alerts":unique,"summary":summary}
