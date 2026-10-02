import re
from datetime import datetime
from urllib.parse import urlparse
from collectors.brave_search import BraveSearchCollector

CATEGORY_LABELS = {
    "Geral / todas": "GERAL",
    "Pets": "pets",
    "Casa e cozinha": "casa cozinha",
    "Organização": "organizacao",
    "Beleza": "beleza",
    "Ferramentas": "ferramentas",
    "Automotivo": "automotivo",
    "Esporte e lazer": "esporte lazer",
    "Bebê e família": "bebe familia",
    "Eletrônicos e acessórios": "eletronicos acessorios",
}

CATEGORY_TERMS = {
    "Pets": ["acessório para cachorro gato","higiene pet","organização alimentação pet","brinquedo pet prático"],
    "Casa e cozinha": ["utensílio cozinha prático","organizador cozinha","limpeza doméstica produto","acessório casa funcional"],
    "Organização": ["organizador guarda roupa","organizador cozinha","organizador banheiro","organizador gaveta"],
    "Beleza": ["acessório cabelo","organizador maquiagem","acessório skincare não eletrônico","acessório beleza portátil"],
    "Ferramentas": ["ferramenta manual prática","acessório furadeira","kit reparo doméstico","ferramenta compacta manutenção"],
    "Automotivo": ["organizador automotivo","acessório limpeza carro","acessório interior carro","suporte automotivo"],
    "Esporte e lazer": ["acessório treino","acessório caminhada corrida","organizador esporte","acessório lazer portátil"],
    "Bebê e família": ["organizador bebê","acessório alimentação bebê","acessório passeio bebê","produto rotina família"],
    "Eletrônicos e acessórios": ["suporte celular","organizador cabos","acessório eletrônico pequeno","acessório carregamento organização"],
}

GENERAL_ROTATION = [
    ("Pets","acessório pet"),
    ("Casa e cozinha","utilidade cozinha"),
    ("Organização","organizador casa"),
    ("Ferramentas","ferramenta compacta"),
    ("Automotivo","acessório automotivo"),
    ("Beleza","acessório beleza"),
    ("Eletrônicos e acessórios","acessório eletrônico"),
    ("Esporte e lazer","acessório treino"),
]

MODE_HINTS = {
    "Geral": "produto específico com demanda e potencial de revenda",
    "Sazonalidade": "produto específico com procura sazonal nos próximos meses",
    "Recorrência": "produto consumível ou de recompra recorrente",
    "Problema → solução": "produto específico que resolve uma dor prática",
    "Fornecedor / atacado": "produto específico com atacadista distribuidor ou fabricante",
}

MARKETPLACE_DOMAINS = ("shopee.com.br","mercadolivre.com.br","amazon.com.br","magazineluiza.com.br","americanas.com.br")
SUPPLIER_WORDS = ("atacado","distribuidor","distribuidora","fabricante","fábrica","fabrica","fornecedor")
PRODUCT_WORDS = (
    "kit","organizador","suporte","tapete","escova","capa","protetor","refil","dispensador",
    "porta","gancho","caixa","bolsa","estojo","bandeja","prateleira","adaptador","cabo",
    "filtro","rodo","escorredor","pote","garrafa","comedouro","bebedouro","brinquedo",
    "arranhador","coleira","guia","luva","almofada","cesto","lixeira","chave","alicate",
    "broca","jogo","aplicador","removedor","esponja"
)

GENERIC_PHRASES = (
    "produtos mais vendidos","mais vendidos na shopee","mais vendidos na amazon",
    "produtos em alta","tendências 2026","tendencias 2026","apostas para 2026",
    "o que vender","ideias de produtos","produtos para vender","melhores produtos",
    "lista de produtos","guia completo","marketplace -","maior petshop online",
    "loja online","53 produtos","50 produtos","100 produtos","top 10","top 20",
    "tiktok shop brasil","categorias mais vendidas"
)

ARTICLE_DOMAINS = ("blog.","medium.com","uol.com.br","exame.com","shopify.com","nuvemshop.com.br","tray.com.br","sebrae.com.br")

def _norm(text):
    return re.sub(r"\s+"," ",(text or "").lower()).strip()

def _clean_title(title):
    title = re.sub(r"\s+"," ",title or "").strip()
    parts = re.split(r"\s+[|–—]\s+", title)
    if parts and len(parts[0]) >= 8:
        title = parts[0]
    return title[:180]

def _is_generic(title, desc, domain):
    text = _norm(f"{title} {desc}")
    if any(p in text for p in GENERIC_PHRASES):
        return True
    if any(domain.startswith(d) or d in domain for d in ARTICLE_DOMAINS):
        if not any(w in _norm(title) for w in PRODUCT_WORDS):
            return True
    if re.match(r"^(como|por que|porque|quais|o que|guia|tendências|tendencias)\b", _norm(title)):
        return True
    return False

