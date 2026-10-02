import os
import re
from datetime import datetime
from urllib.parse import urlparse
from collectors.brave_search import BraveSearchCollector

CATEGORY_LABELS = {
    "Geral / todas": "produtos úteis para casa, pets, beleza, organização, ferramentas e acessórios",
    "Pets": "produtos para cães e gatos",
    "Casa e cozinha": "utilidades domésticas, cozinha e organização da casa",
    "Organização": "organizadores para casa, cozinha, banheiro e guarda-roupa",
    "Beleza": "acessórios de beleza e cuidados pessoais não medicamentosos",
    "Ferramentas": "ferramentas e acessórios para reparos e manutenção",
    "Automotivo": "acessórios automotivos práticos",
    "Esporte e lazer": "acessórios para esporte, treino e lazer",
    "Bebê e família": "acessórios práticos para rotina de bebês e família",
    "Eletrônicos e acessórios": "acessórios eletrônicos de baixo risco e fácil envio",
}

MODE_HINTS = {
    "Geral": "oportunidade de produto com demanda crescente, boa margem e concorrência vencível",
    "Sazonalidade": "produto sazonal com pico de demanda se aproximando",
    "Recorrência": "produto de recompra frequente ou consumo recorrente",
    "Problema → solução": "produto que resolve uma dor ou problema recorrente do consumidor",
    "Fornecedor / atacado": "produto com fornecedor atacadista, distribuidor ou fabricante no Brasil",
}

HIGH_SIGNALS = {
    "em alta": 10,
    "tendência": 10,
    "tendencias": 8,
    "mais vendido": 10,
    "mais vendidos": 10,
    "best seller": 10,
    "viral": 7,
    "crescimento": 8,
    "procura": 6,
    "demanda": 8,
    "atacado": 8,
    "fornecedor": 8,
    "distribuidor": 8,
    "fabricante": 8,
    "avaliações": 4,
    "avaliacoes": 4,
    "reclamações": 4,
    "reclamacoes": 4,
    "problema": 5,
    "solução": 5,
    "solucao": 5,
    "kit": 5,
    "recompra": 6,
}

LOW_SIGNALS = {
    "grátis": -4,
    "gratis": -4,
    "emprego": -12,
    "vaga": -12,
    "curso": -8,
    "pdf": -4,
    "download": -5,
    "manual": -3,
}

TRUST_DOMAINS = (
    "google.com", "amazon.com", "mercadolivre.com", "magazineluiza.com", "uol.com.br",
    "globo.com", "exame.com", "sebrae.com.br", "gov.br", "statista.com", "trends.google"
)


def _clean_title(title):
    title = re.sub(r"\s+", " ", title or "").strip()
    # Remove common site suffixes while retaining the useful headline/listing text.
    parts = re.split(r"\s+[|–—-]\s+", title)
    if len(parts) > 1 and len(parts[0]) >= 18:
        title = parts[0]
    return title[:180]


def _normalize(text):
    return re.sub(r"[^a-z0-9áéíóúâêôãõç]+", " ", (text or "").lower()).strip()


def build_queries(category="Geral / todas", mode="Geral", max_queries=6):
    subject = CATEGORY_LABELS.get(category, CATEGORY_LABELS["Geral / todas"])
    hint = MODE_HINTS.get(mode, MODE_HINTS["Geral"])
    now = datetime.now()
    month = now.strftime("%m")
    year = now.year

    templates = [
        f'{subject} produtos em alta Brasil {year}',
        f'{subject} tendências de consumo Brasil {year}',
        f'{subject} mais vendidos marketplace Brasil',
        f'{subject} {hint} Brasil',
        f'{subject} novidades atacado fornecedor Brasil {year}',
        f'{subject} problemas reclamações consumidores produto solução',
        f'{subject} produtos virais tendência redes sociais Brasil {year}',
        f'{subject} oportunidade ecommerce margem kit Brasil',
        f'{subject} sazonalidade próximos meses Brasil {year}',
        f'{subject} lançamento fornecedor distribuidor atacado Brasil',
        f'{subject} produtos pequenos leves fácil envio ecommerce',
        f'{subject} recompra recorrência consumidor Brasil',
    ]
    # Preserve order and remove duplicates.
    seen = set(); queries = []
    for q in templates:
        if q not in seen:
            seen.add(q); queries.append(q)
    return queries[:max(1, int(max_queries))]


def _score_result(row, query, rank):
    text = _normalize(f"{row.get('title','')} {row.get('description','')} {query}")
    score = 38
    reasons = []
    for phrase, pts in HIGH_SIGNALS.items():
        if phrase in text:
            score += pts
            if pts >= 7:
                reasons.append(phrase)
    for phrase, pts in LOW_SIGNALS.items():
        if phrase in text:
            score += pts
    score += max(0, 9 - int(rank or 10))
    domain = (row.get("source_domain") or "").lower()
    if any(d in domain for d in TRUST_DOMAINS):
        score += 4
    if "2026" in text or "2025" in text:
        score += 3
    score = max(0, min(100, score))
    reasons = list(dict.fromkeys(reasons))[:4]
    return score, reasons


def _why_now(reasons, mode):
    if reasons:
        return "Sinais encontrados: " + ", ".join(reasons) + "."
    if mode == "Sazonalidade":
        return "Resultado ligado a uma busca de janela sazonal; precisa validar o pico e o lead time."
    if mode == "Recorrência":
        return "Resultado ligado a busca de recompra/recorrência; precisa validar frequência real."
    if mode == "Fornecedor / atacado":
        return "Resultado ligado a busca de fornecedor/atacado; precisa confirmar custo e MOQ."
    if mode == "Problema → solução":
        return "Resultado ligado a uma dor do consumidor; precisa validar intensidade e concorrência."
    return "Resultado apareceu em uma busca de oportunidade; precisa passar pela investigação do Garimpeiro."


def classification(score):
    if score >= 80: return "🔥 Prioridade alta"
    if score >= 68: return "🟢 Investigar agora"
    if score >= 55: return "🟡 Radar"
    return "⚪ Baixa prioridade"


def run_opportunity_radar(category="Geral / todas", mode="Geral", max_queries=6, results_per_query=8):
    collector = BraveSearchCollector(count=max(1, min(20, int(results_per_query))))
    if not collector.enabled():
        return {
            "enabled": False,
            "message": "BRAVE_SEARCH_API_KEY não configurada.",
            "queries_used": 0,
            "rows": [],
        }

    queries = build_queries(category, mode, max_queries)
    rows = []
    errors = []
    seen_urls = set()

    for query in queries:
        try:
            results = collector.search(query)
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            continue
        for item in results:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            score, reasons = _score_result(item, query, item.get("rank", 10))
            rows.append({
                "score_radar": score,
                "classificacao": classification(score),
                "oportunidade": _clean_title(item.get("title", "")),
                "por_que_agora": _why_now(reasons, mode),
                "fonte": item.get("source_domain") or urlparse(url).netloc,
                "url": url,
                "consulta": query,
                "descricao": (item.get("description") or "")[:400],
                "rank_fonte": item.get("rank"),
            })

    rows.sort(key=lambda x: (x["score_radar"], -(x.get("rank_fonte") or 99)), reverse=True)
    return {
        "enabled": True,
        "message": "Garimpo público concluído.",
        "queries_used": len(queries),
        "results_found": len(rows),
        "errors": errors,
        "rows": rows,
    }
