from statistics import median

try:
    from opportunity_engine import similarity, risk_flags
except Exception:
    similarity = None
    risk_flags = lambda p: []

try:
    from competitor_engine import analyze_market
except Exception:
    analyze_market = None

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

def _similar_products(target, products, threshold=0.48, limit=20):
    title = target.get("produto","")
    rows=[]
    for p in products or []:
        if not isinstance(p, dict):
            continue
        if p is target:
            continue
        if str(p.get("pid") or "") and str(p.get("pid") or "") == str(target.get("pid") or ""):
            continue
        try:
            sim = float(similarity(title, p.get("produto",""))) if similarity else 0.0
        except Exception:
            sim = 0.0
        if sim >= threshold:
            q=dict(p)
            q["_similarity"]=round(sim,3)
            rows.append(q)
    rows.sort(key=lambda p:(p["_similarity"], _int(p.get("vendidos_30d"))), reverse=True)
    return rows[:limit]

def _confidence(cluster_row, target, competitors):
    points=0
    reasons=[]
    if _int(target.get("vendidos_30d")) > 0:
        points+=20; reasons.append("vendas 30d disponíveis")
    if _num(target.get("avaliacao")) > 0:
        points+=12; reasons.append("avaliação disponível")
    if _int(target.get("qtd_avaliacoes")) > 0:
        points+=12; reasons.append("quantidade de avaliações disponível")
    if _num(target.get("preco")) > 0:
        points+=10; reasons.append("preço disponível")
    if _int(cluster_row.get("snapshots")) >= 2:
        points+=22; reasons.append("histórico temporal disponível")
    elif _int(cluster_row.get("snapshots")) == 1:
        points+=8; reasons.append("apenas um snapshot")
    if competitors:
        points+=14; reasons.append("concorrentes semelhantes encontrados")
    if cluster_row.get("evento_sazonal"):
        points+=10; reasons.append("sazonalidade classificada")
    points=max(0,min(100,points))
    if points>=75:
        label="Alta"
    elif points>=50:
        label="Média"
    else:
        label="Baixa"
    return points,label,", ".join(reasons)

