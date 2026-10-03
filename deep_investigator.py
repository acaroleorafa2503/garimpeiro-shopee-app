import re
from statistics import median
from urllib.parse import urlparse
from collectors.brave_search import BraveSearchCollector

SHOPEE_DOMAINS = ("shopee.com.br",)
SECONDARY_MARKETPLACE_DOMAINS = (
    "mercadolivre.com.br","amazon.com.br","magazineluiza.com.br","americanas.com.br"
)
SUPPLIER_WORDS = (
    "atacado","distribuidor","distribuidora","fabricante","fábrica","fabrica",
    "fornecedor","revenda","caixa fechada"
)

def _norm(s):
    return re.sub(r"\s+"," ",(s or "").lower()).strip()

def _domain(url, fallback=""):
    return (fallback or urlparse(url or "").netloc or "").lower()

def _source_type(domain, text):
    n = _norm(text)
    if any(d in domain for d in SHOPEE_DOMAINS) or "shopee" in n:
        return "Shopee"
    if any(w in n for w in SUPPLIER_WORDS):
        return "Fornecedor"
    if any(d in domain for d in SECONDARY_MARKETPLACE_DOMAINS):
        return "Marketplace secundário"
    return "Fonte pública"

def _extract_brl(text):
    if not text:
        return []
    vals=[]
    # Only explicit currency values, avoiding years/model numbers.
    pattern=r"R\$\s*([0-9]{1,5}(?:\.[0-9]{3})*(?:,[0-9]{1,2})?|[0-9]{1,5}(?:\.[0-9]{1,2})?)"
    for raw in re.findall(pattern, text, flags=re.I):
        s=raw.strip()
        # Brazilian thousand separator + decimal comma
        if "," in s:
            s=s.replace(".","").replace(",",".")
        else:
            # Ambiguous dots: treat one/two decimals as decimal, otherwise thousands.
            parts=s.split(".")
            if len(parts)>2:
                s="".join(parts)
            elif len(parts)==2 and len(parts[1])==3:
                s="".join(parts)
        try:
            v=float(s)
        except Exception:
            continue
        if 2 <= v <= 20000:
            vals.append(round(v,2))
    return vals

def _price_stats(values):
    vals=sorted(set(round(float(v),2) for v in values if v and v > 0))
    if not vals:
        return {"count":0,"min":None,"median":None,"max":None}
    return {
        "count":len(vals),
        "min":round(vals[0],2),
        "median":round(median(vals),2),
        "max":round(vals[-1],2),
    }

def build_investigation_queries(product_name, max_queries=5):
    p=product_name.strip()
    queries=[
        f'site:shopee.com.br "{p}"',
        f'"{p}" Shopee Brasil avaliações vendidos',
        f'"{p}" atacado fornecedor distribuidor fabricante Brasil',
        f'"{p}" preço atacado caixa fechada Brasil',
        f'"{p}" Mercado Livre Amazon preço Brasil',
        f'"{p}" tendência procura sazonalidade Brasil',
    ]
    return queries[:max(3,min(6,int(max_queries)))]

def _decision(score, shopee_count, supplier_count):
    if shopee_count >= 1 and supplier_count >= 1 and score >= 78:
        return "✅ AVANÇAR PARA COTAÇÃO REAL"
    if shopee_count >= 1 and supplier_count == 0:
        return "🟡 PROCURAR FORNECEDOR"
    if shopee_count == 0:
        return "🟠 CONFIRMAR DEMANDA NA SHOPEE"
    return "🟡 CONTINUAR INVESTIGAÇÃO"

