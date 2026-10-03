import json
import os
import urllib.request
import urllib.error
from statistics import median

ENDPOINT = "https://api.nexscope.ai/api/skill-api/v1/skills/shopee-product-search/run"

ORDER_LABELS = {
    "Mais vendidos (30 dias)": "sold",
    "Mais vendidos históricos": "historical_sold",
    "Maior faturamento (30 dias)": "payment",
    "Melhor avaliação": "rating",
    "Mais avaliações": "ratings",
    "Mais favoritos": "favorite",
    "Mais recentes": "gen_time",
    "Preço": "price",
}

def enabled():
    return bool(os.getenv("NEXSCOPE_API_KEY"))

def _num(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

def _int(v, default=0):
    try:
        if v is None:
            return default
        return int(float(v))
    except Exception:
        return default

def score_product(p):
    sold=max(0,_int(p.get("sold")))
    hist=max(0,_int(p.get("historicalSold")))
    ratings=max(0,_int(p.get("ratings")))
    rating=max(0.0,_num(p.get("rating"),0.0))
    favorite=max(0,_int(p.get("favorite")))
    stock=max(0,_int(p.get("stock")))
    payment=max(0.0,_num(p.get("payment"),0.0))

    score=35
    reasons=[]
    if sold>=1000:
        score+=22; reasons.append("vendas 30d muito fortes")
    elif sold>=300:
        score+=16; reasons.append("vendas 30d fortes")
    elif sold>=100:
        score+=10; reasons.append("vendas 30d relevantes")
    elif sold>=20:
        score+=5; reasons.append("vendas 30d presentes")

    if hist>=5000:
        score+=12; reasons.append("histórico consolidado")
    elif hist>=1000:
        score+=8; reasons.append("bom histórico")

    if rating>=4.8 and ratings>=100:
        score+=8; reasons.append("avaliação forte")
    elif rating>=4.5 and ratings>=30:
        score+=4; reasons.append("boa avaliação")

    if ratings>=500:
        score+=6; reasons.append("muitas avaliações")
    elif ratings>=100:
        score+=3; reasons.append("base de avaliações")

    if favorite>=500:
        score+=5; reasons.append("muitos favoritos")
    if payment>0:
        score+=4; reasons.append("faturamento 30d disponível")
    if stock==0:
        score-=10; reasons.append("estoque zerado")

    return max(0,min(100,score)), reasons[:6]

def classify(score):
    if score>=85: return "💎 Sinal forte"
    if score>=75: return "🟢 Investigar"
    if score>=60: return "🟡 Radar"
    return "⚪ Fraco"

def search_products(
    keyword,
    station="BR",
    page=1,
    page_size=20,
    keyword_type=2,
    order_by="sold",
    order_by_type="DESC",
    price_min=None,
    price_max=None,
    sold_min=None,
    rating_min=None,
    local_only=False,
):
    key=os.getenv("NEXSCOPE_API_KEY")
    if not key:
        return {"ok":False,"error":"NEXSCOPE_API_KEY não configurada.","products":[]}

    payload={
        "station":station,
        "page":int(page),
        "keyword":(keyword or "").strip(),
        "keywordType":int(keyword_type),
        "pageSize":int(page_size),
        "orderBy":order_by,
        "orderByType":order_by_type,
    }
    if price_min is not None and float(price_min)>0: payload["priceMin"]=float(price_min)
    if price_max is not None and float(price_max)>0: payload["priceMax"]=float(price_max)
    if sold_min is not None and int(sold_min)>0: payload["soldMin"]=int(sold_min)
    if rating_min is not None and float(rating_min)>0: payload["ratingMin"]=float(rating_min)
    if local_only: payload["cbOption"]=0

    req=urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization":f"Bearer {key}",
            "Content-Type":"application/json",
            "User-Agent":"GarimpeiroShopee/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req,timeout=45) as resp:
            raw=resp.read().decode("utf-8","replace")
            http_status=getattr(resp,"status",200)
    except urllib.error.HTTPError as exc:
        body=exc.read().decode("utf-8","replace")
        return {"ok":False,"http_status":exc.code,"error":body[:1500],"products":[]}
    except Exception as exc:
        return {"ok":False,"error":str(exc),"products":[]}

    try:
        envelope=json.loads(raw)
    except Exception:
        return {"ok":False,"http_status":http_status,"error":"Resposta não-JSON da Nexscope.","products":[]}

    if envelope.get("code")!=0:
        return {
            "ok":False,
            "http_status":http_status,
            "error":envelope.get("msg") or f"Código Nexscope {envelope.get('code')}",
            "products":[],
        }

    data=envelope.get("data") or {}
    products=[]
    for p in data.get("products") or []:
        score,reasons=score_product(p)
        title=p.get("title") or p.get("description") or f"Produto {p.get('pid','')}"
        products.append({
            "score_shopee":score,
            "classificacao":classify(score),
            "produto":title,
            "preco":_num(p.get("price")),
            "preco_min":_num(p.get("minPrice")),
            "preco_max":_num(p.get("maxPrice")),
            "vendidos_30d":_int(p.get("sold")),
            "vendidos_estimados_30d":_int(p.get("estimateSold")),
            "vendidos_historicos":_int(p.get("historicalSold")),
            "faturamento_30d":_num(p.get("payment")),
            "avaliacao":_num(p.get("rating")),
            "qtd_avaliacoes":_int(p.get("ratings")),
            "favoritos":_int(p.get("favorite")),
            "visualizacoes":_int(p.get("viewCount")),
            "estoque":_int(p.get("stock")),
            "skus":_int(p.get("skuNumber")),
            "loja":p.get("shopName") or p.get("userName") or "",
            "local_loja":p.get("shopLocation") or "",
            "oficial":"Sim" if _int(p.get("isOfficialShop"))==1 else "Não",
            "preferida":"Sim" if _int(p.get("isShopeeVerified"))==1 else "Não",
            "cross_border":"Sim" if _int(p.get("cbOption"))==1 else "Não",
            "categoria":p.get("categoryStructure") or "",
            "pid":str(p.get("pid") or ""),
            "shop_id":str(p.get("shopId") or ""),
            "imagem":p.get("imageUrl") or "",
            "url":p.get("shopeeUrl") or p.get("productUrl") or "",
            "por_que":", ".join(reasons),
        })

    products.sort(key=lambda x:x["score_shopee"],reverse=True)

    prices=[p["preco"] for p in products if isinstance(p.get("preco"),(int,float)) and p["preco"]>0]
    solds=[p["vendidos_30d"] for p in products]
    ratings=[p["avaliacao"] for p in products if isinstance(p.get("avaliacao"),(int,float)) and p["avaliacao"]>0]

    return {
        "ok":True,
        "products":products,
        "summary":{
            "total":data.get("total"),
            "total_size":data.get("totalSize"),
            "page":data.get("page") or payload["page"],
            "page_size":data.get("pageSize") or payload["pageSize"],
            "source_type":data.get("sourceType"),
            "cost_token":data.get("costToken"),
            "median_price":round(median(prices),2) if prices else None,
            "median_sold_30d":int(median(solds)) if solds else 0,
            "median_rating":round(median(ratings),2) if ratings else None,
        },
        "payload":payload,
        "time":envelope.get("time"),
        "trace_id":envelope.get("traceId"),
    }

def as_structured_shopee_rows(result):
    return [{
        "produto":p.get("produto",""),
        "preco":p.get("preco"),
        "vendidos":p.get("vendidos_30d",0),
        "avaliacoes":p.get("qtd_avaliacoes",0),
        "loja":p.get("loja",""),
        "link":p.get("url",""),
    } for p in result.get("products",[])]
