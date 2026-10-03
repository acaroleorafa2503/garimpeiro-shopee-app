from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import unicodedata
import re

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")

EVENTS = [
    {
        "name":"Dia das Crianças","type":"Data comercial","month":10,"day":12,
        "lead_days":45,"ad_start_days":30,
        "keywords":["brinquedo","infantil","crianca","bebe","educativo","presente infantil"],
        "dead_stock_risk":"Médio",
    },
    {
        "name":"Halloween","type":"Data comercial","month":10,"day":31,
        "lead_days":45,"ad_start_days":30,
        "keywords":["halloween","fantasia","abobora","terror","decoracao halloween","festa halloween"],
        "dead_stock_risk":"Alto",
    },
    {
        "name":"Black Friday","type":"Data comercial","special":"black_friday",
        "lead_days":45,"ad_start_days":21,
        "keywords":["eletronico","ferramenta","automotivo","notebook","celular","eletroportatil"],
        "dead_stock_risk":"Baixo",
    },
    {
        "name":"Natal","type":"Data comercial","month":12,"day":25,
        "lead_days":60,"ad_start_days":45,
        "keywords":["presente","decoracao natal","luz natal","arvore natal","brinquedo"],
        "dead_stock_risk":"Médio",
    },
    {
        "name":"Volta às Aulas","type":"Sazonal forte","month":1,"day":20,
        "lead_days":60,"ad_start_days":40,
        "keywords":["escolar","mochila","estojo","caderno","material escolar","organizador mesa"],
        "dead_stock_risk":"Médio",
    },
    {
        "name":"Verão","type":"Climático","month":12,"day":21,
        "lead_days":60,"ad_start_days":45,
        "keywords":["verao","praia","piscina","garrafa termica","ventilador","protetor solar"],
        "dead_stock_risk":"Baixo",
    },
]

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii","ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _black_friday(year):
    d = date(year,11,1)
    fridays=[]
    while d.month == 11:
        if d.weekday() == 4:
            fridays.append(d)
        d += timedelta(days=1)
    return fridays[3]

def _event_date(event, year):
    if event.get("special") == "black_friday":
        return _black_friday(year)
    return date(year,int(event["month"]),int(event["day"]))

def _next_event_date(event, today):
    d = _event_date(event,today.year)
    if d < today:
        d = _event_date(event,today.year+1)
    return d

def detect_seasonality(product, today=None):
    today = today or datetime.now(BRAZIL_TZ).date()
    hay = _norm(
        (product.get("produto") or "") + " " +
        (product.get("categorias_descoberta") or "") + " " +
        (product.get("categoria") or "")
    )

    matches=[]
    for event in EVENTS:
        hits=sum(1 for kw in event["keywords"] if _norm(kw) and _norm(kw) in hay)
        if not hits:
            continue

        peak=_next_event_date(event,today)
        days=(peak-today).days
        lead=int(event.get("lead_days",45))
        ad_start=int(event.get("ad_start_days",30))

        if days <= 7:
            window="🔴 Atrasado"
        elif days <= ad_start:
            window="🟡 Atenção"
        elif days <= lead:
            window="🟢 Momento ideal"
        else:
            window="🔵 Antecipação"

        bonus={"🟢 Momento ideal":12,"🟡 Atenção":7,"🔵 Antecipação":3,"🔴 Atrasado":-6}[window]

        matches.append({
            "evento":event["name"],
            "tipo":event["type"],
            "data_pico":peak.isoformat(),
            "dias_ate_pico":days,
            "janela":window,
            "lead_time_ideal_dias":lead,
            "inicio_ads_dias_antes":ad_start,
            "risco_encalhe":event["dead_stock_risk"],
            "bonus_sazonal":bonus,
            "hits":hits,
        })

    if not matches:
        return {
            "evento":"Perene / sem evento claro","tipo":"Perene","data_pico":"",
            "dias_ate_pico":None,"janela":"🟢 Perene","lead_time_ideal_dias":0,
            "inicio_ads_dias_antes":0,"risco_encalhe":"Baixo","bonus_sazonal":0,"hits":0
        }

    priority={"🟢 Momento ideal":4,"🟡 Atenção":3,"🔵 Antecipação":2,"🔴 Atrasado":1}
    matches.sort(key=lambda x:(x["hits"],priority.get(x["janela"],0),-x["dias_ate_pico"]),reverse=True)
    return matches[0]

def apply_seasonality_to_rows(rows,today=None):
    out=[]
    for row in rows or []:
        r=dict(row)
        p=r.get("_product") or {"produto":r.get("produto","")}
        saz=detect_seasonality(p,today=today)
        r.update({
            "evento_sazonal":saz["evento"],
            "tipo_sazonal":saz["tipo"],
            "janela_sazonal":saz["janela"],
            "dias_ate_pico":saz["dias_ate_pico"],
            "data_pico":saz["data_pico"],
            "risco_encalhe":saz["risco_encalhe"],
            "bonus_sazonal":saz["bonus_sazonal"],
        })
        r["score_oportunidade_hoje"]=max(
            0,min(100,int(r.get("score_oportunidade_hoje") or 0)+int(saz["bonus_sazonal"]))
        )
        out.append(r)
    return out
