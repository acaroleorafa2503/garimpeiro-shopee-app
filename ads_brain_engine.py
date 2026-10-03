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

def _pct(v):
    try:
        return float(v) / 100.0
    except Exception:
        return 0.0

def _round_money(v):
    return round(float(v or 0), 2)

def build_ads_brain(candidate, market_products=None):
    candidate = candidate or {}
    market_products = market_products or []

    title = str(candidate.get("produto") or "")
    current_price = _num(candidate.get("preco"))
    opportunity = _int(candidate.get("score_oportunidade_hoje"))
    acceleration = _int(candidate.get("score_aceleracao"))
    confidence = _int(candidate.get("confianca_score"))
    sold_30d = _int(candidate.get("vendidos_30d"))
    rating = _num(candidate.get("avaliacao"))
    reviews = _int(candidate.get("qtd_avaliacoes"))
    season_window = str(candidate.get("janela_sazonal") or "🟢 Perene")
    season_event = str(candidate.get("evento_sazonal") or "Perene / sem evento claro")
    risk_flags = candidate.get("riscos") or []

    prices = []
    for p in market_products:
        if not isinstance(p, dict):
            continue
        px = _num(p.get("preco"))
        if px > 0:
            prices.append(px)

    median_market_price = 0.0
    if prices:
        s = sorted(prices)
        n = len(s)
        median_market_price = s[n//2] if n % 2 else (s[n//2 - 1] + s[n//2]) / 2

    # ENTRY PRICE
    reference_price = current_price or median_market_price
    if median_market_price > 0 and current_price > 0:
        reference_price = min(current_price, median_market_price)

    if reference_price > 0:
        if opportunity >= 80:
            entry_price = reference_price * 0.95
        elif opportunity >= 68:
            entry_price = reference_price * 0.92
        else:
            entry_price = reference_price * 0.90
    else:
        entry_price = 0.0

    entry_price = _round_money(entry_price)

    # OFFER / KIT
    offer_type = "Produto unitário com promessa clara"
    kit_strategy = "Sem kit obrigatório no primeiro teste."
    if sold_30d >= 3000 and reviews >= 300:
        offer_type = "Oferta de entrada + variação/kit de valor percebido"
        kit_strategy = "Criar kit apenas se aumentar utilidade real e não complicar logística."
    if current_price and current_price < 25:
        kit_strategy = "Priorizar kit de 2 unidades ou combo simples para elevar ticket e diluir custo de Ads."

    # POSITIONING
    differentiators = []
    if candidate.get("top_brecha"):
        tb = candidate["top_brecha"]
        gaps = str(tb.get("brechas") or "")
        attack = str(tb.get("como_atacar") or "")
        if gaps:
            differentiators.append(f"Explorar brecha concorrente: {gaps}")
        if attack:
            differentiators.append(f"Direção de ataque: {attack}")

    if rating >= 4.8:
        differentiators.append("Manter promessa de qualidade compatível com prova social do mercado.")
    elif rating and rating < 4.7:
        differentiators.append("Não copiar os pontos fracos da experiência do anúncio atual.")

    if season_window == "🟢 Momento ideal":
        differentiators.append(f"Comunicação pode aproveitar a janela de {season_event}.")
    elif season_window == "🟡 Atenção":
        differentiators.append(f"Campanha precisa ser rápida: janela curta para {season_event}.")
    elif season_window == "🔵 Antecipação":
        differentiators.append(f"Preparar campanha antecipadamente para {season_event}.")

    if not differentiators:
        differentiators.append("Diferenciar por clareza visual, prova de uso e oferta simples.")

    # TITLE ANGLE
    title_terms = []
    base_words = [w for w in title.replace("|"," ").replace("-"," ").split() if len(w) > 2]
    for w in base_words:
        lw = w.lower()
        if lw not in [x.lower() for x in title_terms]:
            title_terms.append(w)
        if len(title_terms) >= 8:
            break
    title_template = " ".join(title_terms)
    if title_template:
        title_template += " | Benefício principal | Diferencial"
    else:
        title_template = "Produto + benefício principal + principal diferencial + uso"

    # MAIN IMAGE
    image_plan = [
        "Produto ocupando a maior parte da imagem, sem poluição visual.",
        "Benefício principal entendido em 1 segundo.",
        "Evitar excesso de texto na imagem principal.",
        "Segunda imagem: problema → solução.",
        "Terceira imagem: medidas/compatibilidade/uso real.",
        "Quarta imagem: diferencial contra concorrentes.",
    ]

    # ADS BUDGET HEURISTIC (not pretending exact economics)
    # These are test-budget recommendations, not forecasts.
    if confidence >= 75 and opportunity >= 75:
        daily_budget = 30.0
    elif confidence >= 50 and opportunity >= 65:
        daily_budget = 20.0
    else:
        daily_budget = 12.0

    if season_window == "🟡 Atenção" and opportunity >= 65:
        daily_budget *= 1.20
    daily_budget = _round_money(daily_budget)

    test_days = 5 if confidence >= 50 else 7
    test_budget = _round_money(daily_budget * test_days)

    # Testing rules
    test_rule = (
        f"Rodar teste inicial por {test_days} dias com orçamento aproximado de "
        f"R$ {daily_budget:.2f}/dia, desde que a margem futura permita."
    )

    cut_rules = [
        "Cortar palavra/segmento que consome cliques sem sinal de intenção após volume mínimo razoável.",
        "Não insistir em anúncio com CTR muito baixo após troca de imagem/título.",
        "Se houver vendas mas margem negativa, corrigir preço/oferta antes de escalar.",
        "Se produto entrar em risco sazonal atrasado, reduzir exposição e evitar estoque novo.",
    ]

    scale_rules = [
        "Escalar somente após vendas repetidas, margem positiva e estabilidade do anúncio.",
        "Aumentar orçamento gradualmente, não de forma brusca.",
        "Priorizar o anúncio/variação com melhor conversão, não apenas mais cliques.",
        "Manter monitoramento de preço e concorrência durante a escala.",
    ]

    # Guard rails
    blocked_reasons = []
    if risk_flags:
        blocked_reasons.append("Há risco especial pendente na investigação.")
    if confidence < 50:
        blocked_reasons.append("Confiança da investigação ainda insuficiente.")
    if opportunity < 58:
        blocked_reasons.append("Score de oportunidade ainda baixo para campanha.")
    if sold_30d < 300:
        blocked_reasons.append("Demanda atual ainda fraca.")

    if blocked_reasons:
        execution_status = "🟡 PLANO GERADO, MAS NÃO LIBERADO PARA ESCALA"
    else:
        execution_status = "🟢 PLANO DE TESTE LIBERADO"

    # What must be entered later before real money decisions
    missing_financials = [
        "custo posto no Brasil",
        "taxas reais da Shopee aplicáveis ao produto",
        "margem alvo",
        "CAC máximo / ROAS de equilíbrio",
    ]

    return {
        "produto": title,
        "status_execucao": execution_status,
        "preco_atual": _round_money(current_price),
        "preco_mediano_mercado": _round_money(median_market_price),
        "preco_entrada_sugerido": entry_price,
        "tipo_oferta": offer_type,
        "estrategia_kit": kit_strategy,
        "diferenciais": differentiators,
        "titulo_sugerido": title_template,
        "plano_imagem": image_plan,
        "orcamento_diario_teste": daily_budget,
        "dias_teste": test_days,
        "orcamento_total_teste": test_budget,
        "regra_teste": test_rule,
        "regras_corte": cut_rules,
        "regras_escala": scale_rules,
        "bloqueios": blocked_reasons,
        "financeiro_pendente": missing_financials,
        "oportunidade": opportunity,
        "aceleracao": acceleration,
        "confianca": confidence,
        "evento_sazonal": season_event,
        "janela_sazonal": season_window,
    }
