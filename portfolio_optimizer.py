
from db import latest_snapshots,performance,inventory

def optimize(max_products=5):
    snaps=latest_snapshots()
    perf=performance(limit=100000)
    by={}
    for r in perf: by.setdefault(r["product_id"],[]).append(r)
    items=[]
    for s in snaps:
        rows=by.get(s["product_id"],[])
        revenue=sum(r["revenue"] or 0 for r in rows)
        profit=sum(r["profit_real"] or 0 for r in rows)
        ads=sum(r["ad_spend"] or 0 for r in rows)
        roas=revenue/ads if ads else 0
        margin=profit/revenue*100 if revenue else 0
        score=float(s.get("score") or 0)
        composite=score*0.4 + max(0,min(100,margin*2))*0.3 + max(0,min(100,roas*10))*0.3
        items.append({"product":s["name"],"score":score,"margin_real":round(margin,2),"roas_real":round(roas,2),"portfolio_score":round(composite,2)})
    items.sort(key=lambda x:x["portfolio_score"],reverse=True)
    return items[:max_products]
