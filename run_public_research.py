
from db import init_db, products, clear_public_search, add_public_search_result
from collectors.brave_search import BraveSearchCollector

def run_public_research():
    init_db()
    collector=BraveSearchCollector()
    if not collector.enabled():
        return {"enabled":False,"message":"BRAVE_SEARCH_API_KEY não configurada.","count":0}

    total=0
    for p in products():
        clear_public_search(p["id"])
        for q in collector.product_research_queries(p):
            try:
                rows=collector.search(q)
            except Exception as e:
                print("Erro de busca:",p["name"],q,e)
                continue
            for r in rows:
                add_public_search_result(
                    p["id"], q, r["title"], r["url"], r["description"],
                    r["source_domain"], r["rank"]
                )
                total+=1
    return {"enabled":True,"message":"Pesquisa pública concluída.","count":total}

if __name__=="__main__":
    print(run_public_research())
