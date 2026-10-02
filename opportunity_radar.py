import re
from datetime import datetime
from urllib.parse import urlparse
from collectors.brave_search import BraveSearchCollector

CATEGORY_CONFIG = {
    "Geral / todas": {
        "tokens": [],
        "queries": [
            "produto pet específico comprar Brasil",
            "organizador casa produto específico comprar Brasil",
            "utensílio cozinha produto específico comprar Brasil",
            "ferramenta compacta produto específico comprar Brasil",
            "acessório automotivo produto específico comprar Brasil",
            "acessório beleza produto específico comprar Brasil",
        ],
    },
    "Pets": {
        "tokens": ["pet","cão","cachorro","gato","coleira","comedouro","bebedouro","tapete higiênico","arranhador","escova","guia","peitoral","brinquedo"],
        "queries": [
            "coleira pet comprar atacado Brasil",
            "tapete higiênico cachorro atacado Brasil",
            "arranhador gato comprar Brasil",
            "comedouro pet comprar atacado Brasil",
            "escova removedora pelos pet comprar Brasil",
            "brinquedo pet interativo comprar Brasil",
        ],
    },
    "Casa e cozinha": {
        "tokens": ["cozinha","panela","pote","escorredor","organizador","talher","prateleira","copo","garrafa","pia","geladeira"],
        "queries": [
            "organizador panelas comprar Brasil",
            "escorredor cozinha comprar Brasil",
            "organizador geladeira comprar Brasil",
            "pote hermético kit comprar Brasil",
            "organizador pia comprar Brasil",
        ],
    },
    "Organização": {
        "tokens": ["organizador","gaveta","armário","guarda roupa","sapato","cabide","caixa organizadora","prateleira"],
        "queries": [
            "organizador gaveta comprar Brasil",
            "organizador guarda roupa comprar Brasil",
            "organizador sapatos comprar Brasil",
            "caixa organizadora comprar Brasil",
        ],
    },
    "Beleza": {
        "tokens": ["beleza","cabelo","maquiagem","skincare","escova","touca","organizador maquiagem","pente","necessaire"],
        "queries": [
            "organizador maquiagem comprar Brasil",
            "acessório cabelo comprar Brasil",
            "escova cabelo produto comprar Brasil",
            "necessaire organizadora comprar Brasil",
        ],
    },
    "Ferramentas": {
        "tokens": ["ferramenta","broca","alicate","chave","furadeira","parafuso","kit reparo","soquete"],
        "queries": [
            "kit ferramentas comprar Brasil",
            "jogo brocas comprar Brasil",
            "alicate multifuncional comprar Brasil",
            "kit chave soquete comprar Brasil",
        ],
    },
    "Automotivo": {
        "tokens": ["carro","automotivo","veículo","porta malas","painel","limpeza carro","suporte celular carro"],
        "queries": [
            "organizador porta malas comprar Brasil",
            "suporte celular carro comprar Brasil",
            "kit limpeza automotiva comprar Brasil",
            "organizador banco carro comprar Brasil",
        ],
    },
    "Esporte e lazer": {
        "tokens": ["treino","academia","corrida","esporte","garrafa","faixa","elástico","bolsa esportiva"],
        "queries": [
            "elástico treino comprar Brasil",
            "acessório academia comprar Brasil",
            "garrafa esportiva comprar Brasil",
            "bolsa treino compacta comprar Brasil",
        ],
    },
    "Bebê e família": {
        "tokens": ["bebê","bebe","mamadeira","fralda","organizador bebê","passeio bebê","alimentação bebê"],
        "queries": [
            "organizador bebê comprar Brasil",
            "acessório alimentação bebê comprar Brasil",
            "organizador carrinho bebê comprar Brasil",
            "kit passeio bebê comprar Brasil",
        ],
    },
    "Eletrônicos e acessórios": {
        "tokens": ["celular","cabo","carregador","suporte","eletrônico","eletronico","fone","adaptador"],
        "queries": [
            "suporte celular comprar Brasil",
            "organizador cabos comprar Brasil",
            "adaptador usb comprar Brasil",
            "acessório carregamento comprar Brasil",
        ],
    },
}