def _looks_product(title, desc, domain):
    text = _norm(f"{title} {desc}")
    title_n = _norm(title)
    signals = 0
    if any(d in domain for d in MARKETPLACE_DOMAINS): signals += 2
    if any(w in text for w in PRODUCT_WORDS): signals += 2
    if any(w in text for w in SUPPLIER_WORDS): signals += 1
    if re.search(r"\bkit\b|\b\d+\s*(pcs|peças|pecas|unidades|cm|mm|ml|l)\b", text): signals += 1
    if 3 <= len(title_n.split()) <= 18: signals += 1
    return signals >= 2

def _source_type(domain, text):
    t=_norm(text)
    if any(d in domain for d in MARKETPLACE_DOMAINS): return "Marketplace"
    if any(w in t for w in SUPPLIER_WORDS): return "Fornecedor/atacado"
    return "Produto/fonte pública"

def build_queries(category="Geral / todas", mode="Geral", max_queries=6):
    year=datetime.now().year
    if category=="Geral / todas":
        seeds=GENERAL_ROTATION
    else:
        seeds=[(category,t) for t in CATEGORY_TERMS.get(category,[CATEGORY_LABELS.get(category,category)])]

    q=[]
    for _,term in seeds:
        q.extend([
            f'{term} comprar "mais vendidos" Brasil {year}',
            f'{term} site:mercadolivre.com.br produto',
            f'{term} atacado fornecedor distribuidor Brasil',
            f'{term} kit produto avaliações Brasil',
        ])
        if mode=="Sazonalidade":
            q.append(f'{term} produto sazonal procura próximos meses Brasil {year}')
        elif mode=="Recorrência":
            q.append(f'{term} refil consumo recorrente recompra Brasil')
        elif mode=="Problema → solução":
            q.append(f'{term} produto solução problema avaliações reclamações')
        elif mode=="Fornecedor / atacado":
            q.append(f'{term} fabricante atacado preço caixa fechada Brasil')

    seen=[]; used=set()
    for x in q:
        if x not in used:
            seen.append(x); used.add(x)
    return seen[:max(1,int(max_queries))]

def _score(item, query, rank):
    title=item.get("title","")
    desc=item.get("description","")
    domain=(item.get("source_domain") or "").lower()
    text=_norm(f"{title} {desc}")
    score=42; reasons=[]

    if any(d in domain for d in MARKETPLACE_DOMAINS):
        score += 15; reasons.append("página de marketplace")
    if any(w in text for w in PRODUCT_WORDS):
        score += 12; reasons.append("produto específico")
    if any(w in text for w in SUPPLIER_WORDS):
        score += 10; reasons.append("sinal de fornecedor")
    if "kit" in text:
        score += 5; reasons.append("potencial de kit")
    if "avalia" in text:
        score += 4; reasons.append("sinal de avaliações")
    if "mais vendido" in text or "vendidos" in text:
        score += 7; reasons.append("sinal de demanda")
    if re.search(r"r\$\s?\d+|preço|preco", text):
        score += 4; reasons.append("sinal de preço")
    score += max(0,8-int(rank or 10))
    return min(100,max(0,score)), list(dict.fromkeys(reasons))[:4]

def classification(score):
    if score>=82: return "🔥 Prioridade alta"
    if score>=70: return "🟢 Investigar agora"
    if score>=58: return "🟡 Radar"
    return "⚪ Baixa prioridade"

def _why(reasons, source_type):
    if reasons:
        return f"{source_type}: " + ", ".join(reasons) + ". Validar margem, concorrência e logística."
    return f"{source_type}. Validar demanda, fornecedor, margem, concorrência e logística."

def run_opportunity_radar(category="Geral / todas", mode="Geral", max_queries=6, results_per_query=8):
    collector=BraveSearchCollector(count=max(1,min(20,int(results_per_query))))
    if not collector.enabled():
        return {"enabled":False,"message":"BRAVE_SEARCH_API_KEY não configurada.","queries_used":0,"rows":[]}

    queries=build_queries(category,mode,max_queries)
    rows=[]; errors=[]; seen=set(); discarded_generic=0

    for query in queries:
        try:
            results=collector.search(query)
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            continue

        for item in results:
            url=item.get("url","")
            if not url or url in seen:
                continue
            seen.add(url)
            title=_clean_title(item.get("title",""))
            desc=item.get("description","") or ""
            domain=(item.get("source_domain") or urlparse(url).netloc).lower()

            if _is_generic(title,desc,domain) or not _looks_product(title,desc,domain):
                discarded_generic += 1
                continue

            score,reasons=_score(item,query,item.get("rank",10))
            stype=_source_type(domain,f"{title} {desc}")
            rows.append({
                "score_radar":score,
                "classificacao":classification(score),
                "oportunidade":title,
                "por_que_agora":_why(reasons,stype),
                "fonte":domain,
                "url":url,
                "consulta":query,
                "descricao":desc[:400],
                "rank_fonte":item.get("rank"),
            })

    rows.sort(key=lambda x:(x["score_radar"],-(x.get("rank_fonte") or 99)),reverse=True)
    return {
        "enabled":True,
        "message":"Garimpo de produtos concluído.",
        "queries_used":len(queries),
        "results_found":len(rows),
        "generic_discarded":discarded_generic,
        "errors":errors,
        "rows":rows,
    }
