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

MARKETPLACE_DOMAINS = (
    "mercadolivre.com.br","amazon.com.br","shopee.com.br",
    "magazineluiza.com.br","americanas.com.br"
)

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
    if any(d in domain for d in MARKETPLACE_DOMAINS):
        return "Marketplace"
    if any(w in n for w in SUPPLIER_WORDS):
        return "Fornecedor"
    return "Fonte pública"

def _score_product(item, category_match=True):
    title = item.get("product_name","")
    desc = item.get("description","")
    domain = item.get("source_domain","")
    text = _norm(f"{title} {desc}")
    score = 45
    reasons = []

    if any(d in domain for d in MARKETPLACE_DOMAINS):
        score += 15; reasons.append("marketplace")
    if any(w in text for w in SUPPLIER_WORDS):
        score += 10; reasons.append("fornecedor")
    if any(noun in _norm(title) for noun in PRODUCT_NOUNS):
        score += 12; reasons.append("produto específico")
    if "kit" in text:
        score += 5; reasons.append("kit")
    if re.search(r"r\$\s?\d+|preço|preco", text):
        score += 5; reasons.append("preço")
    if "avalia" in text or "estrela" in text:
        score += 5; reasons.append("avaliações")
    if category_match:
        score += 5; reasons.append("categoria coerente")
    rank = item.get("rank") or 10
    score += max(0, 8-int(rank))
    return min(score,100), reasons[:5]

def classification(score):
    if score >= 82: return "🔥 Prioridade alta"
    if score >= 70: return "🟢 Investigar agora"
    if score >= 58: return "🟡 Radar"
    return "⚪ Baixa prioridade"

def build_queries(category, mode, max_queries):
    cfg = CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["Geral / todas"])
    base = list(cfg.get("queries", []))
    if mode == "Fornecedor / atacado":
        base = [q.replace("comprar Brasil","atacado fornecedor Brasil") for q in base]
    elif mode == "Recorrência":
        base = [q + " refil recompra recorrente" for q in base]
    elif mode == "Problema → solução":
        base = [q + " resolve problema avaliações" for q in base]
    elif mode == "Sazonalidade":
        year = datetime.now().year
        base = [q + f" sazonal próximos meses {year}" for q in base]

    if not base:
        base = ["produto específico comprar Brasil"]
    return base[:max(1,int(max_queries))]

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

            products.append({
                "score_radar": score,
                "classificacao": classification(score),
                "produto": product_name,
                "tipo_fonte": _source_kind(domain, text),
                "por_que_agora": ", ".join(reasons) if reasons else "produto específico encontrado",
                "fonte": domain,
                "url": url,
                "descricao": desc[:350],
                "consulta": query,
            })

    products.sort(key=lambda x: x["score_radar"], reverse=True)

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