# Compatibilidade com o app.py atual
CATEGORY_LABELS = {name: name for name in CATEGORY_CONFIG.keys()}
MODE_HINTS = {
    "Geral": "Busca equilibrada de produtos específicos",
    "Sazonalidade": "Prioriza oportunidades ligadas aos próximos meses",
    "Recorrência": "Prioriza produtos com recompra/refil",
    "Problema → solução": "Prioriza produtos que resolvem dores práticas",
    "Fornecedor / atacado": "Prioriza sinais de fabricante, distribuidor e atacado",
}

SHOPEE_DOMAINS = ("shopee.com.br",)
SECONDARY_MARKETPLACE_DOMAINS = (
    "mercadolivre.com.br","amazon.com.br","magazineluiza.com.br","americanas.com.br"
)
MARKETPLACE_DOMAINS = SHOPEE_DOMAINS + SECONDARY_MARKETPLACE_DOMAINS

SUPPLIER_WORDS = (
    "atacado","distribuidor","distribuidora","fabricante","fábrica","fabrica",
    "fornecedor","revenda","caixa fechada"
)

GENERIC_TITLES = (
    "acessórios pet","acessorios pet","distribuidora pet shop","atacado de produtos pet",
    "produtos pet mais vendidos","produtos mais vendidos","mais vendidos online",
    "loja online","pet shop","marketplace","catálogo","catalogo","categoria",
    "linha completa","todos os produtos","departamento","ofertas","home"
)

PRODUCT_NOUNS = (
    "coleira","tapete","arranhador","comedouro","bebedouro","escova","guia","peitoral","brinquedo",
    "organizador","suporte","kit","pote","escorredor","prateleira","garrafa","capa","protetor",
    "refil","dispensador","gancho","estojo","bandeja","adaptador","cabo","filtro","rodo",
    "caixa","bolsa","lixeira","chave","alicate","broca","jogo","aplicador","removedor",
    "necessaire","touca","pente","elástico","faixa","mamadeira","fralda"
)

BRAND_NOISE = (
    "blog","guia","tendência","tendencia","como escolher","o que vender","ideias",
    "melhores produtos","mais vendidos","lista de","top 10","top 20","2026"
)

def _norm(s):
    return re.sub(r"\s+"," ",(s or "").lower()).strip()

def _domain(url, fallback=""):
    return (fallback or urlparse(url or "").netloc or "").lower()

def _clean_title(title):
    title = re.sub(r"\s+"," ",title or "").strip()
    # Remove site suffixes and long marketing tails
    title = re.split(r"\s+[|–—]\s+", title)[0]
    return title[:160]

def _is_generic_page(title, desc, domain):
    t = _norm(title)
    text = _norm(f"{title} {desc}")
    if any(x in t for x in GENERIC_TITLES):
        # allow a generic phrase only if a concrete product noun also appears strongly
        concrete = sum(1 for p in PRODUCT_NOUNS if p in t)
        if concrete < 1:
            return True
    if any(x in text for x in BRAND_NOISE) and not any(p in t for p in PRODUCT_NOUNS):
        return True
    if len(t.split()) < 2:
        return True
    return False

def _extract_product_name(title, desc):
    title = _clean_title(title)
    t = _norm(title)
    if _is_generic_page(title, desc, ""):
        return None

    # Prefer titles that contain a concrete product noun.
    if any(noun in t for noun in PRODUCT_NOUNS):
        # Strip common supplier/store prefixes.
        title = re.sub(
            r"^(distribuidora|distribuidor|atacado|fornecedor|loja|pet shop)\s*[:\-–—]?\s*",
            "",
            title,
            flags=re.I,
        ).strip()
        return title if len(title) >= 6 else None

    # If title isn't concrete, try the description's first phrase.
    first = re.split(r"[.;|]", desc or "")[0].strip()
    fn = _norm(first)
    if any(noun in fn for noun in PRODUCT_NOUNS) and 6 <= len(first) <= 150:
        return first
    return None

