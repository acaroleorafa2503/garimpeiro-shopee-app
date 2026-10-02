
import json, math
from pathlib import Path
from db import products, performance, history, inventory, portfolio_actions, save_growth_plan

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))

def safe_div(a,b):
    return a/b if b not in (0,None) else 0

def latest_action_map():
    rows=portfolio_actions(limit=1000)
    out={}
    for r in rows:
        if r["product_id"] not in out:
            out[r["product_id"]]=r
    return out

def aggregate_perf(rows):
    if not rows:
        return {
            "days":0,"orders":0,"revenue":0,"ad_spend":0,"profit":0,
            "orders_per_day":0,"avg_order_value":0,"roas":0,"cac":0,
            "profit_margin":0
        }
    orders=sum(r["orders"] or 0 for r in rows)
    revenue=sum(r["revenue"] or 0 for r in rows)
    ad_spend=sum(r["ad_spend"] or 0 for r in rows)
    profit=sum(r["profit_real"] or 0 for r in rows)
    days=max(1,len(set(r["date"] for r in rows)))
    return {
        "days":days,
        "orders":orders,
        "revenue":revenue,
        "ad_spend":ad_spend,
        "profit":profit,
        "orders_per_day":orders/days,
        "avg_order_value":safe_div(revenue,orders),
        "roas":safe_div(revenue,ad_spend),
        "cac":safe_div(ad_spend,orders),
        "profit_margin":safe_div(profit,revenue)*100 if revenue else 0
    }

def growth_factor(action, score, roas_real, roas_target, margin_real, cfg):
    min_step=cfg["min_growth_step_pct"]/100
    max_step=cfg["max_growth_step_pct"]/100

    if action=="ESCALAR":
        base=max_step
    elif action in ("RECOMPRAR ESTOQUE","PREPARAR SAZONALIDADE"):
        base=max(min_step, max_step*0.6)
    elif action=="MANTER":
        base=min_step
    elif action=="TROCAR FORNECEDOR":
        base=0
    elif action=="REDUZIR":
        return -min_step
    elif action=="PAUSAR":
        return -1.0
    else:
        base=0

    if roas_target and roas_real:
        ratio=roas_real/roas_target
        if ratio>=1.25: base=min(max_step,base+0.05)
        elif ratio<0.9: base=max(0,base-0.05)

    if margin_real<10:
        base=max(0,base-0.05)
    if score<65:
        base=max(0,base-0.05)

    return round(base,4)