def investigate_existing_opportunity(cluster_row, all_products):
    target = cluster_row.get("_product") or {}
    if not target:
        target={
            "produto":cluster_row.get("produto",""),
            "preco":cluster_row.get("preco_representante"),
            "vendidos_30d":cluster_row.get("vendidos_30d"),
            "avaliacao":cluster_row.get("avaliacao"),
            "qtd_avaliacoes":cluster_row.get("qtd_avaliacoes"),
            "loja":cluster_row.get("loja",""),
            "url":cluster_row.get("url",""),
        }

    competitors=_similar_products(target, all_products)
    comp_analysis = analyze_market(competitors) if analyze_market and competitors else {"rows":[],"context":{}}
    comp_rows=comp_analysis.get("rows") or []
    top_gap=comp_analysis.get("top_vulnerable")

    opp=_int(cluster_row.get("score_oportunidade_hoje"))
    accel=_int(cluster_row.get("score_aceleracao"))
    snapshots=_int(cluster_row.get("snapshots"))
    risks=risk_flags(target)
    if not risks and cluster_row.get("risco") not in (None,"","Baixo"):
        risks=[cluster_row.get("risco")]

    season_event=cluster_row.get("evento_sazonal") or "Perene / sem evento claro"
    season_window=cluster_row.get("janela_sazonal") or "🟢 Perene"
    days_peak=cluster_row.get("dias_ate_pico")
    dead_stock=cluster_row.get("risco_encalhe") or "Baixo"

    conf_score,conf_label,conf_reason=_confidence(cluster_row,target,competitors)

    positives=[]
    warnings=[]
    why_now=[]

    sold=_int(target.get("vendidos_30d"))
    rating=_num(target.get("avaliacao"))
    reviews=_int(target.get("qtd_avaliacoes"))
    price=_num(target.get("preco"))

    if sold>=3000:
        positives.append("demanda forte já comprovada")
    elif sold>=1000:
        positives.append("boa demanda comprovada")
    elif sold>=300:
        positives.append("demanda presente")
    else:
        warnings.append("demanda ainda fraca na amostra")

    if opp>=72:
        positives.append("score de oportunidade hoje forte")
    elif opp>=58:
        positives.append("oportunidade comercial investigável")
    else:
        warnings.append("score de oportunidade hoje ainda baixo")

    if rating>=4.75 and reviews>=100:
        positives.append("prova social forte")
    elif reviews>5000:
        warnings.append("barreira de avaliações alta")

    if 20 <= price <= 120:
        positives.append("ticket comercialmente interessante")

    if accel>=70 and snapshots>=2:
        positives.append("aceleração forte confirmada por histórico")
        why_now.append("o produto está ganhando velocidade")
    elif accel>=45 and snapshots>=2:
        positives.append("movimento positivo no histórico")
        why_now.append("há sinais de crescimento")
    elif snapshots<2:
        warnings.append("aceleração ainda não confirmada: falta histórico temporal")

    if season_window == "🟢 Momento ideal":
        positives.append(f"janela sazonal favorável: {season_event}")
        why_now.append(f"está na janela ideal para {season_event}")
    elif season_window == "🟡 Atenção":
        warnings.append(f"janela sazonal curta: {season_event}")
        why_now.append(f"há urgência comercial antes de {season_event}")
    elif season_window == "🔴 Atrasado":
        warnings.append(f"janela sazonal praticamente perdida: {season_event}")
    elif season_window == "🔵 Antecipação":
        why_now.append(f"é oportunidade de preparação antecipada para {season_event}")

    if top_gap and _int(top_gap.get("vulnerabilidade"))>=40:
        positives.append("há concorrente semelhante com brecha atacável")
        why_now.append("existe espaço competitivo objetivo")
    elif competitors:
        warnings.append("concorrência semelhante não mostra brecha forte")
    else:
        warnings.append("amostra de concorrentes semelhantes ainda pequena")

    if risks:
        warnings.append("risco especial: " + ", ".join(str(x) for x in risks))

    # Commercial gate
    if risks:
        verdict="🔴 REVISAR RISCO ANTES DE AVANÇAR"
        gate="risco"
    elif opp>=72 and sold>=1000 and conf_score>=50:
        verdict="🟢 APROVADO PARA CÉREBRO DE ANÚNCIOS"
        gate="ads"
    elif opp>=58 and sold>=300:
        verdict="🟡 MANTER EM INVESTIGAÇÃO / MONITORAR"
        gate="monitor"
    else:
        verdict="⚪ NÃO PRIORIZAR AGORA"
        gate="low"

    if not why_now:
        why_now.append("não há gatilho temporal forte confirmado neste momento")

    # What is still missing before money is committed
    missing=[]
    if snapshots<2:
        missing.append("coletar novo snapshot em outro momento para confirmar aceleração")
    if not competitors:
        missing.append("ampliar amostra de concorrentes semelhantes")
    if risks:
        missing.append("resolver/revisar risco antes de qualquer compra")
    missing.append("validar fornecedor, custo posto, margem e teste pequeno somente após aprovação comercial")

    comp_table=[]
    for c in comp_rows[:10]:
        comp_table.append({
            "vulnerabilidade":c.get("vulnerabilidade"),
            "status":c.get("status_concorrente"),
            "produto":c.get("produto"),
            "loja":c.get("loja"),
            "preco":c.get("preco"),
            "vendidos_30d":c.get("vendidos_30d"),
            "avaliacao":c.get("avaliacao"),
            "avaliacoes":c.get("qtd_avaliacoes"),
            "brechas":c.get("brechas"),
            "como_atacar":c.get("como_atacar"),
            "url":c.get("url"),
        })

    return {
        "produto":target.get("produto",""),
        "loja":target.get("loja",""),
        "url":target.get("url",""),
        "preco":price,
        "vendidos_30d":sold,
        "avaliacao":rating,
        "qtd_avaliacoes":reviews,
        "score_oportunidade_hoje":opp,
        "score_aceleracao":accel,
        "snapshots":snapshots,
        "evento_sazonal":season_event,
        "janela_sazonal":season_window,
        "dias_ate_pico":days_peak,
        "risco_encalhe":dead_stock,
        "riscos":risks,
        "concorrentes_semelhantes":len(competitors),
        "top_brecha":top_gap,
        "concorrentes":comp_table,
        "pontos_fortes":positives,
        "alertas":warnings,
        "por_que_agora":why_now,
        "confianca_score":conf_score,
        "confianca":conf_label,
        "confianca_motivo":conf_reason,
        "veredito":verdict,
        "gate":gate,
        "faltando":missing,
    }
