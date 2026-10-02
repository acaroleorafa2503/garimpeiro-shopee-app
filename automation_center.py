
import json
from pathlib import Path
from datetime import datetime, timezone
from db import (
    products, latest_snapshots, inventory, performance, suppliers,
    save_automation_event, last_event_by_key, save_automation_run
)
from analytics import seasonal_window

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))
CFG=CONFIG["automation_center"]

def hours_since(iso):
    if not iso:
        return 999999
    dt=datetime.fromisoformat(iso)
    now=datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    return (now-dt).total_seconds()/3600

def should_emit(key):
    prev=last_event_by_key(key)
    if not prev:
        return True
    return hours_since(prev["created_at"]) >= CFG["alert_cooldown_hours"]

def perf_by_product():
    rows=performance(limit=100000)
    out={}
    for r in rows:
        out.setdefault(r["product_id"],[]).append(r)
    return out

def latest_snapshot_map():
    return {r["product_id"]:r for r in latest_snapshots()}

def inventory_map():
    return {r["product_id"]:r for r in inventory()}

def best_supplier_saving(product_id):
    rows=suppliers(product_id)
    costs=sorted([float(r["unit_cost"]) for r in rows if r.get("unit_cost") not in (None,0)])
    if len(costs)<2:
        return None
    best, second=costs[0],costs[1]
    return ((second-best)/second*100) if second else None

def aggregate_perf(rows):
    if not rows:
        return {"orders":0,"revenue":0,"ad_spend":0,"profit":0,"days":0,"orders_per_day":0,"roas":0,"margin":0}
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
        "roas":(revenue/ad_spend) if ad_spend else 0,
        "margin":(profit/revenue*100) if revenue else 0
    }

def emit(product_id,event_type,severity,title,message,key):
    if not should_emit(key):
        return False
    save_automation_event(product_id,event_type,severity,title,message,key)
    return True

def run_alert_center():
    ps=products()
    snaps=latest_snapshot_map()
    invs=inventory_map()
    perfmap=perf_by_product()
    created=0

    t=CFG["thresholds"]

    for p in ps:
        pid=p["id"]
        snap=snaps.get(pid)
        if not snap:
            continue

        perf=aggregate_perf(perfmap.get(pid,[]))
        inv=invs.get(pid)

        # Stock alert
        if inv and perf["orders_per_day"]>0:
            stock=float(inv.get("stock_on_hand") or 0)+float(inv.get("stock_inbound") or 0)
            cover=stock/perf["orders_per_day"]
            if cover <= t["stock_cover_days_low"]:
                if emit(pid,"ESTOQUE_BAIXO","alta",
                        f"Estoque baixo — {p['name']}",
                        f"Cobertura estimada de {cover:.1f} dias.",
                        f"{pid}:ESTOQUE_BAIXO"):
                    created+=1

        # ROAS
        roas_target=float(snap.get("roas_target") or 0)
        if roas_target and perf["roas"] and perf["roas"] < roas_target*t["roas_below_target_factor"]:
            if emit(pid,"ROAS_BAIXO","alta",
                    f"ROAS abaixo do alvo — {p['name']}",
                    f"ROAS real {perf['roas']:.2f} vs alvo {roas_target:.2f}.",
                    f"{pid}:ROAS_BAIXO"):
                created+=1

        # Margin deterioration / low margin versus model
        model_margin=float(snap.get("margin_est_pct") or 0)
        if model_margin and perf["margin"] < model_margin*(1-t["margin_drop_pct"]/100):
            if emit(pid,"MARGEM_DERRETENDO","alta",
                    f"Margem deteriorando — {p['name']}",
                    f"Margem real {perf['margin']:.1f}% vs estimada {model_margin:.1f}%.",
                    f"{pid}:MARGEM_DERRETENDO"):
                created+=1

        # Supplier opportunity
        saving=best_supplier_saving(pid)
        if saving is not None and saving >= t["supplier_saving_pct"]:
            if emit(pid,"FORNECEDOR_MELHOR","media",
                    f"Fornecedor mais barato — {p['name']}",
                    f"Há uma cotação aproximadamente {saving:.1f}% mais barata.",
                    f"{pid}:FORNECEDOR_MELHOR"):
                created+=1

        # Seasonality
        sw=seasonal_window(p.get("peak_months",""))
        if sw["days_to_peak"] is not None and sw["days_to_peak"] <= t["seasonal_days_ahead"]:
            if emit(pid,"JANELA_SAZONAL","alta",
                    f"Janela sazonal chegando — {p['name']}",
                    f"Próximo pico em cerca de {sw['days_to_peak']} dias.",
                    f"{pid}:JANELA_SAZONAL"):
                created+=1

        # Strong score
        score=float(snap.get("score") or 0)
        if score >= t["score_strong"]:
            if emit(pid,"SCORE_FORTE","media",
                    f"Garimpo forte — {p['name']}",
                    f"Score atual {score:.1f}/100.",
                    f"{pid}:SCORE_FORTE"):
                created+=1

    save_automation_run("alert_center",created,"Varredura automática de gatilhos V11.")
    return {"events_created":created}

if __name__=="__main__":
    print(run_alert_center())
