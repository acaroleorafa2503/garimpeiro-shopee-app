
from db import init_db, products, history, add_snapshot, add_alert, suppliers
from engine import score
from analytics import infer_trend, seasonal_window, generate_alerts
from collectors.csv_collector import CSVCollector
from pathlib import Path

BASE=Path(__file__).resolve().parent

def heuristic_notes(prod,signals):
    defaults={
        "demanda":6,"tendencia":5,"sazonalidade":7,"concorrencia":5,"margem":5,
        "fornecedor":5,"prontidao":7,"logistica":7,"devolucao":7,"visual":7,
        "kit":6,"recorrencia":5,"comoditizacao":5,"escala":7
    }
    for k in list(defaults):
        if signals.get(k) is not None:
            defaults[k]=signals[k]
    return defaults

def best_supplier_cost(product_id):
    rows=suppliers(product_id)
    costs=[r["unit_cost"] for r in rows if r.get("unit_cost") is not None and r["unit_cost"]>0]
    return min(costs) if costs else None

def run():
    init_db()
    collector=CSVCollector(BASE/"data"/"coleta_atual.csv")
    results=[]
    for p in products():
        signals=collector.collect(p)
        if not signals:
            continue

        supplier_best=best_supplier_cost(p["id"])
        if supplier_best is not None:
            signals["supplier_cost"]=supplier_best

        prev=history(p["id"],limit=30)
        notes=heuristic_notes(p,signals)

        if prev and signals.get("demand_signal") is not None:
            pseudo=[{"demand_signal":signals.get("demand_signal")}] + prev
            tr=infer_trend(pseudo)
            if tr["change_pct"] is not None:
                notes["tendencia"]=max(0,min(10,5+tr["change_pct"]/10))

        sw=seasonal_window(p.get("peak_months",""))
        if sw["days_to_peak"] is None:
            notes["sazonalidade"]=8 if p.get("seasonality_type")=="Perene" else notes["sazonalidade"]
        elif sw["days_to_peak"]<=60:
            notes["sazonalidade"]=10
        elif sw["days_to_peak"]<=120:
            notes["sazonalidade"]=8
        else:
            notes["sazonalidade"]=5

        payload={**signals,**notes}
        res=score(payload)
        snapshot={
            **signals,**notes,
            "score":res["score"],
            "classification":res["classification"],
            "profit_est":res["profit_est"],
            "margin_est_pct":res["margin_est_pct"],
            "contribution_before_ads":res["contribution_before_ads"],
            "cac_max_break_even":res["cac_max_break_even"],
            "cac_max_target":res["cac_max_target"],
            "roas_min_break_even":res["roas_min_break_even"],
            "roas_target":res["roas_target"],
            "target_profit_margin_pct":float(signals.get("target_profit_margin_pct") or 12),
            "why_now":res["why_now"],
            "notes":""
        }
        add_snapshot(p["id"],snapshot)
        hist=history(p["id"],limit=30)
        for t,sev,msg in generate_alerts(p,hist):
            add_alert(p["id"],t,sev,msg)
        results.append((p["name"],res))
    return results

if __name__=="__main__":
    for name,res in run():
        print(name,res)
