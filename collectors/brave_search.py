
import os, json, urllib.parse, urllib.request
from urllib.parse import urlparse

class BraveSearchCollector:
    ENDPOINT="https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key=None, country="BR", search_lang="pt-br", count=10):
        self.api_key=api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        self.country=country
        self.search_lang=search_lang
        self.count=count

    def enabled(self):
        return bool(self.api_key)

    def search(self, query):
        if not self.api_key:
            return []
        params=urllib.parse.urlencode({
            "q": query,
            "country": self.country,
            "search_lang": self.search_lang,
            "count": self.count
        })
        req=urllib.request.Request(
            self.ENDPOINT+"?"+params,
            headers={
                "Accept":"application/json",
                "Accept-Encoding":"identity",
                "X-Subscription-Token": self.api_key,
                "User-Agent":"GarimpeiroShopeeV4/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data=json.loads(resp.read().decode("utf-8"))
        results=[]
        for i,r in enumerate((data.get("web") or {}).get("results") or [], start=1):
            url=r.get("url","")
            results.append({
                "title":r.get("title",""),
                "url":url,
                "description":r.get("description",""),
                "source_domain":urlparse(url).netloc,
                "rank":i
            })
        return results

    def product_research_queries(self, product):
        kw=product["keyword"]
        return [
            f'{kw} preço comprar Brasil',
            f'{kw} atacado fornecedor Brasil',
            f'{kw} avaliações reclamações',
            f'{kw} tendência 2026'
        ]
