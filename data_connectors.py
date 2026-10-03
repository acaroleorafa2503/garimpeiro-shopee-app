import csv
import re
import unicodedata
from pathlib import Path
from statistics import median
from product_identity import compatibility_score

SHOPEE_REQUIRED=["produto","preco","vendidos","avaliacoes","loja","link"]
SUPPLIER_REQUIRED=["produto","fornecedor","custo","moq","frete","link"]

def _ascii_norm(s):
    s=(s or "").lower().strip()
    s=unicodedata.normalize("NFKD",s)
    s="".join(ch for ch in s if not unicodedata.combining(ch))
    s=re.sub(r"[^a-z0-9\s]"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _to_float(v):
    if v is None: return None
    s=str(v).strip().replace("R$","").replace(" ","")
    if not s: return None
    if "," in s: s=s.replace(".","").replace(",",".")
    try: return float(s)
    except Exception: return None

def _to_int(v):
    f=_to_float(v)
    return int(f) if f is not None else None

def _token_overlap(a,b):
    ta={t for t in _ascii_norm(a).split() if len(t)>2}
    tb={t for t in _ascii_norm(b).split() if len(t)>2}
    if not ta or not tb: return 0.0
    return len(ta & tb)/max(1,len(ta | tb))

def _combined_match_score(reference,candidate):
    ref=_ascii_norm(reference)
    cand=_ascii_norm(candidate)
    identity=compatibility_score(reference,candidate,"")
    if ref==cand: return 100
    if ref and cand and (ref in cand or cand in ref): return max(identity,90)
    overlap=_token_overlap(reference,candidate)
    if overlap>=0.75: return max(identity,90)
    if overlap>=0.55: return max(identity,75)
    if overlap>=0.40: return max(identity,60)
    return identity

def read_csv_file(path_or_file,expected_columns):
    if hasattr(path_or_file,"read"):
        content=path_or_file.read()
        if isinstance(content,bytes): content=content.decode("utf-8-sig")
        rows=list(csv.DictReader(content.splitlines()))
    else:
        with Path(path_or_file).open("r",encoding="utf-8-sig",newline="") as f:
            rows=list(csv.DictReader(f))
    cols=set(rows[0].keys()) if rows else set()
    return rows,[c for c in expected_columns if c not in cols]

def normalize_shopee_rows(rows):
    return [{
        "produto":(r.get("produto") or "").strip(),
        "preco":_to_float(r.get("preco")),
        "vendidos":_to_int(r.get("vendidos")) or 0,
        "avaliacoes":_to_int(r.get("avaliacoes")) or 0,
        "loja":(r.get("loja") or "").strip(),
        "link":(r.get("link") or "").strip(),
    } for r in rows]

def normalize_supplier_rows(rows):
    return [{
        "produto":(r.get("produto") or "").strip(),
        "fornecedor":(r.get("fornecedor") or "").strip(),
        "custo":_to_float(r.get("custo")),
        "moq":_to_int(r.get("moq")) or 0,
        "frete":_to_float(r.get("frete")) or 0,
        "link":(r.get("link") or "").strip(),
    } for r in rows]

def match_shopee(product_name,rows,min_score=70):
    matches=[]
    for r in normalize_shopee_rows(rows):
        score=_combined_match_score(product_name,r["produto"])
        if score>=min_score:
            x=dict(r); x["compatibilidade"]=score; matches.append(x)
    matches.sort(key=lambda x:(x["compatibilidade"],x["vendidos"],x["avaliacoes"]),reverse=True)
    prices=[x["preco"] for x in matches if x["preco"] and x["preco"]>0]
    return {
        "matches":matches,"count":len(matches),
        "median_price":round(median(prices),2) if prices else None,
        "min_price":round(min(prices),2) if prices else None,
        "max_price":round(max(prices),2) if prices else None,
        "total_sold":sum(x["vendidos"] for x in matches),
        "total_reviews":sum(x["avaliacoes"] for x in matches),
    }

def match_suppliers(product_name,rows,min_score=65):
    matches=[]
    for r in normalize_supplier_rows(rows):
        score=_combined_match_score(product_name,r["produto"])
        if score>=min_score:
            x=dict(r); x["compatibilidade"]=score; matches.append(x)
    matches.sort(key=lambda x:(x["compatibilidade"],-(x["custo"] or 10**9)),reverse=True)
    costs=[x["custo"] for x in matches if x["custo"] and x["custo"]>0]
    moqs=[x["moq"] for x in matches if x["moq"]]
    freights=[x["frete"] for x in matches if x["frete"] is not None]
    return {
        "matches":matches,"count":len(matches),
        "min_cost":round(min(costs),2) if costs else None,
        "median_cost":round(median(costs),2) if costs else None,
        "min_moq":min(moqs) if moqs else 0,
        "median_freight":round(median(freights),2) if freights else 0,
    }

def combine_structured_data(product_name,shopee_rows=None,supplier_rows=None):
    sh=match_shopee(product_name,shopee_rows or [])
    su=match_suppliers(product_name,supplier_rows or [])
    return {
        "product":product_name,
        "shopee":sh,
        "suppliers":su,
        "auto_sale_price":sh["median_price"],
        "auto_cost_price":su["min_cost"],
        "auto_moq":su["min_moq"],
        "auto_inbound_freight":su["median_freight"],
        "shopee_confidence":"Alta" if sh["count"]>=3 else ("Média" if sh["count"]>=1 else "Baixa"),
        "supplier_confidence":"Alta" if su["count"]>=2 else ("Média" if su["count"]>=1 else "Baixa"),
    }
