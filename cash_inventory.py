
import json, math
from pathlib import Path
from db import products, performance, history, inventory, suppliers, portfolio_actions, save_cash_plan

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))

ACTION_SCORE = {
    "ESCALAR": 1.00,
    "RECOMPRAR ESTOQUE": 0.95,
    "PREPARAR SAZONALIDADE": 0.85,
    "MANTER": 0.60,
    "TROCAR FORNECEDOR": 0.55,
    "REDUZIR": 0.30,
    "PAUSAR": 0.00
}

def safe_div(a,b):
    return a/b if b not in (None,0) else 0

def aggregate_perf(rows):
    if not rows:
        return {
            "orders":0,"revenue":0,"ad_spend":0,"profit":0,"days":0,
            "orders_per_day":0,"roas":0,"profit_margin":0
        }
    orders=sum(r["orders"] or 0 for r in rows)
    revenue=sum(r["revenue"] or 0 for r in rows)
    ad_spend=sum(r["ad_spend"] or 0 for r in rows)
    profit=sum(r["profit_real"] or 0 for r in rows)
    days=max(1,len(set(r["date"] for r in rows)))
    return {
        "orders":orders,
        "revenue":revenue,
        "ad_spend":ad_spend,
        "profit":profit,
        "days":days,
        "orders_per_day":orders/days,
        "roas":safe_div(revenue,ad_spend),
        "profit_margin":safe_div(profit,revenue)*100 if revenue else 0
    }

def latest_action_map():
    rows=portfolio_actions(limit=1000)
    out={}
    for r in rows:
        if r["product_id"] not in out:
            out[r["product_id"]]=r
    return out

def best_supplier(product_id):
    rows=suppliers(product_id)
    if not rows:
        return None
    valid=[r for r in rows if r.get("unit_cost") not in (None,0)]
    if not valid:
        return None
    return sorted(valid,key=lambda r: float(r["unit_cost"]))[0]

def normalize(vals, reverse=False):
    if not vals:
        return []
    lo=min(vals); hi=max(vals)
    if hi==lo:
        base=[0.5]*len(vals)
    else:
        base=[(v-lo)/(hi-lo) for v in vals]
    if reverse:
        base=[1-x for x in base]
    return base