def _is_category_match(category, product_name, desc):
    if category == "Geral / todas":
        return True
    cfg = CATEGORY_CONFIG.get(category, {})
    tokens = cfg.get("tokens", [])
    text = _norm(f"{product_name} {desc}")
    return any(tok in text for tok in tokens)

def _source_kind(domain, text):
    n = _norm(text)
    if any(d in domain for d in SHOPEE_DOMAINS) or "shopee" in n:
        return "Shopee"
    if any(w in n for w in SUPPLIER_WORDS):
        return "Fornecedor"
    if any(d in domain for d in SECONDARY_MARKETPLACE_DOMAINS):
        return "Marketplace secundário"
    return "Fonte pública"

def _score_product(item, category_match=True):
    title=item.get("product_name","")
    desc=item.get("description","")
    domain=item.get("source_domain","")
    text=_norm(f"{title} {desc}")
    score=34
    reasons=[]

    shopee_signal = any(d in domain for d in SHOPEE_DOMAINS) or "shopee" in text
    secondary_market = any(d in domain for d in SECONDARY_MARKETPLACE_DOMAINS)
    supplier_signal = any(w in text for w in SUPPLIER_WORDS)

    if shopee_signal:
        score += 34; reasons.append("evidência Shopee")
    elif secondary_market:
        score += 8; reasons.append("confirmação em outro marketplace")

    if supplier_signal:
        score += 12; reasons.append("fornecedor/atacado")
    if any(noun in _norm(title) for noun in PRODUCT_NOUNS):
        score += 10; reasons.append("produto específico")
    if "kit" in text:
        score += 4; reasons.append("potencial de kit")
    if re.search(r"r\$\s?\d+|preço|preco", text):
        score += 4; reasons.append("sinal de preço")
    if "avalia" in text or "estrela" in text or "vendid" in text:
        score += 5; reasons.append("sinal de demanda")
    if category_match:
        score += 5; reasons.append("categoria coerente")
    rank=item.get("rank") or 10
    score += max(0,6-int(rank))

    if not shopee_signal:
        score=min(score,79)

    return min(score,100), reasons[:6]

def classification(score):
    if score >= 82: return "🔥 Prioridade alta"
    if score >= 70: return "🟢 Investigar agora"
    if score >= 58: return "🟡 Radar"
    return "⚪ Baixa prioridade"

def build_queries(category, mode, max_queries):
    cfg = CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["Geral / todas"])
    base_terms = list(cfg.get("queries", []))
    terms = []
    for q in base_terms:
        q2 = re.sub(r"\b(comprar|Brasil|atacado|produto específico)\b", " ", q, flags=re.I)
        q2 = re.sub(r"\s+", " ", q2).strip()
        if q2 and q2 not in terms:
            terms.append(q2)
    if not terms:
        terms = ["produto utilidade"]

    queries = []
    for term in terms:
        queries.append(f'site:shopee.com.br "{term}"')
        queries.append(f'"{term}" Shopee Brasil')
        if mode == "Fornecedor / atacado":
            queries.append(f'"{term}" atacado fornecedor distribuidor Brasil')
        elif mode == "Recorrência":
            queries.append(f'"{term}" refil recompra recorrente Shopee')
        elif mode == "Problema → solução":
            queries.append(f'"{term}" avaliações problema solução Shopee')
        elif mode == "Sazonalidade":
            queries.append(f'"{term}" Shopee sazonal próximos meses {datetime.now().year}')
        else:
            queries.append(f'"{term}" atacado fornecedor Brasil')
            queries.append(f'"{term}" Mercado Livre Amazon Brasil')

    seen=[]; used=set()
    for q in queries:
        if q not in used:
            seen.append(q); used.add(q)
    return seen[:max(1,int(max_queries))]

