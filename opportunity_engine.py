import re
import unicodedata
from statistics import median

CATEGORY_RULES = {
    "Casa e Organização": {
        "positive": ["organizador","organizacao","geladeira","banheiro","guarda roupa","lavanderia","cesto","caixa","prateleira"],
        "negative": ["amigdala","garganta","unha","furadeira","carro","pet","cachorro","gato"],
    },
    "Pets": {
        "positive": ["pet","cachorro","cao","gato","coleira","guia","tapete higienico","arranhador","brinquedo"],
        "negative": ["carro","notebook","furadeira","maquiagem","geladeira"],
    },
    "Automotivo": {
        "positive": ["carro","veicular","automotivo","automotiva","moto","suporte celular","organizador carro","limpeza automotiva"],
        "negative": ["gato","cachorro","geladeira","maquiagem","bebe"],
    },
    "Beleza e Cuidados": {
        "positive": ["cabelo","maquiagem","unha","beleza","escova","cuidados pessoais","organizador maquiagem"],
        "negative": ["carro","furadeira","pet","gato","cachorro"],
    },
    "Ferramentas e Utilidades": {
        "positive": ["ferramenta","furadeira","chave","broca","alicate","reparo","parafuso","porca","organizacao ferramentas"],
        "negative": ["amigdala","garganta","dental","medico","medical","saude","beleza","pet"],
    },
    "Escritório e Estudo": {
        "positive": ["escritorio","notebook","laptop","mesa","cabos","material escritorio","suporte notebook"],
        "negative": ["carro","pet","cachorro","gato","maquiagem"],
    },
    "Infantil e Família": {
        "positive": ["bebe","infantil","crianca","brinquedo educativo","seguranca infantil","organizacao bebe"],
        "negative": ["carro","furadeira","amigdala","garganta"],
    },
    "Cozinha": {
        "positive": ["cozinha","panela","pote","pia","alimento","utensilio","tampa","descanso panela","organizador panelas"],
        "negative": ["carro","pet","gato","cachorro","amigdala","garganta"],
    },
}

RISK_KEYWORDS = {
    "Saúde/regulado": ["amigdala","garganta","dental","dentario","medico","medical","cirurgico","cirurgica","termometro","oximetro","pressao arterial","remedio","medicamento"],
    "Marca/IP": ["disney","marvel","harry potter","bts","nike","adidas","apple","samsung","lego"],
    "Alto risco operacional": ["vidro","fragil","liquido","quimico","bateria litio","inflamavel"],
}

STOP = {
    "de","da","do","das","dos","para","com","sem","e","o","a","os","as","em","um","uma",
    "universal","novo","nova","produto","kit","peca","pcs","pc","original","premium","modelo",
    "360","graus","cor","cores","tamanho","grande","pequeno","multifuncional"
}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii","ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def tokens(s):
    return [t for t in norm(s).split() if len(t) >= 3 and t not in STOP]

def category_relevance(product, category):
    title = norm(product.get("produto",""))
    rules = CATEGORY_RULES.get(category, {})
    if not rules:
        return 50, "sem regra específica"
    pos_hits = sum(1 for x in rules.get("positive",[]) if norm(x) in title)
    neg_hits = sum(1 for x in rules.get("negative",[]) if norm(x) in title)
    score = max(0, min(100, 30 + min(60,pos_hits*25) - min(70,neg_hits*40)))
    return score, f"{pos_hits} sinais positivos, {neg_hits} negativos"

def risk_flags(product):
    title = norm(product.get("produto",""))
    flags=[]
    for label,kws in RISK_KEYWORDS.items():
        if any(norm(k) in title for k in kws):
            flags.append(label)
    return flags

def similarity(a,b):
    ta,tb=set(tokens(a)),set(tokens(b))
    if not ta or not tb:
        return 0.0
    inter=len(ta & tb)
    union=len(ta | tb)
    j=inter/union if union else 0
    containment=inter/min(len(ta),len(tb))
    return max(j,containment*0.85)

def cluster_products(products, threshold=0.64):
    clusters=[]
    for p in products or []:
        placed=False
        for c in clusters:
            if similarity(p.get("produto",""), c["representative"].get("produto","")) >= threshold:
                c["items"].append(p)
                if int(p.get("vendidos_30d") or 0) > int(c["representative"].get("vendidos_30d") or 0):
                    c["representative"]=p
                placed=True
                break
        if not placed:
            clusters.append({"representative":p,"items":[p]})
    return clusters

