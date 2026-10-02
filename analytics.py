
from datetime import datetime
import statistics
from engine import CONFIG

def pct_change(new, old):
    if old in (None,0): return None
    return (new-old)/old*100

def infer_trend(history):
    # history comes newest first
    vals=[r.get("demand_signal") for r in history if r.get("demand_signal") is not None]
    if len(vals)<2: return {"change_pct":None,"label":"sem histórico"}
    new=vals[0]
    baseline=statistics.mean(vals[1:min(len(vals),8)])
    ch=pct_change(new, baseline)
    if ch is None: return {"change_pct":None,"label":"sem histórico"}
    if ch >= CONFIG["limiares_alerta"]["aceleracao_pct"]: label="acelerando"
    elif ch <= CONFIG["limiares_alerta"]["queda_pct"]: label="caindo"
    else: label="estável"
    return {"change_pct":round(ch,2),"label":label}

def parse_peak_months(s):
    if not s: return []
    out=[]
    for x in str(s).split(","):
        x=x.strip()
        if x.isdigit() and 1 <= int(x) <= 12:
            out.append(int(x))
    return out

def seasonal_window(peak_months, today=None):
    today=today or datetime.now().date()
    peaks=parse_peak_months(peak_months)
    if not peaks:
        return {"label":"perene/indefinido","days_to_peak":None}
    candidates=[]
    for m in peaks:
        y=today.year
        target=datetime(y,m,15).date()
        if target < today:
            target=datetime(y+1,m,15).date()
        candidates.append((target-today).days)
    d=min(candidates)
    lead=CONFIG["limiares_alerta"]["dias_antecipacao_sazonal"]
    if d <= 14: label="🟡 pico muito próximo"
    elif d <= lead: label="🟢 momento ideal de entrada"
    elif d <= lead+60: label="🔵 antecipação"
    else: label="fora da janela principal"
    return {"label":label,"days_to_peak":d}

def generate_alerts(product, history):
    alerts=[]
    if not history: return alerts
    latest=history[0]
    trend=infer_trend(history)
    if trend["label"]=="acelerando":
        alerts.append(("ACELERACAO","alta",f"Demanda acelerou {trend['change_pct']}% versus histórico recente."))
    if trend["label"]=="caindo":
        alerts.append(("QUEDA","media",f"Demanda caiu {abs(trend['change_pct'])}% versus histórico recente."))
    score=latest.get("score") or 0
    if score >= CONFIG["limiares_alerta"]["score_forte"]:
        alerts.append(("GARIMPO_FORTE","alta",f"Score atingiu {score}/100."))
    elif score >= CONFIG["limiares_alerta"]["score_teste"]:
        alerts.append(("CANDIDATO_TESTE","media",f"Score atingiu {score}/100."))
    margin=latest.get("margin_est_pct")
    if margin is not None and margin < CONFIG["limiares_alerta"]["margem_min_pct"]:
        alerts.append(("MARGEM_BAIXA","alta",f"Margem líquida estimada em {margin}%."))
    sw=seasonal_window(product.get("peak_months",""))
    if sw["days_to_peak"] is not None and sw["days_to_peak"] <= CONFIG["limiares_alerta"]["dias_antecipacao_sazonal"]:
        alerts.append(("SAZONALIDADE","alta",f"{sw['label']}; cerca de {sw['days_to_peak']} dias para o próximo pico."))
    return alerts