def investigate_product(product_name, max_queries=5, results_per_query=8):
    collector=BraveSearchCollector(count=max(3,min(15,int(results_per_query))))
    if not collector.enabled():
        return {"enabled":False,"message":"BRAVE_SEARCH_API_KEY não configurada."}

    queries=build_investigation_queries(product_name,max_queries)
    rows=[]
    seen=set()
    errors=[]
    shopee_prices=[]
    supplier_prices=[]
    secondary_prices=[]

    for query in queries:
        try:
            results=collector.search(query)
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            continue

        for r in results:
            url=r.get("url","")
            if not url or url in seen:
                continue
            seen.add(url)
            title=r.get("title","") or ""
            desc=r.get("description","") or ""
            domain=_domain(url,r.get("source_domain",""))
            stype=_source_type(domain,f"{title} {desc}")
            prices=_extract_brl(f"{title} {desc}")

            if stype=="Shopee":
                shopee_prices.extend(prices)
            elif stype=="Fornecedor":
                supplier_prices.extend(prices)
            elif stype=="Marketplace secundário":
                secondary_prices.extend(prices)

            rows.append({
                "tipo":stype,
                "titulo":title[:180],
                "fonte":domain,
                "precos_encontrados":", ".join(f"R$ {x:.2f}" for x in prices[:5]) if prices else "",
                "descricao":desc[:350],
                "url":url,
                "consulta":query,
                "rank":r.get("rank"),
            })

    shopee_rows=[r for r in rows if r["tipo"]=="Shopee"]
    supplier_rows=[r for r in rows if r["tipo"]=="Fornecedor"]
    secondary_rows=[r for r in rows if r["tipo"]=="Marketplace secundário"]

    sp=_price_stats(shopee_prices)
    fp=_price_stats(supplier_prices)
    mp=_price_stats(secondary_prices)

    score=25
    reasons=[]
    if shopee_rows:
        score += min(30, 14 + 4*min(4,len(shopee_rows)))
        reasons.append(f"{len(shopee_rows)} evidência(s) Shopee")
    if supplier_rows:
        score += min(22, 10 + 3*min(4,len(supplier_rows)))
        reasons.append(f"{len(supplier_rows)} fonte(s) de fornecedor")
    if secondary_rows:
        score += min(10,2*min(5,len(secondary_rows)))
        reasons.append(f"{len(secondary_rows)} confirmação(ões) secundária(s)")

    gross_spread_pct=None
    if sp["median"] and fp["min"] and sp["median"] > 0:
        gross_spread_pct=round((sp["median"]-fp["min"])/sp["median"]*100,2)
        if gross_spread_pct >= 45:
            score += 15; reasons.append("spread bruto preliminar forte")
        elif gross_spread_pct >= 25:
            score += 8; reasons.append("spread bruto preliminar moderado")
        elif gross_spread_pct > 0:
            score += 2; reasons.append("spread bruto preliminar apertado")

    score=min(100,score)
    decision=_decision(score,len(shopee_rows),len(supplier_rows))

    confidence="Baixa"
    if len(shopee_rows)>=2 and len(supplier_rows)>=2:
        confidence="Alta"
    elif len(shopee_rows)>=1 and len(supplier_rows)>=1:
        confidence="Média"

    return {
        "enabled":True,
        "product":product_name,
        "queries_used":len(queries),
        "score_investigacao":score,
        "decisao_preliminar":decision,
        "confianca":confidence,
        "motivos":reasons,
        "shopee_evidencias":len(shopee_rows),
        "fornecedores_encontrados":len(supplier_rows),
        "confirmacoes_secundarias":len(secondary_rows),
        "preco_shopee":sp,
        "preco_fornecedor":fp,
        "preco_secundario":mp,
        "spread_bruto_pct":gross_spread_pct,
        "rows":rows,
        "supplier_rows":supplier_rows,
        "shopee_rows":shopee_rows,
        "secondary_rows":secondary_rows,
        "errors":errors,
        "warning":"Faixas de preço são extraídas de trechos públicos e podem conter promoções, kits ou variações. Spread bruto não é margem líquida: ainda faltam taxas Shopee, frete, impostos, Ads, embalagem e devoluções."
    }
