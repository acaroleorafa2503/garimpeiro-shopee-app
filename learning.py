
import json, math, statistics
from pathlib import Path
from db import products, performance, history, save_calibration

BASE=Path(__file__).resolve().parent
CONFIG_PATH=BASE/"config.json"

CRITERIA = [
    "demanda","tendencia","sazonalidade","concorrencia","margem","fornecedor",
    "prontidao","logistica","devolucao","visual","kit","recorrencia","comoditizacao","escala"
]

def clamp(x,a,b):
    return max(a,min(b,x))

def safe_corr(xs, ys):
    if len(xs)<3 or len(ys)<3:
        return 0.0
    mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
    num=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    dx=math.sqrt(sum((x-mx)**2 for x in xs))
    dy=math.sqrt(sum((y-my)**2 for y in ys))
    if dx==0 or dy==0:
        return 0.0
    return num/(dx*dy)

def minmax(vals):
    if not vals:
        return []
    lo=min(vals); hi=max(vals)
    if hi==lo:
        return [0.5]*len(vals)
    return [(v-lo)/(hi-lo) for v in vals]

def product_performance_target(rows, cfg):
    if not rows:
        return None
    # aggregate by product across available periods
    impressions=sum(r["impressions"] or 0 for r in rows)
    clicks=sum(r["clicks"] or 0 for r in rows)
    orders=sum(r["orders"] or 0 for r in rows)
    revenue=sum(r["revenue"] or 0 for r in rows)
    ad_spend=sum(r["ad_spend"] or 0 for r in rows)
    returns=sum(r["returns"] or 0 for r in rows)
    profit=sum(r["profit_real"] or 0 for r in rows)

    ctr=(clicks/impressions*100) if impressions else 0
    conv=(orders/clicks*100) if clicks else 0
    roas=(revenue/ad_spend) if ad_spend else 0
    return_rate=(returns/orders*100) if orders else 0
    profit_margin=(profit/revenue*100) if revenue else -100
    velocity=orders/max(1,len(set(r["date"] for r in rows)))

    return {
        "profit_margin":profit_margin,
        "roas":roas,
        "conversion_rate":conv,
        "ctr":ctr,
        "return_rate_inverse":-return_rate,
        "sales_velocity":velocity
    }

def calibrate_weights(apply=False):
    cfg=json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    learn=cfg["learning"]
    min_obs=learn["min_observations_to_calibrate"]
    shrink=learn["shrinkage"]
    max_change=learn["max_weight_change_pct_per_run"]/100

    all_perf=performance(limit=100000)
    if len(all_perf)<min_obs:
        return {
            "ready":False,
            "observations":len(all_perf),
            "minimum":min_obs,
            "message":f"Precisamos de pelo menos {min_obs} observações; há {len(all_perf)}."
        }

    by_product={}
    for r in all_perf:
        by_product.setdefault(r["product_id"],[]).append(r)

    products_rows=products()
    data=[]
    for p in products_rows:
        perf_rows=by_product.get(p["id"],[])
        if not perf_rows:
            continue
        target_parts=product_performance_target(perf_rows,cfg)
        hist=history(p["id"],limit=1)
        if not hist:
            continue
        snap=hist[0]
        data.append({"product":p,"target_parts":target_parts,"snapshot":snap})

    if len(data)<3:
        return {
            "ready":False,
            "observations":len(all_perf),
            "minimum_products":3,
            "message":"Há dados, mas ainda precisamos de desempenho de pelo menos 3 produtos diferentes."
        }

    # normalize each performance component across products
    component_names=list(learn["performance_target_weights"].keys())
    normalized={}
    for comp in component_names:
        vals=[float(d["target_parts"][comp]) for d in data]
        normalized[comp]=minmax(vals)

    targets=[]
    for i,d in enumerate(data):
        t=0
        for comp,w in learn["performance_target_weights"].items():
            t += normalized[comp][i]*w
        targets.append(t)

    old=cfg["pesos"].copy()
    raw_importance={}
    for criterion in CRITERIA:
        xs=[float(d["snapshot"].get(criterion) or 0) for d in data]
        c=safe_corr(xs,targets)
        # positive association matters; negative correlations reduce importance
        raw_importance[criterion]=max(0.05,(c+1)/2)

    # scale importances back to 100 points total
    total_imp=sum(raw_importance.values())
    desired={k:raw_importance[k]/total_imp*100 for k in CRITERIA}

    suggested={}
    for k in CRITERIA:
        oldw=float(old[k])
        blended=oldw*(1-shrink)+desired[k]*shrink
        lo=oldw*(1-max_change); hi=oldw*(1+max_change)
        suggested[k]=round(clamp(blended,lo,hi),2)

    # normalize to 100
    s=sum(suggested.values())
    suggested={k:round(v/s*100,2) for k,v in suggested.items()}
    # correct rounding drift
    drift=round(100-sum(suggested.values()),2)
    if drift:
        biggest=max(suggested,key=suggested.get)
        suggested[biggest]=round(suggested[biggest]+drift,2)

    applied=None
    if apply:
        applied=suggested.copy()
        cfg["pesos"]=applied
        CONFIG_PATH.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")

    save_calibration(
        len(all_perf),old,suggested,applied,
        notes="Calibração com correlação suavizada; alterações limitadas por execução."
    )
    return {
        "ready":True,
        "observations":len(all_perf),
        "products":len(data),
        "old_weights":old,
        "suggested_weights":suggested,
        "applied":bool(apply)
    }
