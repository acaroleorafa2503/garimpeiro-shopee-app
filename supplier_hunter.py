import re
from statistics import median
from urllib.parse import urlparse
from collectors.brave_search import BraveSearchCollector

SUPPLIER_WORDS = (
    "atacado","atacadista","distribuidor","distribuidora","fabricante","fábrica","fabrica",
    "fornecedor","revenda","caixa fechada","lote mínimo","lote minimo","pedido mínimo",
    "pedido minimo","lojista","b2b","representante","importador"
)

STRONG_SUPPLIER_SIGNALS = (
    "venda por atacado","somente atacado","para lojistas","revendedores",
    "pedido mínimo","pedido minimo","lote mínimo","lote minimo",
    "caixa fechada","distribuidora","fabricante","fábrica","fabrica"
)

EXCLUDE_HINTS = (
    "blog","notícia","noticia","guia","como escolher","mais vendidos","tendência","tendencia",
    "mercado livre","amazon","magazine luiza","magalu","shopee","lista de produtos"
)

TITLE_NOISE = (
    "armário","armario","cozinha","casa","ajustável","ajustavel","suporte",
    "tampa","tampas","utensílio","utensilios","promoção","promocao","oferta",
    "novo","premium","universal","multiuso"
)

def _norm(s):
    return re.sub(r"\s+"," ",(s or "").lower()).strip()

def _domain(url, fallback=""):
    return (fallback or urlparse(url or "").netloc or "").lower()

def _clean_product_name(name):
    n = re.sub(r"\s+"," ",name or "").strip()

    # Remove marketplace/marketing tails.
    n = re.sub(r"\b(amazon\.com\.br|mercado livre|magazine luiza|magalu|shopee)\b", " ", n, flags=re.I)
    n = re.sub(r"\b(110v|220v|bivolt)\b", " ", n, flags=re.I)
    n = re.sub(r"\b(cor|modelo|tamanho)\s+\w+\b", " ", n, flags=re.I)
    n = re.sub(r"\b(r\$)?\s?\d+([.,]\d+)?\b", " ", n, flags=re.I)
    n = re.sub(r"\s+"," ",n).strip(" -–—|")

    # Prefer the meaningful left side before long ad tails.
    parts = re.split(r"\s+[|–—]\s+", n)
    if parts:
        n = parts[0].strip()

    return n[:120]

def _core_phrase(name):
    n = _norm(_clean_product_name(name))

    # Known commercial patterns first.
    patterns = [
        (r".*organizador.*panelas.*", "organizador de panelas"),
        (r".*suporte.*panelas.*", "suporte para panelas"),
        (r".*organizador.*geladeira.*", "organizador de geladeira"),
        (r".*porta.*tampas.*", "organizador de tampas"),
        (r".*escorredor.*cozinha.*", "escorredor de cozinha"),
        (r".*tapete.*higi[eê]nico.*", "tapete higiênico"),
        (r".*arranhador.*gato.*", "arranhador para gatos"),
    ]
    for p, out in patterns:
        if re.match(p, n):
            return out

    tokens = []
    for t in re.findall(r"[a-záàâãéêíóôõúç0-9]+", n):
        if t in TITLE_NOISE or len(t) <= 2:
            continue
        if t not in tokens:
            tokens.append(t)

    # Keep first 3-5 meaningful commercial tokens.
    return " ".join(tokens[:5]) or n

def _name_variants(name):
    clean = _clean_product_name(name)
    core = _core_phrase(name)
    variants = []

    for v in [core, clean]:
        if v and v not in variants:
            variants.append(v)

    n = _norm(core)
    mappings = {
        "organizador de panelas": [
            "suporte para panelas",
            "organizador aramado para panelas",
            "porta panelas",
            "organizador de tampas e panelas",
        ],
        "organizador de geladeira": [
            "organizador para geladeira",
            "cesto organizador geladeira",
            "caixa organizadora geladeira",
        ],
        "escorredor de cozinha": [
            "escorredor de louças",
            "escorredor de utensílios",
        ],
        "tapete higiênico": [
            "tapete higiênico cachorro",
            "tapete absorvente pet",
        ],
        "arranhador para gatos": [
            "arranhador adesivo gato",
            "protetor arranhador gato",
        ],
    }

    for key, vals in mappings.items():
        if key in n:
            for v in vals:
                if v not in variants:
                    variants.append(v)

    return variants[:6]