def _canonical_tokens(name):
    n = _norm(name)
    # Remove marketplace/site tails and model-only noise.
    n = re.sub(r"\b(amazon\.com\.br|mercado livre|magazine luiza|magalu|shopee)\b", " ", n)
    n = re.sub(r"\b(110v|220v|bivolt)\b", " ", n)
    n = re.sub(r"\b(r\$)?\s?\d+([.,]\d+)?\b", " ", n)
    n = re.sub(r"[^a-z0-9áàâãéêíóôõúç\s]", " ", n)
    toks = [t for t in n.split() if len(t) > 2 and t not in STOPWORDS]
    return toks

def _product_family(name):
    toks = _canonical_tokens(name)
    nouns = [t for t in toks if any(p == t or p in t for p in PRODUCT_NOUNS)]
    core = []
    for t in toks:
        if t not in core:
            core.append(t)
    # Keep a compact signature; product noun first when available.
    ordered = []
    for t in nouns + core:
        if t not in ordered:
            ordered.append(t)
    return ordered[:7]

def _similar_product(a, b):
    ta, tb = set(_product_family(a)), set(_product_family(b))
    if not ta or not tb:
        return False
    common = ta & tb
    # Must share at least one concrete product noun.
    noun_common = any(any(p == x or p in x for p in PRODUCT_NOUNS) for x in common)
    if not noun_common:
        return False
    j = len(common) / max(1, len(ta | tb))
    # Flexible enough to merge "organizador geladeira" variants.
    return j >= 0.42 or (len(common) >= 2 and min(len(ta), len(tb)) <= 4)

def _best_product_name(names):
    # Prefer concise, concrete names and avoid marketplace suffixes.
    cleaned = [_clean_title(x) for x in names if x]
    cleaned.sort(key=lambda x: (len(_canonical_tokens(x)), -len(x)), reverse=False)
    # Among shortest useful names, prefer one containing more concrete product nouns.
    cleaned.sort(key=lambda x: (-sum(1 for p in PRODUCT_NOUNS if p in _norm(x)), len(x)))
    return cleaned[0] if cleaned else ""

def _consolidate_products(rows):
    clusters = []
    for row in rows:
        placed = False
        for c in clusters:
            if _similar_product(row["oportunidade"], c["names"][0]):
                c["rows"].append(row)
                c["names"].append(row["oportunidade"])
                placed = True
                break
        if not placed:
            clusters.append({"names":[row["oportunidade"]],"rows":[row]})

    consolidated = []
    for c in clusters:
        members = c["rows"]
        domains = []
        urls = []
        source_types = []
        reasons = []
        for r in members:
            if r.get("fonte") and r["fonte"] not in domains:
                domains.append(r["fonte"])
            if r.get("url") and r["url"] not in urls:
                urls.append(r["url"])
            if r.get("tipo_fonte") and r["tipo_fonte"] not in source_types:
                source_types.append(r["tipo_fonte"])
            if r.get("por_que_agora"):
                reasons.extend([x.strip() for x in r["por_que_agora"].split(",") if x.strip()])

        base = max(members, key=lambda x: x.get("score_radar",0)).copy()
        n_sources = len(domains)
        confirmation_bonus = min(8, max(0, n_sources - 1) * 3)
        base["score_radar"] = min(100, int(base.get("score_radar",0)) + confirmation_bonus)
        base["classificacao"] = classification(base["score_radar"])
        base["oportunidade"] = _best_product_name(c["names"])
        shopee_domains = [d for d in domains if any(sd in d for sd in SHOPEE_DOMAINS)]
        secondary_domains = [d for d in domains if any(md in d for md in SECONDARY_MARKETPLACE_DOMAINS)]
        supplier_domains = list(dict.fromkeys([
            r.get("fonte") for r in members if r.get("tipo_fonte") == "Fornecedor" and r.get("fonte")
        ]))
        tem_shopee = bool(shopee_domains) or any(r.get("tipo_fonte") == "Shopee" for r in members)

        if tem_shopee:
            base["score_radar"] = min(100, base["score_radar"] + 6)
        else:
            base["score_radar"] = min(base["score_radar"], 79)

        base["classificacao"] = classification(base["score_radar"])
        base["fontes_confirmando"] = n_sources
        base["evidencia_shopee"] = "✅ Sim" if tem_shopee else "⚠️ Não"
        base["confirmacoes_secundarias"] = len(secondary_domains)
        base["fornecedores_sinal"] = len(supplier_domains)
        base["fontes"] = ", ".join(domains[:6])
        base["tipo_fonte"] = ", ".join(source_types)
        base["evidencias"] = f"{n_sources} fonte(s) independente(s)"
        unique_reasons = []
        for x in reasons:
            if x not in unique_reasons:
                unique_reasons.append(x)
        base["por_que_agora"] = ", ".join(unique_reasons[:5]) + (
            f"; confirmação em {n_sources} fonte(s)" if n_sources > 1 else ""
        )
        base["url"] = urls[0] if urls else base.get("url","")
        consolidated.append(base)

    consolidated.sort(
        key=lambda x: (x.get("score_radar",0), x.get("fontes_confirmando",1)),
        reverse=True
    )
    return consolidated

