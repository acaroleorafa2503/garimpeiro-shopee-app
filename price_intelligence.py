import re
from statistics import median
from urllib.parse import urlparse
from collectors.brave_search import BraveSearchCollector

SHOPEE_DOMAINS=("shopee.com.br",)
SECONDARY_MARKETS=("mercadolivre.com.br","amazon.com.br","magazineluiza.com.br","americanas.com.br")
SUPPLIER_HINTS=("atacado","atacadista","distribuidor","distribuidora","fabricante","fábrica","fabrica","fornecedor","revenda","lojista","b2b")

def _norm(s):
    return re.sub(r"\s+"," ",(s or "").lower()).strip()

def _domain(url, fallback=""):
    return (fallback or urlparse(url or "").netloc or "").lower()

def _clean_product_name(name):
    n=re.sub(r"\s+"," ",name or "").strip()
    n=re.sub(r"\b(amazon\.com\.br|mercado livre|magazine luiza|magalu|shopee)\b"," ",n,flags=re.I)
    n=re.sub(r"\b(110v|220v|bivolt)\b"," ",n,flags=re.I)
    n=re.sub(r"\s+"," ",n).strip(" -–—|")
    return n[:120]

def _core_name(name):
    n=_norm(_clean_product_name(name))
    patterns=[
        (r".*jogo.*ferrament.*", "jogo de ferramentas"),
        (r".*kit.*ferrament.*", "kit de ferramentas"),
        (r".*organizador.*panelas.*", "organizador de panelas"),
        (r".*organizador.*geladeira.*", "organizador de geladeira"),
        (r".*tapete.*higi[eê]nico.*", "tapete higiênico"),
        (r".*arranhador.*gato.*", "arranhador para gatos"),
    ]
    for p,o in patterns:
        if re.match(p,n):
            return o
    toks=[t for t in re.findall(r"[a-záàâãéêíóôõúç0-9]+",n) if len(t)>2]
    return " ".join(toks[:5]) if toks else n

def _extract_prices(text):
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
        except:
            continue
        if 1 <= v <= 100000:
            vals.append(round(v,2))
    return vals

def _pack_qty(text):
    t=_norm(text)
    pats=[
        r"kit\s+(?:com|de)\s+(\d{1,4})\s*(?:peças|pecas|unidades|pcs)?",
        r"jogo\s+(?:com|de)\s+(\d{1,4})\s*(?:peças|pecas|unidades|pcs)?",
        r"caixa\s+com\s+(\d{1,4})\s*(?:unidades|un|pcs|peças|pecas)?",
        r"pacote\s+com\s+(\d{1,4})\s*(?:unidades|un|pcs|peças|pecas)?",
        r"(\d{1,4})\s*(?:peças|pecas|unidades|pcs)\b",
    ]
    for p in pats:
        m=re.search(p,t)
        if m:
            try:
                q=int(m.group(1))
                if 1 <= q <= 10000:
                    return q
            except:
                pass
    return None

def _source_type(domain,text):
    n=_norm(text)
    if any(d in domain for d in SHOPEE_DOMAINS) or "shopee" in n:
        return "Shopee"
    if any(h in n for h in SUPPLIER_HINTS) or any(h in domain for h in ("atacado","distrib","fornecedor","fabric")):
        return "Fornecedor"
    if any(d in domain for d in SECONDARY_MARKETS):
        return "Marketplace secundário"
    return "Fonte pública"

def build_price_queries(product_name,max_queries=8):
    p=_clean_product_name(product_name)
    core=_core_name(product_name)
    qs=[
        f'site:shopee.com.br "{p}" R$',
        f'site:shopee.com.br "{core}" preço',
        f'"{core}" Shopee preço Brasil',
        f'"{core}" Mercado Livre preço',
        f'"{core}" Amazon Brasil preço',
        f'"{core}" atacado preço fornecedor',
        f'"{core}" distribuidor preço lojista',
        f'"{core}" fabricante preço revenda',
        f'"{core}" caixa fechada preço',
        f'"{core}" kit lote preço',
    ]
    seen=[]; used=set()
    for q in qs:
        if q not in used:
            seen.append(q); used.add(q)
    return seen[:max(4,min(10,int(max_queries)))]

