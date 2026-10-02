
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE/"config.json").read_text(encoding="utf-8"))
WEIGHTS = CONFIG["pesos"]

def clamp(v, lo=0, hi=10):
    try: v=float(v)
    except: v=0
    return max(lo,min(hi,v))

def normalize(v, max_points):
    return round(clamp(v)/10*max_points,2)

def classify(score):
    for f in CONFIG["faixas_score"]:
        if f["min"] <= score <= f["max"]:
            return f["classe"]
    return "Sem classificação"

def financials(p):
    price=float(p.get("price_avg") or p.get("preco_venda") or 0)
    cost=float(p.get("supplier_cost") or p.get("custo_produto") or 0)
    shipping=float(p.get("shipping_in") or p.get("frete_entrada") or 0)
    packaging=float(p.get("packaging") or p.get("embalagem") or 0)
    fixed=float(p.get("marketplace_fixed") or 0)

    marketplace=float(p.get("marketplace_pct") or 0)/100
    tax=float(p.get("tax_pct") or 0)/100
    discount=float(p.get("discount_pct") or 0)/100
    losses=float(p.get("losses_pct") or 0)/100
    ads=float(p.get("ads_pct") or 0)/100
    target_margin=float(p.get("target_profit_margin_pct") or CONFIG.get("target_profit_margin_pct",12))/100

    non_ad_pct = marketplace + tax + discount + losses
    non_ad_cost = price*non_ad_pct
    contribution_before_ads = price - cost - shipping - packaging - fixed - non_ad_cost

    ad_spend_assumed = price*ads
    profit_after_ads = contribution_before_ads - ad_spend_assumed
    margin_after_ads = (profit_after_ads/price*100) if price else 0

    cac_break_even = max(0, contribution_before_ads)
    target_profit = price*target_margin
    cac_target = max(0, contribution_before_ads-target_profit)

    roas_break_even = (price/cac_break_even) if cac_break_even>0 else None
    roas_target = (price/cac_target) if cac_target>0 else None

    return {
        "profit_est": round(profit_after_ads,2),
        "margin_est_pct": round(margin_after_ads,2),
        "contribution_before_ads": round(contribution_before_ads,2),
        "cac_max_break_even": round(cac_break_even,2),
        "cac_max_target": round(cac_target,2),
        "roas_min_break_even": round(roas_break_even,2) if roas_break_even else None,
        "roas_target": round(roas_target,2) if roas_target else None
    }

def why_now(p):
    reasons=[]
    if clamp(p.get("tendencia")) >= 8: reasons.append("tendência em aceleração")
    if clamp(p.get("demanda")) >= 8: reasons.append("demanda comprovada")
    if clamp(p.get("fornecedor")) >= 8: reasons.append("fornecedor competitivo")
    if clamp(p.get("margem")) >= 8: reasons.append("margem atrativa")
    if clamp(p.get("recorrencia")) >= 8: reasons.append("forte recompra")
    if clamp(p.get("sazonalidade")) >= 8: reasons.append("janela sazonal favorável")
    return (", ".join(reasons[:4]).capitalize()+".") if reasons else "Precisa de mais validação."

def score(p):
    details={}
    total=0
    for k,w in WEIGHTS.items():
        pts=normalize(p.get(k,0),w)
        details[k]=pts
        total+=pts
    total=round(total,2)
    fin=financials(p)
    return {
        "score":total,
        "classification":classify(total),
        "why_now":why_now(p),
        "details":details,
        **fin
    }
