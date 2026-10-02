
import json, statistics
from pathlib import Path
from datetime import datetime
from db import products, performance, history, suppliers, inventory, save_portfolio_action
from analytics import seasonal_window

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))

def safe_div(a,b):
    return a/b if b not in (0,None) else None

def aggregate_perf(rows):
    if not rows:
        return None
    impressions=sum(r["impressions"] or 0 for r in rows)
    clicks=sum(r["clicks"] or 0 for r in rows)
    orders=sum(r["orders"] or 0 for r in rows)
    revenue=sum(r["revenue"] or 0 for r in rows)
    ad_spend=sum(r["ad_spend"] or 0 for r in rows)
    returns=sum(r["returns"] or 0 for r in rows)
    profit=sum(r["profit_real"] or 0 for r in rows)
    unique_days=max(1,len(set(r["date"] for r in rows)))
    return {
        "days": unique_days,
        "impressions":impressions,
        "clicks":clicks,
        "orders":orders,
        "revenue":revenue,
        "ad_spend":ad_spend,
        "returns":returns,
        "profit":profit,
        "ctr":safe_div(clicks,impressions)*100 if impressions else 0,
        "conversion_rate":safe_div(orders,clicks)*100 if clicks else 0,
        "cac":safe_div(ad_spend,orders),
        "roas":safe_div(revenue,ad_spend),
        "return_rate":safe_div(returns,orders)*100 if orders else 0,
        "profit_margin":safe_div(profit,revenue)*100 if revenue else 0,
        "orders_per_day":orders/unique_days
    }

def supplier_opportunity(product_id):
    rows=suppliers(product_id)
    costs=sorted([float(r["unit_cost"]) for r in rows if r.get("unit_cost") not in (None,0)])
    if len(costs)<2:
        return None
    best=costs[0]; second=costs[1]
    gain=(second-best)/second*100 if second else 0
    return {"best":best,"second":second,"gain_pct":gain}

def stock_metrics(product_id, orders_per_day):
    inv=inventory(product_id)
    if not inv:
        return None
    i=inv[0]
    stock=float(i.get("stock_on_hand") or 0)+float(i.get("stock_inbound") or 0)
    cover=stock/orders_per_day if orders_per_day and orders_per_day>0 else None
    reorder_lead=float(i.get("reorder_lead_days") or 0)
    safety=float(i.get("safety_stock_days") or 7)
    return {
        "stock_total":stock,
        "cover_days":cover,
        "reorder_lead_days":reorder_lead,
        "safety_stock_days":safety
    }

def choose_action(product, snapshot, perf, supplier_op, stock):
    cfg=CONFIG["portfolio"]
    score=float(snapshot.get("score") or 0)
    margin=float(perf.get("profit_margin") or 0)
    roas=perf.get("roas")
    roas_target=snapshot.get("roas_target")
    days=perf.get("days",0)

    # Seasonal preparation can be recommended even with little performance data.
    sw=seasonal_window(product.get("peak_months",""))
    if sw["days_to_peak"] is not None and sw["days_to_peak"] <= cfg["seasonal_prepare_days"]:
        if stock is None or (stock.get("cover_days") is not None and stock["cover_days"] < cfg["seasonal_prepare_days"]):
            return ("PREPARAR SAZONALIDADE","alta",0.85,
                    f"Próximo pico em cerca de {sw['days_to_peak']} dias; revisar estoque, fornecedor e anúncio antes da alta.")

    # Critical stock signal
    if stock and stock.get("cover_days") is not None:
        threshold=max(cfg["stockout_risk_days"], stock.get("reorder_lead_days",0)+stock.get("safety_stock_days",7))
        if stock["cover_days"] <= threshold:
            return ("RECOMPRAR ESTOQUE","alta",0.95,
                    f"Estoque cobre cerca de {stock['cover_days']:.1f} dias, abaixo do necessário para prazo de reposição + segurança.")

    # Supplier swap opportunity
    if supplier_op and supplier_op["gain_pct"] >= cfg["supplier_switch_margin_min_gain_pct"]:
        return ("TROCAR FORNECEDOR","media",0.80,
                f"Melhor cotação está aproximadamente {supplier_op['gain_pct']:.1f}% abaixo da segunda melhor.")

    if days < cfg["min_days_for_action"]:
        return ("MANTER","baixa",0.50,
                f"Ainda há apenas {days} dia(s) de desempenho; acumular mais dados antes de alterar a operação.")

    # Pause
    if margin <= cfg["pause_margin_max_pct"]:
        return ("PAUSAR","alta",0.95,
                f"Margem real está em {margin:.1f}% e o produto não está gerando lucro.")
    if roas is not None and roas_target not in (None,0) and roas < float(roas_target)*cfg["pause_roas_factor_vs_target"]:
        return ("PAUSAR","alta",0.90,
                f"ROAS real {roas:.2f} está muito abaixo do alvo {float(roas_target):.2f}.")

    # Scale
    if score >= cfg["scale_score_min"] and margin >= cfg["scale_margin_min_pct"]:
        if roas_target in (None,0) or (roas is not None and roas >= float(roas_target)*cfg["scale_roas_factor_vs_target"]):
            return ("ESCALAR","alta",0.90,
                    f"Score {score:.1f}, margem real {margin:.1f}% e ROAS compatível com o alvo.")

    # Reduce
    if roas is not None and roas_target not in (None,0) and roas < float(roas_target)*cfg["reduce_roas_factor_vs_target"]:
        return ("REDUZIR","media",0.80,
                f"ROAS real {roas:.2f} está abaixo do alvo {float(roas_target):.2f}; reduzir exposição e revisar oferta.")

    return ("MANTER","media",0.75,
            f"Produto está operacionalmente saudável, mas ainda não reuniu critérios suficientes para escalar.")

def run_portfolio():
    actions=[]
    perf_all=performance(limit=100000)
    by_product={}
    for r in perf_all:
        by_product.setdefault(r["product_id"],[]).append(r)

    for p in products():
        hist=history(p["id"],limit=1)
        if not hist:
            continue
        snap=hist[0]
        perf=aggregate_perf(by_product.get(p["id"],[])) or {
            "days":0,"orders":0,"orders_per_day":0,"profit_margin":0,"roas":None
        }
        supplier_op=supplier_opportunity(p["id"])
        stock=stock_metrics(p["id"],perf.get("orders_per_day",0))
        action,priority,confidence,reason=choose_action(p,snap,perf,supplier_op,stock)

        metrics={
            "score":snap.get("score"),
            "margin_real":perf.get("profit_margin"),
            "roas_real":perf.get("roas"),
            "roas_target":snap.get("roas_target"),
            "orders_per_day":perf.get("orders_per_day"),
            "stock_cover_days":stock.get("cover_days") if stock else None,
            "supplier_gain_pct":supplier_op.get("gain_pct") if supplier_op else None
        }
        save_portfolio_action(
            p["id"],action,priority,confidence,reason,
            json.dumps(metrics,ensure_ascii=False)
        )
        actions.append({"product":p["name"],"action":action,"priority":priority,
                        "confidence":confidence,"reason":reason,**metrics})
    return actions

if __name__=="__main__":
    for a in run_portfolio():
        print(a)