def _confidence(source_type, price_count, has_pack, text):
    score=0
    if source_type=="Shopee": score += 3
    elif source_type=="Fornecedor": score += 3
    elif source_type=="Marketplace secundário": score += 2
    if price_count>0: score += 2
    if has_pack: score += 1
    n=_norm(text)
    if any(x in n for x in ("a partir de","por unidade","cada","unidade","atacado")):
        score += 1
    if score>=6: return "Alta"
    if score>=4: return "Média"
    return "Baixa"

def analyze_price_cost(product_name,max_queries=8,results_per_query=8):
    collector=BraveSearchCollector(count=max(4,min(15,int(results_per_query))))
    if not collector.enabled():
        return {"enabled":False,"message":"BRAVE_SEARCH_API_KEY não configurada."}

    queries=build_price_queries(product_name,max_queries)
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
            text=f"{title} {desc}"
            stype=_source_type(domain,text)
            prices=_extract_prices(text)
            qty=_pack_qty(text)

            if not prices:
                continue

            # Avoid silently converting a kit/lote price into unit cost.
            unit_prices=[]
            if qty and qty>1 and any(x in _norm(text) for x in ("caixa com","pacote com","lote","por unidade","cada")):
                # Preserve raw total price and derived unit equivalent separately.
                unit_prices=[round(p/qty,2) for p in prices]
            elif qty and qty>1 and stype=="Fornecedor" and any(x in _norm(text) for x in ("caixa","pacote","lote")):
                unit_prices=[round(p/qty,2) for p in prices]

            rows.append({
                "tipo":stype,
                "titulo":title[:180],
                "fonte":domain,
                "precos_brutos":", ".join(f"R$ {p:.2f}" for p in prices[:5]),
                "_precos_numericos":prices,
                "quantidade_lote":qty,
                "preco_unitario_derivado":min(unit_prices) if unit_prices else None,
                "confianca":_confidence(stype,len(prices),bool(qty),text),
                "descricao":desc[:350],
                "url":url,
                "consulta":q,
            })

    shopee=[]
    suppliers=[]
    secondary=[]

    for row in rows:
        raw=list(row.get("_precos_numericos") or [])
        usable=[]
        if row["preco_unitario_derivado"]:
            usable=[row["preco_unitario_derivado"]]
        else:
            usable=raw
        if row["tipo"]=="Shopee":
            shopee.extend(usable)
        elif row["tipo"]=="Fornecedor":
            suppliers.extend(usable)
        elif row["tipo"]=="Marketplace secundário":
            secondary.extend(usable)

    def stats(vals):
        vals=sorted(v for v in vals if v>0)
        if not vals:
            return {"count":0,"min":None,"median":None,"max":None}
        return {
            "count":len(vals),
            "min":round(min(vals),2),
            "median":round(median(vals),2),
            "max":round(max(vals),2),
        }

    sh=stats(shopee)
    su=stats(suppliers)
    se=stats(secondary)

    auto_sale = sh["median"] if sh["count"]>=1 else (se["median"] if se["count"]>=2 else None)
    auto_cost = su["min"] if su["count"]>=1 else None

    sale_conf="Baixa"
    if sh["count"]>=3: sale_conf="Alta"
    elif sh["count"]>=1: sale_conf="Média"
    elif se["count"]>=2: sale_conf="Baixa"

    cost_conf="Baixa"
    if su["count"]>=3: cost_conf="Alta"
    elif su["count"]>=1: cost_conf="Média"

    return {
        "enabled":True,
        "product":product_name,
        "core_name":_core_name(product_name),
        "queries_used":len(queries),
        "rows":rows,
        "shopee_stats":sh,
        "supplier_stats":su,
        "secondary_stats":se,
        "auto_sale_price":auto_sale,
        "auto_cost_price":auto_cost,
        "sale_confidence":sale_conf,
        "cost_confidence":cost_conf,
        "errors":errors,
        "message":"Inteligência de preço e custo concluída."
    }
