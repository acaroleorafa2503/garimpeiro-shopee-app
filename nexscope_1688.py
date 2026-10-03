import json
import os
import re
import urllib.request
import urllib.error
from statistics import median

ENDPOINT = "https://api.nexscope.ai/api/skill-api/v1/skills/1688-product-search/run"

SORT_LABELS = {
    "Mais pedidos — 30 dias": "orderCount30d",
    "Mais unidades vendidas — 30 dias": "saleCount30d",
    "Maior volume de vendas — 30 dias": "saleVolume30d",
    "Mais pedidos — 7 dias": "orderCount7d",
    "Mais unidades vendidas — 7 dias": "saleCount7d",
    "Maior volume de vendas — 7 dias": "saleVolume7d",
    "Mais recentes": "offerCreateTime",
    "Menor preço": "price",
    "Menor preço dropshipping": "consignPrice",
}

# Common ecommerce concepts. This creates a sourcing query, not a full translation.
PHRASES = [
    (("suporte", "celular", "carro"), "车载手机支架"),
    (("suporte", "celular", "veicular"), "车载手机支架"),
    (("suporte", "magnetico", "celular"), "磁吸手机支架"),
    (("organizador", "panelas"), "锅具收纳架"),
    (("tapete", "higienico", "cachorro"), "宠物尿垫"),
    (("tapete", "higienico", "caes"), "宠物尿垫"),
    (("arranhador", "gato"), "猫抓板"),
    (("protetor", "adesivo", "gato"), "猫抓贴"),
    (("coleira", "cachorro"), "狗项圈"),
    (("coleira", "pet"), "宠物项圈"),
    (("guia", "retratil", "cachorro"), "伸缩狗牵引绳"),
    (("organizador", "geladeira"), "冰箱收纳盒"),
]

FEATURES = [
    (("magnetico", "magnético", "ima", "ímã"), "磁吸"),
    (("360", "360°"), "360度"),
    (("dobravel", "dobrável"), "折叠"),
    (("articulado", "articulada"), "可调节"),
    (("dupla", "face"), "双面"),
    (("ventosa",), "吸盘"),
    (("adesivo", "adesiva"), "自粘"),
    (("retratil", "retrátil"), "伸缩"),
    (("impermeavel", "impermeável"), "防水"),
    (("ajustavel", "ajustável"), "可调节"),
]

def _norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii","ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9° ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def suggest_chinese_keyword(product_name):
    n = _norm(product_name)
    base = ""
    for keys, zh in PHRASES:
        if all(_norm(k) in n for k in keys):
            base = zh
            break

    extras = []
    for keys, zh in FEATURES:
        if any(_norm(k) in n for k in keys):
            if zh not in base and zh not in extras:
                extras.append(zh)

    if base:
        return base + "".join(extras[:3])

    # Broad fallback based on known commercial nouns.
    pieces = []
    noun_map = [
        ("celular","手机"), ("carro","车载"), ("veicular","车载"),
        ("suporte","支架"), ("organizador","收纳架"), ("pet","宠物"),
        ("cachorro","狗"), ("gato","猫"), ("coleira","项圈"),
        ("tapete","垫"), ("cozinha","厨房"), ("geladeira","冰箱"),
    ]
    for pt, zh in noun_map:
        if pt in n and zh not in pieces:
            pieces.append(zh)
    pieces.extend([x for x in extras if x not in pieces])
    return "".join(pieces[:5])

def _num(v, default=None):
    try:
        if v in (None, ""): return default
        return float(v)
    except Exception:
        return default

def _int(v, default=0):
    try:
        if v in (None, ""): return default
        return int(float(v))
    except Exception:
        return default

def _han_chars(s):
    return set(re.findall(r"[\u4e00-\u9fff]", str(s or "")))

def compatibility(query_zh, title_zh):
    q = _han_chars(query_zh)
    t = _han_chars(title_zh)
    if not q or not t:
        return 0
    # Query-coverage score: useful for ensuring core sourcing phrase appears.
    return round(100 * len(q & t) / len(q))

