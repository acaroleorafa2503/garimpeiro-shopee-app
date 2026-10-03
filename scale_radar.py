import sqlite3
from datetime import datetime, timezone

DB_PATH = "garimpeiro_scale.db"

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = _conn()
    c.execute("""
    CREATE TABLE IF NOT EXISTS product_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        captured_at TEXT NOT NULL,
        pid TEXT,
        shop_id TEXT,
        produto TEXT NOT NULL,
        preco REAL,
        vendidos_30d INTEGER,
        vendidos_historicos INTEGER,
        avaliacao REAL,
        qtd_avaliacoes INTEGER,
        favoritos INTEGER,
        estoque INTEGER,
        loja TEXT,
        url TEXT,
        source TEXT DEFAULT 'nexscope'
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_snap_pid_time ON product_snapshots(pid, captured_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_snap_title_time ON product_snapshots(produto, captured_at)")
    c.commit()
    c.close()

def save_snapshot(products, captured_at=None):
    init_db()
    captured_at = captured_at or datetime.now(timezone.utc).isoformat()
    c = _conn()
    for p in products or []:
        c.execute("""
        INSERT INTO product_snapshots (
            captured_at,pid,shop_id,produto,preco,vendidos_30d,vendidos_historicos,
            avaliacao,qtd_avaliacoes,favoritos,estoque,loja,url,source
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            captured_at,
            str(p.get("pid") or ""),
            str(p.get("shop_id") or ""),
            p.get("produto") or "",
            p.get("preco"),
            p.get("vendidos_30d"),
            p.get("vendidos_historicos"),
            p.get("avaliacao"),
            p.get("qtd_avaliacoes"),
            p.get("favoritos"),
            p.get("estoque"),
            p.get("loja") or "",
            p.get("url") or "",
            "nexscope",
        ))
    c.commit()
    c.close()
    return captured_at

def _identity(product):
    pid = str(product.get("pid") or "")
    if pid:
        return "pid = ?", [pid]
    return "produto = ?", [product.get("produto") or ""]

def get_history(product, limit=20):
    init_db()
    clause, args = _identity(product)
    c = _conn()
    rows = c.execute(
        f"SELECT * FROM product_snapshots WHERE {clause} ORDER BY captured_at DESC LIMIT ?",
        args + [int(limit)]
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]

def _delta(new, old, key):
    try:
        return float(new.get(key) or 0) - float(old.get(key) or 0)
    except Exception:
        return 0.0


def scale_signal(product):
    hist = get_history(product, 20)
    if len(hist) < 2:
        return {
            "status":"🆕 Sem histórico suficiente",
            "score":0,
            "history_points":len(hist),
            "sold30_delta":0,
            "sales_velocity":0,
            "ratings_delta":0,
            "favorites_delta":0,
            "price_change_pct":0,
            "reason":"Precisamos de pelo menos 2 coletas em momentos diferentes."
        }

    newest = hist[0]
    oldest = hist[-1]
    prev = hist[1]

    sold30_delta = _delta(newest, oldest, "vendidos_30d")
    recent_sold30_delta = _delta(newest, prev, "vendidos_30d")
    ratings_delta = _delta(newest, oldest, "qtd_avaliacoes")
    favorites_delta = _delta(newest, oldest, "favoritos")

    score = 20
    reasons = []

    if sold30_delta >= 1000:
        score += 32; reasons.append("vendas 30d subiram muito")
    elif sold30_delta >= 300:
        score += 24; reasons.append("vendas 30d subiram forte")
    elif sold30_delta >= 100:
        score += 16; reasons.append("vendas 30d cresceram")
    elif sold30_delta > 0:
        score += 8; reasons.append("vendas 30d avançando")
    elif sold30_delta < 0:
        score -= 8; reasons.append("vendas 30d recuando")

    if recent_sold30_delta >= 300:
        score += 18; reasons.append("velocidade recente alta")
    elif recent_sold30_delta >= 100:
        score += 12; reasons.append("boa velocidade recente")
    elif recent_sold30_delta > 0:
        score += 5; reasons.append("movimento recente positivo")

    if ratings_delta >= 100:
        score += 14; reasons.append("avaliações crescendo muito")
    elif ratings_delta >= 20:
        score += 9; reasons.append("avaliações crescendo")
    elif ratings_delta > 0:
        score += 4; reasons.append("novas avaliações")

    if favorites_delta >= 100:
        score += 8; reasons.append("favoritos crescendo")
    elif favorites_delta > 0:
        score += 3; reasons.append("favoritos subindo")

    current_sales = int(newest.get("vendidos_30d") or 0)
    if current_sales >= 10000:
        score += 8; reasons.append("volume atual muito alto")
    elif current_sales >= 3000:
        score += 5; reasons.append("volume atual alto")
    elif current_sales >= 1000:
        score += 3; reasons.append("bom volume atual")

    p0 = float(oldest.get("preco") or 0)
    p1 = float(newest.get("preco") or 0)
    price_change_pct = ((p1-p0)/p0*100) if p0 > 0 and p1 > 0 else 0

    if price_change_pct <= -15:
        score -= 6; reasons.append("crescimento pode estar vindo de forte corte de preço")
    elif price_change_pct >= 10 and sold30_delta > 0:
        score += 4; reasons.append("crescendo mesmo com preço maior")

    score = max(0, min(100, score))

    has_growth = sold30_delta > 0 or ratings_delta > 0 or favorites_delta > 0
    if not has_growth:
        status = "🟣 Estável / cedo demais"
        score = min(score, 49)
    elif score >= 85:
        status = "🚀 Escalando forte"
    elif score >= 70:
        status = "🟢 Acelerando"
    elif score >= 50:
        status = "🟡 Crescendo"
    else:
        status = "⚪ Movimento fraco"

    return {
        "status":status,
        "score":score,
        "history_points":len(hist),
        "sold30_delta":sold30_delta,
        "sales_velocity":recent_sold30_delta,
        "ratings_delta":ratings_delta,
        "favorites_delta":favorites_delta,
        "price_change_pct":round(price_change_pct,2),
        "reason":", ".join(reasons) if reasons else "Sem mudança mensurável ainda."
    }