def _extract_brl(text):
    vals=[]
    pattern=r"R\$\s*([0-9]{1,6}(?:\.[0-9]{3})*(?:,[0-9]{1,2})?|[0-9]{1,6}(?:\.[0-9]{1,2})?)"
    for raw in re.findall(pattern,text or "",flags=re.I):
        s=raw.strip()
        if "," in s:
            s=s.replace(".","").replace(",",".")
        else:
            parts=s.split(".")
            if len(parts)>2:
                s="".join(parts)
            elif len(parts)==2 and len(parts[1])==3:
                s="".join(parts)
        try:
            v=float(s)
        except Exception:
            continue
        if 1 <= v <= 50000:
            vals.append(round(v,2))
    return vals

def _extract_moq(text):
    t=_norm(text)
    patterns=[
        r"(?:pedido mínimo|pedido minimo|lote mínimo|lote minimo|mínimo|minimo)\D{0,15}(\d{1,5})\s*(?:un|unid|unidades|pcs|peças|pecas)?",
        r"caixa\s+com\s+(\d{1,5})",
        r"pacote\s+com\s+(\d{1,5})",
        r"fardo\s+com\s+(\d{1,5})",
    ]
    for p in patterns:
        m=re.search(p,t)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return None

def _supplier_likelihood(title,desc,domain):
    text=_norm(f"{title} {desc}")
    score=0
    strong_hits=sum(1 for w in STRONG_SUPPLIER_SIGNALS if w in text)
    weak_hits=sum(1 for w in SUPPLIER_WORDS if w in text)

    score += strong_hits * 3
    score += min(3, weak_hits)

    if any(x in domain for x in ("atacado","distrib","fornecedor","fabric","b2b","import")):
        score += 3
    if any(x in text for x in EXCLUDE_HINTS):
        score -= 3
    return score

def _supplier_status(title,desc,domain):
    score=_supplier_likelihood(title,desc,domain)
    text=_norm(f"{title} {desc}")
    strong=sum(1 for w in STRONG_SUPPLIER_SIGNALS if w in text)
    if score >= 7 and strong >= 1:
        return "✅ Confirmado"
    if score >= 3:
        return "🟡 Possível"
    return "⚪ Fraco"

def build_supplier_queries(product_name,max_queries=6):
    variants=_name_variants(product_name)
    queries=[]

    # Start with short commercial names, not the Shopee title.
    for v in variants:
        queries.extend([
            f'{v} atacado',
            f'{v} distribuidor Brasil',
            f'{v} fabricante Brasil',
            f'{v} fornecedor para lojista',
            f'{v} caixa fechada preço',
            f'{v} revenda b2b',
        ])

    # Add broad category-style queries to catch sites that don't repeat exact product wording.
    core=_core_phrase(product_name)
    broad = [
        f'atacado {core}',
        f'distribuidora {core}',
        f'fábrica {core}',
        f'fornecedor utilidades domésticas {core}',
    ]
    queries.extend(broad)

    seen=[]; used=set()
    for q in queries:
        q=re.sub(r"\s+"," ",q).strip()
        if q not in used:
            seen.append(q); used.add(q)

    return seen[:max(4,min(12,int(max_queries)))]