def plan_cash(total_budget=None, reserve_pct=None, target_cover_days=None, save=True):
    cfg=CONFIG["cash_inventory"]
    total_budget=float(total_budget if total_budget is not None else cfg["default_budget"])
    reserve_pct=float(reserve_pct if reserve_pct is not None else cfg["cash_reserve_pct"])
    target_cover_days=float(target_cover_days if target_cover_days is not None else cfg["default_target_cover_days"])
    target_cover_days=max(cfg["min_cover_days"],min(cfg["max_cover_days"],target_cover_days))
    usable=total_budget*(1-reserve_pct/100)

    perf_all=performance(limit=100000)
    by_product={}
    for r in perf_all:
        by_product.setdefault(r["product_id"],[]).append(r)

    actions=latest_action_map()
    rows=[]

    for p in products():
        hist=history(p["id"],limit=1)
        if not hist:
            continue
        snap=hist[0]
        perf=aggregate_perf(by_product.get(p["id"],[]))
        inv_rows=inventory(p["id"])
        inv=inv_rows[0] if inv_rows else {
            "stock_on_hand":0,"stock_inbound":0,"reorder_lead_days":0,
            "safety_stock_days":7,"unit_cost":0
        }
        supplier=best_supplier(p["id"])

        unit_cost=float(
            (supplier or {}).get("unit_cost")
            or inv.get("unit_cost")
            or snap.get("supplier_cost")
            or 0
        )

        stock_total=float(inv.get("stock_on_hand") or 0)+float(inv.get("stock_inbound") or 0)
        opd=float(perf.get("orders_per_day") or 0)
        current_cover=safe_div(stock_total,opd) if opd>0 else None

        lead=float(inv.get("reorder_lead_days") or 0)
        safety=float(inv.get("safety_stock_days") or 7)
        desired_cover=max(target_cover_days, lead+safety)

        target_units=math.ceil(opd*desired_cover) if opd>0 else 0
        buy_units=max(0,target_units-stock_total)
        capital_needed=buy_units*unit_cost

        price=float(snap.get("price_avg") or 0)
        est_unit_profit=float(snap.get("profit_est") or 0)
        expected_lot_profit=buy_units*est_unit_profit

        action=(actions.get(p["id"]) or {}).get("action","MANTER")
        stockout_risk=1.0 if (current_cover is not None and current_cover < max(7,lead+safety)) else 0.0

        rows.append({
            "product_id":p["id"],
            "product":p["name"],
            "action":action,
            "score":float(snap.get("score") or 0),
            "margin_real":float(perf.get("profit_margin") or 0),
            "roas_real":float(perf.get("roas") or 0),
            "orders_per_day":opd,
            "stock_total":stock_total,
            "current_cover_days":current_cover,
            "desired_cover_days":desired_cover,
            "unit_cost":unit_cost,
            "recommended_units_raw":buy_units,
            "capital_needed_raw":capital_needed,
            "expected_lot_profit_raw":expected_lot_profit,
            "stockout_risk":stockout_risk
        })

    if not rows:
        return {"budget":total_budget,"usable_budget":usable,"reserve_pct":reserve_pct,"items":[]}

    # Normalize score dimensions
    margins=normalize([r["margin_real"] for r in rows])
    roases=normalize([r["roas_real"] for r in rows])
    scores=normalize([r["score"] for r in rows])
    velocities=normalize([r["orders_per_day"] for r in rows])

    w=cfg["priority_weights"]
    for i,r in enumerate(rows):
        action_score=ACTION_SCORE.get(r["action"],0.5)
        priority=(
            action_score*w["portfolio_action"] +
            margins[i]*w["real_margin"] +
            roases[i]*w["real_roas"] +
            scores[i]*w["score"] +
            velocities[i]*w["sales_velocity"] +
            r["stockout_risk"]*w["stockout_risk"]
        )
        r["priority_score"]=round(priority*100,2)

    # Allocation by priority, while respecting needed capital and max per-product share.
    allocatable=[r for r in rows if r["action"] not in ("PAUSAR","REDUZIR") and r["capital_needed_raw"]>0 and r["unit_cost"]>0]
    total_priority=sum(r["priority_score"] for r in allocatable) or 1
    max_per_product=usable*(cfg["max_product_allocation_pct"]/100)

    remaining=usable
    for r in sorted(allocatable,key=lambda x:x["priority_score"],reverse=True):
        fair_share=usable*(r["priority_score"]/total_priority)
        cap=min(r["capital_needed_raw"],fair_share,max_per_product,remaining)
        units=math.floor(cap/r["unit_cost"]) if r["unit_cost"]>0 else 0
        actual_cap=units*r["unit_cost"]
        r["recommended_units"]=units
        r["capital_allocated"]=round(actual_cap,2)
        r["expected_lot_profit"]=round(units*(r["expected_lot_profit_raw"]/r["recommended_units_raw"]),2) if r["recommended_units_raw"] else 0
        remaining-=actual_cap

    for r in rows:
        r.setdefault("recommended_units",0)
        r.setdefault("capital_allocated",0.0)
        r.setdefault("expected_lot_profit",0.0)
        r["current_cover_days"]=round(r["current_cover_days"],1) if r["current_cover_days"] is not None else None

    rows=sorted(rows,key=lambda x:(x["priority_score"],x["expected_lot_profit"]),reverse=True)

    result={
        "budget":round(total_budget,2),
        "reserve_pct":reserve_pct,
        "reserve_value":round(total_budget-usable,2),
        "usable_budget":round(usable,2),
        "allocated":round(sum(r["capital_allocated"] for r in rows),2),
        "cash_remaining":round(usable-sum(r["capital_allocated"] for r in rows),2),
        "target_cover_days":target_cover_days,
        "items":rows
    }

    if save:
        save_cash_plan(total_budget,reserve_pct,usable,json.dumps(result,ensure_ascii=False),
                       notes="Plano V7 com prioridade de portfólio, margem, ROAS, Score, velocidade e risco de ruptura.")
    return result

if __name__=="__main__":
    p=plan_cash()
    print(json.dumps(p,ensure_ascii=False,indent=2))
