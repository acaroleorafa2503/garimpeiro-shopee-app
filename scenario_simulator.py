
import json, math
from pathlib import Path
from db import products, performance, history, inventory, portfolio_actions, save_scenario_run

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))

def safe_div(a,b):
    return a/b if b not in (0,None) else 0

def aggregate_perf(rows):
    if not rows:
        return {
            "days":0,"orders":0,"revenue":0,"ad_spend":0,"profit":0,
            "orders_per_day":0,"avg_order_value":0,"roas":0,"cac":0,
            "profit_margin":0,"conversion_rate":0
        }
    orders=sum(r["orders"] or 0 for r in rows)
    revenue=sum(r["revenue"] or 0 for r in rows)
    ad_spend=sum(r["ad_spend"] or 0 for r in rows)
    profit=sum(r["profit_real"] or 0 for r in rows)
    clicks=sum(r["clicks"] or 0 for r in rows)
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
        "profit_margin":safe_div(profit,revenue)*100 if revenue else 0,
        "conversion_rate":safe_div(orders,clicks)*100 if clicks else 0
    }

def latest_action_map():
    rows=portfolio_actions(limit=1000)
    out={}
    for r in rows:
        if r["product_id"] not in out:
            out[r["product_id"]]=r
    return out

def run_scenario(name="base", horizon_days=30, overrides=None, save=True):
    preset=CONFIG["scenarios"].get(name,CONFIG["scenarios"]["base"]).copy()
    if overrides:
        preset.update(overrides)

    perf_all=performance(limit=100000)
    by_product={}
    for r in perf_all:
        by_product.setdefault(r["product_id"],[]).append(r)

    actions=latest_action_map()
    items=[]
    total_revenue=0
    total_profit=0
    total_ads=0
    total_stock_cash=0
    total_orders=0

    for p in products():
        hist=history(p["id"],limit=1)
        if not hist:
            continue
        snap=hist[0]
        perf=aggregate_perf(by_product.get(p["id"],[]))
        action=(actions.get(p["id"]) or {}).get("action","MANTER")

        base_opd=float(perf.get("orders_per_day") or 0)
        aov=float(perf.get("avg_order_value") or snap.get("price_avg") or 0)
        base_cac=float(perf.get("cac") or snap.get("cac_max_target") or 0)
        unit_cost=float(snap.get("supplier_cost") or 0)

        demand_mult=float(preset.get("demand_mult",1))
        conv_mult=float(preset.get("conversion_mult",1))
        season_mult=float(preset.get("seasonality_mult",1))
        ad_cost_mult=float(preset.get("ad_cost_mult",1))
        supplier_mult=float(preset.get("supplier_cost_mult",1))

        action_mult={
            "ESCALAR":1.20,
            "RECOMPRAR ESTOQUE":1.10,
            "PREPARAR SAZONALIDADE":1.10,
            "MANTER":1.00,
            "TROCAR FORNECEDOR":1.00,
            "REDUZIR":0.85,
            "PAUSAR":0.00
        }.get(action,1.0)

        projected_opd=base_opd*demand_mult*conv_mult*season_mult*action_mult
        projected_orders=projected_opd*horizon_days
        projected_revenue=projected_orders*aov

        planned_cac=base_cac*ad_cost_mult
        projected_ads=planned_cac*projected_orders

        adjusted_unit_cost=unit_cost*supplier_mult
        cogs=adjusted_unit_cost*projected_orders

        # Use observed non-ad/non-cogs cost ratio inferred from model margin when available.
        model_margin=float(snap.get("margin_est_pct") or 0)/100
        price=float(snap.get("price_avg") or aov or 0)
        model_profit_per_order=float(snap.get("profit_est") or 0)
        model_total_cost_per_order=max(0,price-model_profit_per_order) if price else 0
        inferred_other_cost=max(0,model_total_cost_per_order-unit_cost-(float(snap.get("ads_pct") or 0)/100*price))
        other_costs=inferred_other_cost*projected_orders

        projected_profit=projected_revenue-projected_ads-cogs-other_costs

        inv_rows=inventory(p["id"])
        inv=inv_rows[0] if inv_rows else None
        stock_total=(float(inv.get("stock_on_hand") or 0)+float(inv.get("stock_inbound") or 0)) if inv else 0
        stock_shortage=max(0,math.ceil(projected_orders)-stock_total)
        stock_cash=stock_shortage*adjusted_unit_cost

        stockout_flag=stock_shortage>0
        margin_pct=(projected_profit/projected_revenue*100) if projected_revenue else 0
        roas=(projected_revenue/projected_ads) if projected_ads else 0

        items.append({
            "product":p["name"],
            "action":action,
            "projected_orders":round(projected_orders,1),
            "projected_orders_per_day":round(projected_opd,2),
            "projected_revenue":round(projected_revenue,2),
            "projected_ads":round(projected_ads,2),
            "projected_cac":round(planned_cac,2),
            "projected_roas":round(roas,2),
            "projected_profit":round(projected_profit,2),
            "projected_margin_pct":round(margin_pct,2),
            "adjusted_unit_cost":round(adjusted_unit_cost,2),
            "stock_shortage_units":int(stock_shortage),
            "stock_cash_needed":round(stock_cash,2),
            "stockout_risk":stockout_flag
        })

        total_orders+=projected_orders
        total_revenue+=projected_revenue
        total_profit+=projected_profit
        total_ads+=projected_ads
        total_stock_cash+=stock_cash

    result={
        "scenario":name,
        "horizon_days":horizon_days,
        "params":preset,
        "orders":round(total_orders,1),
        "revenue":round(total_revenue,2),
        "ads":round(total_ads,2),
        "profit":round(total_profit,2),
        "margin_pct":round((total_profit/total_revenue*100) if total_revenue else 0,2),
        "roas":round((total_revenue/total_ads) if total_ads else 0,2),
        "stock_cash_needed":round(total_stock_cash,2),
        "items":sorted(items,key=lambda x:x["projected_profit"],reverse=True)
    }

    if save:
        save_scenario_run(
            name,
            json.dumps(preset,ensure_ascii=False),
            json.dumps(result,ensure_ascii=False),
            notes="Simulação V9 sem execução real; serve para comparar cenários antes de investir."
        )
    return result

def compare_scenarios(horizon_days=30):
    names=["conservador","base","agressivo"]
    return [run_scenario(n,horizon_days,save=False) for n in names]

if __name__=="__main__":
    print(json.dumps(compare_scenarios(),ensure_ascii=False,indent=2))