def hunt_suppliers(product_name,max_queries=6,results_per_query=8):
    collector=BraveSearchCollector(count=max(4,min(15,int(results_per_query))))
    if not collector.enabled():
        return {"enabled":False,"message":"BRAVE_SEARCH_API_KEY não configurada."}

    queries=build_supplier_queries(product_name,max_queries)
    rows=[]; seen=set(); errors=[]

    for q in queries:
        try:
            results=collector.search(q)
        except Exception as exc:
            errors.append(f"{q}: {exc}")
            continue

        for r in results:
            url=r.get("url","")
            if not url or url in seen:
                continue
            seen.add(url)

            title=r.get("title","") or ""
            desc=r.get("description","") or ""
            domain=_domain(url,r.get("source_domain",""))
            likelihood=_supplier_likelihood(title,desc,domain)

            # Broader threshold than V6.1, but status makes confidence explicit.
            if likelihood < 2:
                continue

            prices=_extract_brl(f"{title} {desc}")
            moq=_extract_moq(f"{title} {desc}")
            status=_supplier_status(title,desc,domain)

            evidence=[]
            text_all=_norm(f"{title} {desc}")
            if any(x in text_all for x in ("atacado","atacadista","venda por atacado","somente atacado")):
                evidence.append("atacado")
            if any(x in text_all for x in ("distribuidor","distribuidora")):
                evidence.append("distribuidor")
            if any(x in text_all for x in ("fabricante","fábrica","fabrica")):
                evidence.append("fabricante")
            if any(x in text_all for x in ("lojista","revendedor","revenda")):
                evidence.append("revenda/lojista")
            if any(x in text_all for x in ("pedido mínimo","pedido minimo","lote mínimo","lote minimo","caixa fechada")):
                evidence.append("mínimo/lote")
            if prices:
                evidence.append("preço público")
            if moq:
                evidence.append("MOQ identificado")

            if status=="✅ Confirmado" and prices and moq:
                confidence="Alta"
            elif status=="✅ Confirmado":
                confidence="Média"
            else:
                confidence="Baixa"

            if status=="✅ Confirmado" and prices:
                action="Comparar custo e pedir condição comercial"
            elif status=="✅ Confirmado":
                action="Solicitar cotação"
            else:
                action="Validar se vende para revenda"

            rows.append({
                "fornecedor":title[:180],
                "status_fornecedor":status,
                "confianca":confidence,
                "evidencias":", ".join(evidence) if evidence else "sinais comerciais limitados",
                "acao_sugerida":action,
                "fonte":domain,
                "score_fornecedor":min(100,35+likelihood*10),
                "preco_publico_min":min(prices) if prices else None,
                "precos_encontrados":", ".join(f"R$ {p:.2f}" for p in prices[:5]) if prices else "",
                "moq_estimado":moq,
                "descricao":desc[:350],
                "url":url,
                "consulta":q,
            })

    # Deduplicate by domain, keeping the strongest result.
    best={}
    for row in rows:
        key=row["fonte"] or row["url"]
        current=best.get(key)
        richness=(
            row["status_fornecedor"]=="✅ Confirmado",
            row["score_fornecedor"],
            bool(row["precos_encontrados"]),
            bool(row["moq_estimado"]),
        )
        if not current:
            best[key]=row
        else:
            cur_rich=(
                current["status_fornecedor"]=="✅ Confirmado",
                current["score_fornecedor"],
                bool(current["precos_encontrados"]),
                bool(current["moq_estimado"]),
            )
            if richness > cur_rich:
                best[key]=row

    suppliers=sorted(
        best.values(),
        key=lambda x:(
            x["status_fornecedor"]=="✅ Confirmado",
            x["score_fornecedor"],
            x["preco_publico_min"] is not None
        ),
        reverse=True
    )

    priced=[r["preco_publico_min"] for r in suppliers if r["preco_publico_min"]]
    stats={
        "count":len(priced),
        "min":round(min(priced),2) if priced else None,
        "median":round(median(priced),2) if priced else None,
        "max":round(max(priced),2) if priced else None,
    }

    confirmed=sum(1 for r in suppliers if r["status_fornecedor"]=="✅ Confirmado")
    possible=sum(1 for r in suppliers if r["status_fornecedor"]=="🟡 Possível")

    return {
        "enabled":True,
        "product":product_name,
        "product_core":_core_phrase(product_name),
        "queries_used":len(queries),
        "suppliers_found":len(suppliers),
        "suppliers_confirmed":confirmed,
        "suppliers_possible":possible,
        "price_stats":stats,
        "rows":suppliers,
        "errors":errors,
        "variants":_name_variants(product_name),
        "message":"Busca inteligente de fornecedores concluída."
    }