def plan_growth(horizon_days=None, operational_capacity_orders_per_day=None, save=True):
    cfg=CONFIG["growth"]
    horizon=int(horizon_days or cfg["planning_horizon_days"])
    capacity=float(operational_capacity_orders_per_day or cfg["operational_capacity_orders_per_day"])

    perf_all=performance(limit=100000)
    by_product={}
    for r in perf_all:
        by_product.setdefault(r["product_id"],[]).append(r)

    actions=latest_action_map()
    items=[]
    total_current_opd=0
    total_projected_opd=0
    total_ads_today=0
    total_ads_projected=0
    total_revenue_projected=0
    total_profit_projected=0
    total_stock_needed=0

    for p in products():
        hist=history(p["id"],limit=1)
        if not hist:
            continue
        snap=hist[0]
        perf=aggregate_perf(by_product.get(p["id"],[]))
        action=(actions.get(p["id"]) or {}).get("action","MANTER")

        roas_target=float(snap.get("roas_target") or 0)
        score=float(snap.get("score") or 0)
        margin_real=float(perf.get("profit_margin") or 0)
        gf=growth_factor(action,score,perf.get("roas"),roas_target,margin_real,cfg)

        current_opd=float(perf.get("orders_per_day") or 0)
        if gf<=-1:
            projected_opd=0
        else:
            projected_opd=max(0,current_opd*(1+gf))

        aov=float(perf.get("avg_order_value") or snap.get("price_avg") or 0)
        projected_orders=projected_opd*horizon
        projected_revenue=projected_orders*aov

        # Ads planning: use current CAC when healthy, otherwise use target CAC from the model.
        current_cac=float(perf.get("cac") or 0)
        target_cac=float(snap.get("cac_max_target") or 0)
        if action=="ESCALAR":
            planned_cac=min(x for x in [current_cac or target_cac, target_cac] if x>0) if (current_cac or target_cac) else 0
        else:
            planned_cac=current_cac or target_cac

        ads_daily=planned_cac*projected_opd if planned_cac>0 else 0
        ads_budget=ads_daily*horizon

        # Estimate profit with current real margin, but cap at model-estimated margin if lower.
        model_margin=float(snap.get("margin_est_pct") or 0)
        usable_margin=min(margin_real,model_margin) if margin_real and model_margin else max(margin_real,model_margin)
        projected_profit=projected_revenue*(usable_margin/100)

        inv_rows=inventory(p["id"])
        inv=inv_rows[0] if inv_rows else None
        stock_total=(float(inv.get("stock_on_hand") or 0)+float(inv.get("stock_inbound") or 0)) if inv else 0
        required_stock=math.ceil(projected_orders + projected_opd*cfg["min_stock_cover_after_growth_days"])
        additional_stock=max(0,required_stock-stock_total)

        unit_cost=float(
            (inv or {}).get("unit_cost")
            or snap.get("supplier_cost")
            or 0
        )
        additional_stock_cash=additional_stock*unit_cost

        capacity_usage=(projected_opd/capacity*100) if capacity else 0

        items.append({
            "product":p["name"],
            "action":action,
            "score":round(score,2),
            "current_orders_per_day":round(current_opd,2),
            "growth_step_pct":round(gf*100,1),
            "projected_orders_per_day":round(projected_opd,2),
            "projected_orders_horizon":round(projected_orders,1),
            "planned_cac":round(planned_cac,2),
            "ads_daily":round(ads_daily,2),
            "ads_budget_horizon":round(ads_budget,2),
            "projected_revenue":round(projected_revenue,2),
            "projected_profit":round(projected_profit,2),
            "stock_total":round(stock_total,1),
            "required_stock":required_stock,
            "additional_stock_units":additional_stock,
            "additional_stock_cash":round(additional_stock_cash,2),
            "capacity_usage_pct":round(capacity_usage,1)
        })

        total_current_opd+=current_opd
        total_projected_opd+=projected_opd
        total_ads_today+=current_cac*current_opd if current_cac else 0
        total_ads_projected+=ads_daily
        total_revenue_projected+=projected_revenue
        total_profit_projected+=projected_profit
        total_stock_needed+=additional_stock_cash

    capacity_usage_total=(total_projected_opd/capacity*100) if capacity else 0
    hiring_warning=capacity_usage_total>=cfg["capacity_warning_pct"]

    result={
        "horizon_days":horizon,
        "operational_capacity_orders_per_day":capacity,
        "current_orders_per_day":round(total_current_opd,2),
        "projected_orders_per_day":round(total_projected_opd,2),
        "capacity_usage_pct":round(capacity_usage_total,1),
        "hiring_warning":hiring_warning,
        "projected_revenue":round(total_revenue_projected,2),
        "projected_profit":round(total_profit_projected,2),
        "projected_ads_daily":round(total_ads_projected,2),
        "projected_ads_horizon":round(total_ads_projected*horizon,2),
        "additional_stock_cash_needed":round(total_stock_needed,2),
        "items":sorted(items,key=lambda x:x["projected_profit"],reverse=True)
    }

    if save:
        save_growth_plan(
            horizon,
            json.dumps(result,ensure_ascii=False),
            notes="Plano V8: Ads, pedidos/dia, faturamento, lucro, estoque e capacidade operacional."
        )
    return result

if __name__=="__main__":
    print(json.dumps(plan_growth(),ensure_ascii=False,indent=2))
