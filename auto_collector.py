import csv
import io
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

DEFAULT_TIMEOUT=12

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _read_url(url, headers=None, timeout=DEFAULT_TIMEOUT):
    req=urllib.request.Request(url,headers=headers or {"User-Agent":"GarimpeiroShopee/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        raw=resp.read()
        ctype=(resp.headers.get("Content-Type") or "").lower()
    return raw,ctype

def _csv_rows(raw):
    text=raw.decode("utf-8-sig","replace")
    return list(csv.DictReader(io.StringIO(text)))

def _json_rows(raw):
    obj=json.loads(raw.decode("utf-8","replace"))
    if isinstance(obj,list):
        return obj
    if isinstance(obj,dict):
        for key in ("items","results","data","products","rows"):
            if isinstance(obj.get(key),list):
                return obj[key]
    raise ValueError("JSON não contém uma lista reconhecível de registros.")

def fetch_source(source):
    stype=(source.get("type") or "").lower()
    url=(source.get("url") or "").strip()
    if not url:
        raise ValueError("Fonte sem URL.")

    headers={}
    token_env=(source.get("token_env") or "").strip()
    if token_env:
        token=os.getenv(token_env)
        if token:
            header_name=source.get("token_header") or "Authorization"
            prefix=source.get("token_prefix") or "Bearer "
            headers[header_name]=prefix+token

    raw,ctype=_read_url(url,headers=headers)
    if stype=="csv" or "text/csv" in ctype or url.lower().endswith(".csv"):
        rows=_csv_rows(raw)
    elif stype=="json" or "application/json" in ctype or url.lower().endswith(".json"):
        rows=_json_rows(raw)
    else:
        # Try JSON first, then CSV.
        try:
            rows=_json_rows(raw)
        except Exception:
            rows=_csv_rows(raw)

    return {
        "name":source.get("name") or url,
        "kind":source.get("kind") or "supplier",
        "url":url,
        "rows":rows,
        "count":len(rows),
        "fetched_at":_now_iso(),
    }

def load_registry(path):
    p=str(path)
    if not os.path.exists(p):
        return []
    with open(p,"r",encoding="utf-8") as f:
        data=json.load(f)
    return data if isinstance(data,list) else data.get("sources",[])

def refresh_registry(path):
    sources=load_registry(path)
    results=[]
    for src in sources:
        if src.get("enabled",True) is False:
            continue
        try:
            result=fetch_source(src)
            result["ok"]=True
            results.append(result)
        except Exception as exc:
            results.append({
                "name":src.get("name") or src.get("url",""),
                "kind":src.get("kind") or "supplier",
                "url":src.get("url",""),
                "rows":[],
                "count":0,
                "fetched_at":_now_iso(),
                "ok":False,
                "error":str(exc),
            })
    return results

def merge_rows(refresh_results, kind):
    merged=[]
    provenance=[]
    for res in refresh_results:
        if not res.get("ok") or res.get("kind")!=kind:
            continue
        for row in res.get("rows",[]):
            x=dict(row)
            x["_source_name"]=res.get("name")
            x["_source_url"]=res.get("url")
            x["_fetched_at"]=res.get("fetched_at")
            merged.append(x)
        provenance.append({
            "source":res.get("name"),
            "count":res.get("count",0),
            "fetched_at":res.get("fetched_at"),
            "url":res.get("url"),
        })
    return merged, provenance
