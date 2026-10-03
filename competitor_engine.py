from statistics import median

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

def analyze_competitor(product, market_context=None):
    market_context = market_context or {}
    sold = _int(product.get("vendidos_30d"))
    rating = _num(product.get("avaliacao"))
    reviews = _int(product.get("qtd_avaliacoes"))
    price = _num(product.get("preco"))
    store = product.get("loja") or ""
    official = str(product.get("oficial") or "").lower()
    preferred = str(product.get("preferida") or "").lower()

    median_price = _num(market_context.get("median_price"))
    median_reviews = _num(market_context.get("median_reviews"))
    median_rating = _num(market_context.get("median_rating"))
    median_sales = _num(market_context.get("median_sales"))

    vulnerability = 0
    strengths = []
    gaps = []
    attack = []

    # Demand strength / relevance as competitor
    if sold >= 10000:
        strengths.append("volume de vendas muito alto")
    elif sold >= 3000:
        strengths.append("volume de vendas alto")
    elif sold >= 1000:
        strengths.append("boa tração")
    elif sold >= 300:
        strengths.append("tração moderada")

    # Rating weaknesses
    if rating and rating < 4.60:
        vulnerability += 28
        gaps.append("nota baixa para o volume")
        attack.append("promessa clara + controle de qualidade + pós-venda")
    elif rating and rating < 4.75:
        vulnerability += 18
        gaps.append("nota abaixo dos melhores")
        attack.append("destacar qualidade/garantia e reduzir pontos de frustração")
    elif median_rating and rating < median_rating - 0.08:
        vulnerability += 10
        gaps.append("nota abaixo da média do cluster")

    # Review moat
    if sold >= 1000 and reviews < 150:
        vulnerability += 22
        gaps.append("poucas avaliações frente às vendas")
        attack.append("entrar cedo e acelerar prova social")
    elif sold >= 1000 and reviews < 500:
        vulnerability += 14
        gaps.append("barreira de avaliações ainda vencível")
        attack.append("usar oferta de entrada para ganhar avaliações")
    elif median_reviews and reviews < median_reviews * 0.5 and sold >= median_sales:
        vulnerability += 10
        gaps.append("prova social abaixo da mediana")

    # Price position
    if median_price > 0:
        if price >= median_price * 1.20:
            vulnerability += 18
            gaps.append("preço muito acima da mediana")
            attack.append("entrar 5–12% abaixo ou entregar mais valor pelo mesmo preço")
        elif price >= median_price * 1.08:
            vulnerability += 10
            gaps.append("preço acima da mediana")
            attack.append("usar preço de entrada ou kit de maior valor percebido")
        elif price <= median_price * 0.80:
            strengths.append("preço agressivo")
            attack.append("evitar guerra de preço; diferenciar por oferta e imagem")

    # Store strength
    if official in ("nao","não","false","0",""):
        vulnerability += 5
        gaps.append("não aparenta ser loja oficial")
    else:
        strengths.append("loja oficial")

    if preferred in ("nao","não","false","0",""):
        vulnerability += 4
        gaps.append("sem selo preferido/verificado")
    else:
        strengths.append("loja preferida/verificada")

    # Sales vs rating tension
    if sold >= 3000 and rating and rating < 4.75:
        vulnerability += 8
        gaps.append("vende muito apesar de experiência mediana")
        attack.append("copiar demanda, não os problemas do concorrente")

    vulnerability = max(0, min(100, vulnerability))

    if vulnerability >= 60:
        label = "🎯 Vulnerável"
    elif vulnerability >= 40:
        label = "🟡 Brecha moderada"
    elif vulnerability >= 20:
        label = "🟠 Brecha pequena"
    else:
        label = "🛡️ Forte"

    if not gaps:
        gaps = ["sem brecha objetiva forte nos dados atuais"]
    if not attack:
        attack = ["diferenciar imagem principal, oferta e conteúdo antes de competir por preço"]

    return {
        "vulnerabilidade": vulnerability,
        "status_concorrente": label,
        "forcas": ", ".join(strengths) if strengths else "sem força destacada nos campos disponíveis",
        "brechas": ", ".join(dict.fromkeys(gaps)),
        "como_atacar": ", ".join(dict.fromkeys(attack)),
        "loja": store,
        "produto": product.get("produto",""),
        "preco": price,
        "vendidos_30d": sold,
        "avaliacao": rating,
        "qtd_avaliacoes": reviews,
        "url": product.get("url",""),
    }

def build_market_context(products):
    rows = products or []
    prices = [_num(p.get("preco")) for p in rows if _num(p.get("preco")) > 0]
    reviews = [_int(p.get("qtd_avaliacoes")) for p in rows if _int(p.get("qtd_avaliacoes")) > 0]
    ratings = [_num(p.get("avaliacao")) for p in rows if _num(p.get("avaliacao")) > 0]
    sales = [_int(p.get("vendidos_30d")) for p in rows if _int(p.get("vendidos_30d")) > 0]
    return {
        "median_price": median(prices) if prices else 0,
        "median_reviews": median(reviews) if reviews else 0,
        "median_rating": median(ratings) if ratings else 0,
        "median_sales": median(sales) if sales else 0,
    }

def analyze_market(products):
    ctx = build_market_context(products)
    analyzed = [analyze_competitor(p, ctx) for p in (products or [])]
    analyzed.sort(
        key=lambda r:(
            r["vulnerabilidade"],
            r["vendidos_30d"],
            -r["qtd_avaliacoes"]
        ),
        reverse=True
    )
    return {
        "context": ctx,
        "rows": analyzed,
        "top_vulnerable": analyzed[0] if analyzed else None,
    }

def strategy_from_market(analysis):
    rows = analysis.get("rows", []) if analysis else []
    if not rows:
        return {
            "headline":"Sem dados suficientes",
            "price_strategy":"—",
            "social_strategy":"—",
            "offer_strategy":"—",
            "creative_strategy":"—",
        }

    top = rows[0]
    ctx = analysis.get("context", {})
    median_price = _num(ctx.get("median_price"))

    if top["vulnerabilidade"] >= 60:
        headline = "Há concorrente forte em vendas, mas com brechas claras."
    elif top["vulnerabilidade"] >= 40:
        headline = "Há brechas moderadas; entrada precisa ser bem posicionada."
    else:
        headline = "Mercado mais difícil; diferenciação precisa ser forte."

    if median_price > 0:
        price_strategy = f"Testar entrada próxima ou até 5–10% abaixo da mediana do cluster (R$ {median_price:.2f}), sem iniciar guerra de preço."
    else:
        price_strategy = "Validar mediana de preço antes de definir entrada."

    social_strategy = "Ganhar avaliações rapidamente com experiência consistente, embalagem simples e pós-venda claro."
    offer_strategy = "Criar kit/variação útil ou bônus percebido quando possível, evitando competir apenas por preço."
    creative_strategy = "Imagem principal limpa, benefício visual imediato e prova do uso real; explorar exatamente a brecha encontrada no concorrente."

    return {
        "headline": headline,
        "price_strategy": price_strategy,
        "social_strategy": social_strategy,
        "offer_strategy": offer_strategy,
        "creative_strategy": creative_strategy,
    }