def search_1688(
    keyword_zh,
    page_index=1,
    page_size=20,
    search_type=1,
    sort_field="orderCount30d",
    sort_type="desc",
    begin_price=None,
    end_price=None,
    cycle="30",
):
    key = os.getenv("NEXSCOPE_API_KEY")
    if not key:
        return {"ok":False, "error":"NEXSCOPE_API_KEY não configurada.", "products":[]}

    keyword_zh = (keyword_zh or "").strip()
    if not keyword_zh:
        return {"ok":False, "error":"Informe o termo de busca em chinês simplificado.", "products":[]}

    payload = {
        "keyWord": keyword_zh[:50],
        "searchType": int(search_type),
        "pageIndex": int(page_index),
        "pageSize": int(page_size),
        "sortField": sort_field,
        "sortType": sort_type,
        "cycle": str(cycle),
    }
    if begin_price is not None and float(begin_price) > 0:
        payload["beginPrice"] = float(begin_price)
    if end_price is not None and float(end_price) > 0:
        payload["endPrice"] = float(end_price)

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "GarimpeiroShopee/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8","replace")
            http_status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8","replace")
        return {"ok":False,"http_status":exc.code,"error":body[:1500],"products":[]}
    except Exception as exc:
        return {"ok":False,"error":str(exc),"products":[]}

    try:
        envelope = json.loads(raw)
    except Exception:
        return {"ok":False,"http_status":http_status,"error":"Resposta não-JSON da Nexscope.","products":[]}

    # Nexscope docs show both direct-business and envelope-style variants.
    if isinstance(envelope, dict) and "code" in envelope and envelope.get("code") not in (0, None):
        return {"ok":False,"error":envelope.get("msg") or f"Código Nexscope {envelope.get('code')}","products":[]}

    business = envelope.get("data") if isinstance(envelope, dict) and isinstance(envelope.get("data"), dict) else envelope
    if not isinstance(business, dict):
        return {"ok":False,"error":"Formato inesperado da resposta 1688.","products":[]}

    raw_products = business.get("products") or []
    products = []
    for p in raw_products:
        title = p.get("title") or ""
        compat = compatibility(keyword_zh, title)
        price = _num(p.get("price"))
        consign = _num(p.get("consignPrice"))
        moq = _int(p.get("quantityBegin"), 0)
        company = p.get("company") or p.get("companyName") or ""
        url = p.get("asinUrl") or p.get("shopUrl") or ""
        status = "✅ Compatível" if compat >= 70 else ("🟡 Possível" if compat >= 45 else "⚪ Fraco")
        products.append({
            "status": status,
            "compatibilidade": compat,
            "titulo_1688": title,
            "preco_atacado": price,
            "preco_dropship": consign,
            "faixa_preco": p.get("quantityPrices") or "",
            "moq": moq,
            "unidade": p.get("unit") or "",
            "moeda": p.get("currency") or "CNY",
            "pedidos": _int(p.get("salesOrderCount")),
            "unidades_vendidas": _int(p.get("salesQuantity")),
            "vendas_estimadas": _num(p.get("estimatedSalesAmount")),
            "prazo_entrega": p.get("deliveryTime") or "",
            "empresa": company,
            "offer_id": str(p.get("offerId") or ""),
            "link": url,
            "imagem": p.get("imageUrl") or "",
        })

    products.sort(key=lambda x:(x["compatibilidade"], x["pedidos"], x["unidades_vendidas"]), reverse=True)

    compatible = [p for p in products if p["compatibilidade"] >= 70]
    prices = [p["preco_atacado"] for p in compatible if isinstance(p.get("preco_atacado"), (int,float)) and p["preco_atacado"] > 0]
    return {
        "ok":True,
        "products":products,
        "summary":{
            "total": business.get("total"),
            "returned": len(products),
            "compatible": len(compatible),
            "possible": len([p for p in products if 45 <= p["compatibilidade"] < 70]),
            "median_wholesale_cny": round(median(prices),2) if prices else None,
            "min_wholesale_cny": round(min(prices),2) if prices else None,
        },
        "payload":payload,
    }