def competitor_vulnerability(products):
    rows=[]
    for p in products or []:
        sold=int(p.get("vendidos_30d") or 0)
        rating=float(p.get("avaliacao") or 0)
        reviews=int(p.get("qtd_avaliacoes") or 0)
        price=float(p.get("preco") or 0)
        score=0
        gaps=[]
        if sold >= 300: score += 20
        if sold >= 1000: score += 10
        if rating and rating < 4.7:
            score += 22; gaps.append("nota vulnerável")
        elif rating and rating < 4.8:
            score += 12; gaps.append("nota abaixo dos melhores")
        if sold >= 500 and reviews < 100:
            score += 18; gaps.append("poucas avaliações para o volume")
        elif sold >= 1000 and reviews < 300:
            score += 10; gaps.append("prova social relativamente baixa")
        if price >= 50:
            score += 8; gaps.append("ticket mais alto")
        if p.get("oficial")=="Não":
            score += 6; gaps.append("loja não oficial")
        if p.get("preferida")=="Não":
            score += 4; gaps.append("loja não verificada")
        rows.append({
            "vulnerabilidade":max(0,min(100,score)),
            "loja":p.get("loja",""),"produto":p.get("produto",""),
            "preco":price,"vendidos_30d":sold,"avaliacao":rating,
            "qtd_avaliacoes":reviews,"brechas":", ".join(gaps) if gaps else "sem brecha óbvia",
            "url":p.get("url","")
        })
    return sorted(rows,key=lambda x:x["vulnerabilidade"],reverse=True)

def forecast_from_signal(product, signal):
    base=max(0,int(product.get("vendidos_30d") or 0))
    score=int(signal.get("score") or 0)
    if score>=85:
        factors=(1.05,1.20,1.40)
    elif score>=70:
        factors=(1.00,1.12,1.25)
    elif score>=50:
        factors=(0.95,1.05,1.15)
    else:
        factors=(0.85,0.95,1.05)
    return {"conservador":int(base*factors[0]),"base":int(base*factors[1]),"agressivo":int(base*factors[2])}

def build_alerts(signal, vulnerabilities):
    alerts=[]
    s=int(signal.get("score") or 0)
    if s>=85: alerts.append("🚀 Produto em aceleração forte")
    elif s>=70: alerts.append("🟢 Produto acelerando")
    if signal.get("ratings_delta",0)>=20: alerts.append("⭐ Avaliações crescendo")
    if signal.get("price_change_pct",0)<=-10: alerts.append("🏷️ Preço caiu mais de 10%")
    if vulnerabilities and vulnerabilities[0].get("vulnerabilidade",0)>=50:
        alerts.append("🎯 Concorrente com brecha relevante")
    return alerts or ["ℹ️ Nenhum alerta forte neste momento"]
