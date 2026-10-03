import re
from statistics import median
from urllib.parse import urlparse
from collectors.brave_search import BraveSearchCollector

SUPPLIER_WORDS = (
    "atacado","atacadista","distribuidor","distribuidora","fabricante","fábrica","fabrica",
    "fornecedor","revenda","caixa fechada","lote mínimo","lote minimo","pedido mínimo",
    "pedido minimo","lojista","b2b"
)

EXCLUDE_HINTS = (
    "blog","notícia","noticia","guia","como escolher","mais vendidos","tendência","tendencia",
    "mercado livre","amazon","magazine luiza","magalu","shopee"
)

def _norm(s):
    return re.sub(r"\s+"," ",(s or "").lower()).strip()

def _domain(url, fallback=""):
    return (fallback or urlparse(url or "").netloc or "").lower()

def _short_name(name):
    n=re.sub(r"\s+"," ",name or "").strip()
    n=re.sub(r"\b(armário|armario|cozinha|casa|ajustável|ajustavel|suporte)\b"," ",n,flags=re.I)
    n=re.sub(r"\s+"," ",n).strip(" -–—")
    return n or (name or "").strip()

def _name_variants(name):
    base=(name or "").strip()
    short=_short_name(base)
    variants=[]
    for v in [base,short]:
        if v and v not in variants:
            variants.append(v)

    simple=_norm(base)
    replacements=[
        ("organizador de panelas","suporte organizador de panelas"),
        ("organizador panelas","suporte para panelas"),
        ("organizador de geladeira","organizador para geladeira"),
        ("porta tampas","organizador de tampas"),
    ]
    for src,dst in replacements:
        if src in simple:
            cand=simple.replace(src,dst).title()
            if cand not in variants:
                variants.append(cand)
    return variants[:4]

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
    if any(w in text for w in SUPPLIER_WORDS): score += 3
    if any(x in text for x in ("cnpj","revendedores","lojistas","atendemos lojas","venda por atacado")): score += 2
    if any(x in domain for x in ("atacado","distrib","fornecedor","fabric","b2b")): score += 2
    if any(x in text for x in EXCLUDE_HINTS): score -= 2
    return score

def build_supplier_queries(product_name,max_queries=6):
    variants=_name_variants(product_name)
    queries=[]
    for v in variants:
        queries.extend([
            f'"{v}" atacado fornecedor distribuidor Brasil',
            f'"{v}" fabricante fábrica revenda Brasil',
            f'"{v}" preço atacado caixa fechada',
            f'"{v}" pedido mínimo lojista',
            f'"{v}" b2b distribuidora',
        ])
    seen=[]; used=set()
    for q in queries:
        if q not in used:
            seen.append(q); used.add(q)
    return seen[:max(4,min(10,int(max_queries)))]

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
            if likelihood < 2:
                continue

            prices=_extract_brl(f"{title} {desc}")
            moq=_extract_moq(f"{title} {desc}")
            rows.append({
                "fornecedor":title[:180],
                "fonte":domain,
                "score_fornecedor":min(100,40+likelihood*12),
                "preco_publico_min":min(prices) if prices else None,
                "precos_encontrados":", ".join(f"R$ {p:.2f}" for p in prices[:5]) if prices else "",
                "moq_estimado":moq,
                "descricao":desc[:350],
                "url":url,
                "consulta":q,
            })

    best={}
    for row in rows:
        key=row["fonte"] or row["url"]
        richness=(row["score_fornecedor"], bool(row["precos_encontrados"]), bool(row["moq_estimado"]))
        cur=best.get(key)
        if not cur:
            best[key]=row
        else:
            cur_rich=(cur["score_fornecedor"], bool(cur["precos_encontrados"]), bool(cur["moq_estimado"]))
            if richness > cur_rich:
                best[key]=row

    suppliers=sorted(best.values(),key=lambda x:(x["score_fornecedor"],x["preco_publico_min"] is not None),reverse=True)
    priced=[r["preco_publico_min"] for r in suppliers if r["preco_publico_min"]]
    stats={
        "count":len(priced),
        "min":round(min(priced),2) if priced else None,
        "median":round(median(priced),2) if priced else None,
        "max":round(max(priced),2) if priced else None,
    }

    return {
        "enabled":True,
        "product":product_name,
        "queries_used":len(queries),
        "suppliers_found":len(suppliers),
        "price_stats":stats,
        "rows":suppliers,
        "errors":errors,
        "variants":_name_variants(product_name),
        "message":"Busca de fornecedores concluída."
    }
