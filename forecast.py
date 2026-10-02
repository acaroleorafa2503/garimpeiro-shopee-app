
from db import products,performance

def product_daily_orders(product_id):
    rows=performance(product_id,limit=100000)
    by={}
    for r in rows:
        by[r["date"]]=by.get(r["date"],0)+(r["orders"] or 0)
    return sorted(by.items())

def forecast_product(product_id,horizon=30):
    pts=product_daily_orders(product_id)
    if not pts:
        return {"daily_forecast":0,"forecast_orders":0,"method":"sem dados"}
    vals=[v for _,v in pts]
    recent=vals[-7:]
    avg=sum(recent)/len(recent)
    if len(vals)>=3:
        x=list(range(len(vals)))
        mx=sum(x)/len(x); my=sum(vals)/len(vals)
        denom=sum((i-mx)**2 for i in x) or 1
        slope=sum((i-mx)*(v-my) for i,v in zip(x,vals))/denom
    else:
        slope=0
    daily=max(0,avg+slope*min(7,len(vals))/2)
    return {"daily_forecast":round(daily,2),"forecast_orders":round(daily*horizon,1),"method":"média recente + tendência linear"}

def forecast_all(horizon=30):
    return [{"product":p["name"],**forecast_product(p["id"],horizon)} for p in products()]