def opportunity_today(product, cluster_size=1):
    sold=int(product.get("vendidos_30d") or 0)
    rating=float(product.get("avaliacao") or 0)
    reviews=int(product.get("qtd_avaliacoes") or 0)
    price=float(product.get("preco") or 0)
    score=0
    reasons=[]

    if sold>=10000: score+=28; reasons.append("demanda muito alta")
    elif sold>=3000: score+=24; reasons.append("demanda alta")
    elif sold>=1000: score+=19; reasons.append("boa demanda")
    elif sold>=300: score+=12; reasons.append("demanda presente")
    elif sold>=100: score+=7; reasons.append("demanda inicial")

    if rating>=4.9 and reviews>=300: score+=12; reasons.append("prova social muito forte")
    elif rating>=4.75 and reviews>=100: score+=9; reasons.append("boa prova social")
    elif rating and rating<4.65 and sold>=500: score+=10; reasons.append("vende apesar de nota vulnerável")

    if sold>=1000 and reviews<500: score+=15; reasons.append("barreira de avaliações vencível")
    elif sold>=300 and reviews<150: score+=11; reasons.append("prova social ainda atacável")
    elif reviews>5000: score-=8; reasons.append("forte barreira de avaliações")

    if 20<=price<=120: score+=12; reasons.append("ticket interessante")
    elif 12<=price<20: score+=7; reasons.append("ticket baixo com giro")
    elif price>250: score-=6; reasons.append("ticket alto")

    if cluster_size>=8: score-=12; reasons.append("muitos anúncios muito semelhantes")
    elif cluster_size>=4: score-=6; reasons.append("cluster concorrido")
    elif cluster_size<=2: score+=5; reasons.append("poucos similares na amostra")

    return max(0,min(100,score)),reasons

def final_action(opp,scale,history,risk,cluster_size,reviews):
    if risk:
        return "🔴 REVISAR RISCO"
    if opp>=65 and scale>=70:
        return "🚀 PRIORIDADE MÁXIMA"
    if opp>=72:
        return "🟢 INVESTIGAR AGORA"
    if opp>=58:
        return "🟡 MONITORAR + INVESTIGAR"
    if cluster_size>=8 and reviews>=1500:
        return "🟠 MERCADO CONCORRIDO"
    return "⚪ BAIXA PRIORIDADE"

def build_clusters_with_scores(products, scale_func):
    out=[]
    for c in cluster_products(products):
        rep=c["representative"]
        items=c["items"]
        sig=scale_func(rep)
        opp,reasons=opportunity_today(rep,len(items))
        risks=risk_flags(rep)
        action=final_action(opp,int(sig.get("score") or 0),int(sig.get("history_points") or 0),risks,len(items),int(rep.get("qtd_avaliacoes") or 0))
        prices=[float(x.get("preco") or 0) for x in items if float(x.get("preco") or 0)>0]
        out.append({
            "acao":action,
            "score_oportunidade_hoje":opp,
            "score_aceleracao":int(sig.get("score") or 0),
            "momento":sig.get("status"),
            "snapshots":int(sig.get("history_points") or 0),
            "produto":rep.get("produto",""),
            "anuncios_similares":len(items),
            "preco_representante":rep.get("preco"),
            "preco_mediano_cluster":round(median(prices),2) if prices else None,
            "vendidos_30d":int(rep.get("vendidos_30d") or 0),
            "avaliacao":rep.get("avaliacao"),
            "qtd_avaliacoes":int(rep.get("qtd_avaliacoes") or 0),
            "loja":rep.get("loja",""),
            "risco":", ".join(risks) if risks else "Baixo",
            "por_que":", ".join(reasons[:6]),
            "url":rep.get("url",""),
            "_product":rep,
        })
    priority={"🚀 PRIORIDADE MÁXIMA":5,"🟢 INVESTIGAR AGORA":4,"🟡 MONITORAR + INVESTIGAR":3,"🟠 MERCADO CONCORRIDO":2,"⚪ BAIXA PRIORIDADE":1,"🔴 REVISAR RISCO":0}
    out.sort(key=lambda r:(priority.get(r["acao"],0),r["score_oportunidade_hoje"],r["score_aceleracao"],r["vendidos_30d"]),reverse=True)
    return out
