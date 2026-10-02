
import json
from pathlib import Path
from db import (
    latest_snapshots, alerts, inventory, performance,
    portfolio_actions, cash_plans, growth_plans, scenario_runs
)

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))

def _latest_by_product(actions):
    out={}
    for a in actions:
        if a["product_id"] not in out:
            out[a["product_id"]]=a
    return out

def build_executive_summary():
    ranking=latest_snapshots()
    all_alerts=alerts()
    inv=inventory()
    perf=performance(limit=100000)
    actions=portfolio_actions(limit=1000)
    cash=cash_plans(limit=1)
    growth=growth_plans(limit=1)
    scenarios=scenario_runs(limit=10)

    action_map=_latest_by_product(actions)

    revenue=sum(float(r.get("revenue") or 0) for r in perf)
    ad_spend=sum(float(r.get("ad_spend") or 0) for r in perf)
    profit=sum(float(r.get("profit_real") or 0) for r in perf)
    orders=sum(float(r.get("orders") or 0) for r in perf)
    roas=(revenue/ad_spend) if ad_spend else 0
    margin=(profit/revenue*100) if revenue else 0

    stock_value=sum(float(r.get("stock_on_hand") or 0)*float(r.get("unit_cost") or 0) for r in inv)

    critical=[a for a in all_alerts if a.get("severity") in CONFIG["executive"]["critical_alert_severities"]]

    action_counts={}
    for a in action_map.values():
        action_counts[a["action"]]=action_counts.get(a["action"],0)+1

    top_products=[]
    for r in ranking[:CONFIG["executive"]["top_products_limit"]]:
        top_products.append({
            "name":r.get("name"),
            "score":r.get("score"),
            "classification":r.get("classification"),
            "profit_est":r.get("profit_est"),
            "margin_est_pct":r.get("margin_est_pct"),
            "roas_target":r.get("roas_target"),
            "action":(action_map.get(r.get("product_id")) or {}).get("action")
        })

    latest_cash = json.loads(cash[0]["plan_json"]) if cash else None
    latest_growth = json.loads(growth[0]["plan_json"]) if growth else None

    scenario_summary=[]
    for s in scenarios[:3]:
        try:
            result=json.loads(s["result_json"])
            scenario_summary.append({
                "name":s["scenario_name"],
                "revenue":result.get("revenue"),
                "profit":result.get("profit"),
                "roas":result.get("roas"),
                "margin_pct":result.get("margin_pct"),
                "stock_cash_needed":result.get("stock_cash_needed")
            })
        except Exception:
            pass

    return {
        "kpis":{
            "orders":round(orders,1),
            "revenue":round(revenue,2),
            "ad_spend":round(ad_spend,2),
            "roas":round(roas,2),
            "profit":round(profit,2),
            "margin_pct":round(margin,2),
            "stock_value":round(stock_value,2),
            "critical_alerts":len(critical)
        },
        "action_counts":action_counts,
        "top_products":top_products,
        "critical_alerts":critical[:20],
        "cash_plan":latest_cash,
        "growth_plan":latest_growth,
        "scenarios":scenario_summary
    }

if __name__=="__main__":
    print(json.dumps(build_executive_summary(),ensure_ascii=False,indent=2))