def run_opportunity_radar(category="Geral / todas", mode="Geral", max_queries=6, results_per_query=8):
    collector = BraveSearchCollector(count=max(1,min(20,int(results_per_query))))
    if not collector.enabled():
        return {
            "enabled": False,
            "message": "BRAVE_SEARCH_API_KEY não configurada.",
            "queries_used": 0,
            "rows": [],
            "suppliers": [],
        }

    queries = build_queries(category, mode, max_queries)
    products = []
    suppliers = []
    seen_products = set()
    seen_urls = set()
    discarded_generic = 0
    discarded_category = 0
    errors = []

    for query in queries:
        try:
            results = collector.search(query)
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            continue

        for r in results:
            url = r.get("url","")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = _clean_title(r.get("title",""))
            desc = r.get("description","") or ""
            domain = _domain(url, r.get("source_domain",""))

            # Store supplier source separately, but never score it as a product by itself.
            text = _norm(f"{title} {desc}")
            if any(w in text for w in SUPPLIER_WORDS):
                suppliers.append({
                    "fornecedor": title,
                    "fonte": domain,
                    "url": url,
                    "consulta": query,
                })

            if _is_generic_page(title, desc, domain):
                discarded_generic += 1
                continue

            product_name = _extract_product_name(title, desc)
            if not product_name:
                discarded_generic += 1
                continue

            if not _is_category_match(category, product_name, desc):
                discarded_category += 1
                continue

            key = _norm(product_name)
            if key in seen_products:
                continue
            seen_products.add(key)

            item = {
                "product_name": product_name,
                "description": desc,
                "source_domain": domain,
                "rank": r.get("rank",10),
            }
            score, reasons = _score_product(item, True)

            source_kind = _source_kind(domain, text)
            products.append({
                "score_radar": score,
                "classificacao": classification(score),
                "produto": product_name,
                "oportunidade": product_name,
                "tipo_fonte": source_kind,
                "evidencia_shopee": "✅ Sim" if source_kind == "Shopee" else "⚠️ Não",
                "por_que_agora": ", ".join(reasons) if reasons else "produto específico encontrado",
                "fonte": domain,
                "url": url,
                "descricao": desc[:350],
                "consulta": query,
            })

    products.sort(key=lambda x: x["score_radar"], reverse=True)
    products = _consolidate_products(products)

    # Deduplicate supplier list by domain/name
    unique_suppliers = []
    supplier_keys = set()
    for s in suppliers:
        k = (_norm(s["fornecedor"]), s["fonte"])
        if k not in supplier_keys:
            supplier_keys.add(k)
            unique_suppliers.append(s)

    return {
        "enabled": True,
        "message": "Garimpo de produtos concluído.",
        "queries_used": len(queries),
        "results_found": len(products),
        "suppliers_found": len(unique_suppliers),
        "generic_discarded": discarded_generic,
        "category_discarded": discarded_category,
        "errors": errors,
        "rows": products,
        "suppliers": unique_suppliers,
    }
