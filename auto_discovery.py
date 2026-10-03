from scale_radar import scale_signal

CATEGORY_SEEDS = {
    "Casa e Organização": ["organizador cozinha","organizador geladeira","organizador banheiro","organizador guarda roupa","organizador lavanderia"],
    "Pets": ["acessorios cachorro","acessorios gato","brinquedo pet","tapete higienico cachorro","arranhador gato"],
    "Automotivo": ["acessorios carro","suporte celular carro","organizador carro","limpeza automotiva","acessorios moto"],
    "Beleza e Cuidados": ["acessorios cabelo","organizador maquiagem","escova cabelo","acessorios unhas","cuidados pessoais"],
    "Ferramentas e Utilidades": ["ferramenta manual","organizacao ferramentas","acessorios furadeira","utilidades reparo","ferramenta casa"],
    "Escritório e Estudo": ["organizador escritorio","suporte notebook","acessorios mesa","material escritorio","organizacao cabos"],
    "Infantil e Família": ["organizacao bebe","acessorios bebe","brinquedo educativo","organizacao infantil","seguranca infantil casa"],
    "Cozinha": ["utensilios cozinha","organizador panelas","potes cozinha","acessorios pia cozinha","armazenamento alimentos"],
}

def discovery_plan(selected_categories, depth="Normal"):
    per_cat = {"Rápido":2,"Normal":3,"Profundo":5}.get(depth,3)
    plan=[]
    for cat in selected_categories or []:
        for kw in CATEGORY_SEEDS.get(cat,[])[:per_cat]:
            plan.append({"category":cat,"keyword":kw})
    return plan

def normalize_product_key(p):
    pid=str(p.get("pid") or "").strip()
    shop_id=str(p.get("shop_id") or "").strip()
    if pid:
        return ("pid",pid,shop_id)
    return ("title"," ".join(str(p.get("produto") or "").lower().split())[:180])

def merge_discovery_results(batches):
    merged={}
    for batch in batches:
        for p in batch.get("products",[]):
            k=normalize_product_key(p)
            if k not in merged:
                merged[k]=dict(p)
                merged[k]["_cats"]=set()
                merged[k]["_terms"]=set()
            merged[k]["_cats"].add(batch.get("category",""))
            merged[k]["_terms"].add(batch.get("keyword",""))
    out=[]
    for p in merged.values():
        p["categorias_descoberta"]=", ".join(sorted(x for x in p.pop("_cats") if x))
        p["termos_descoberta"]=", ".join(sorted(x for x in p.pop("_terms") if x))
        out.append(p)
    return out

def opportunity_score(p, sig):
    sold=int(p.get("vendidos_30d") or 0)
    rating=float(p.get("avaliacao") or 0)
    reviews=int(p.get("qtd_avaliacoes") or 0)
    price=float(p.get("preco") or 0)
    score=0
    why=[]
    if sold>=10000: score+=22; why.append("demanda muito alta")
    elif sold>=3000: score+=18; why.append("demanda alta")
    elif sold>=1000: score+=14; why.append("boa demanda")
    elif sold>=300: score+=9; why.append("demanda presente")
    elif sold>=100: score+=5; why.append("demanda inicial")
    if rating>=4.85 and reviews>=300: score+=10; why.append("prova social forte")
    elif rating>=4.7 and reviews>=100: score+=6; why.append("boa prova social")
    elif rating and rating<4.6 and sold>=500: score+=8; why.append("vende apesar de nota vulnerável")
    if sold>=1000 and reviews<500: score+=12; why.append("barreira de avaliações vencível")
    elif sold>=300 and reviews<150: score+=8; why.append("concorrência possivelmente vencível")
    if 20<=price<=120: score+=8; why.append("ticket interessante")
    elif 10<=price<20: score+=4; why.append("ticket baixo com giro")
    ss=int(sig.get("score") or 0)
    if ss>=85: score+=30; why.append("aceleração forte")
    elif ss>=70: score+=22; why.append("produto acelerando")
    elif ss>=50: score+=12; why.append("crescimento detectado")
    elif sig.get("history_points",0)>=2: score+=2; why.append("histórico ainda estável")
    score=max(0,min(100,score))
    label="🚀 Prioridade alta" if score>=80 else "🟢 Investigar" if score>=65 else "🟡 Monitorar" if score>=50 else "⚪ Baixa prioridade"
    return score,label,", ".join(why[:6])

def rank_discovered(products):
    rows=[]
    for p in products or []:
        sig=scale_signal(p)
        score,label,reason=opportunity_score(p,sig)
        rows.append({
            "score_oportunidade":score,
            "prioridade":label,
            "momento":sig.get("status"),
            "score_escala":sig.get("score"),
            "snapshots":sig.get("history_points"),
            "produto":p.get("produto",""),
            "preco":p.get("preco"),
            "vendidos_30d":p.get("vendidos_30d",0),
            "avaliacao":p.get("avaliacao"),
            "qtd_avaliacoes":p.get("qtd_avaliacoes",0),
            "loja":p.get("loja",""),
            "categorias":p.get("categorias_descoberta",""),
            "por_que":reason,
            "url":p.get("url",""),
            "_product":p,
        })
    rows.sort(key=lambda r:(r["score_oportunidade"],r["score_escala"],r["vendidos_30d"]),reverse=True)
    return rows

def estimated_calls(selected_categories, depth="Normal"):
    return len(discovery_plan(selected_categories, depth))

def discovery_run_summary(ranked, errors=None):
    errors = errors or []
    ranked = ranked or []
    return {
        "unique_products": len(ranked),
        "priority_high": len([r for r in ranked if r.get("score_oportunidade",0) >= 80]),
        "investigate": len([r for r in ranked if 65 <= r.get("score_oportunidade",0) < 80]),
        "with_history": len([r for r in ranked if r.get("snapshots",0) >= 2]),
        "errors": len(errors),
    }

def top_candidates(ranked, limit=10):
    return list((ranked or [])[:max(1,int(limit))])
