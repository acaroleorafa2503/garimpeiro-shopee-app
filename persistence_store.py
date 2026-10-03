import os, json, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone

TABLE = "garimpeiro_snapshots"

def configured():
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))

def _base():
    return os.getenv("SUPABASE_URL","").rstrip("/")

def _key():
    return os.getenv("SUPABASE_KEY","")

def _headers(extra=None):
    h = {
        "apikey": _key(),
        "Authorization": f"Bearer {_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h

def product_key(product):
    pid = str(product.get("pid") or "").strip()
    shop_id = str(product.get("shop_id") or "").strip()
    url = str(product.get("url") or "").strip()
    title = " ".join(str(product.get("produto") or "").lower().split())
    raw = f"{pid}|{shop_id}|{url}|{title[:220]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _request(method, path, payload=None, headers=None, timeout=30):
    url = f"{_base()}/rest/v1/{path.lstrip('/')}"
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_headers(headers),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = getattr(resp, "status", 200)
        return {"ok": True, "status": status, "data": json.loads(raw) if raw.strip() else None}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        return {"ok": False, "status": exc.code, "error": body[:1500]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def healthcheck():
    if not configured():
        return {"ok": False, "error": "SUPABASE_URL/SUPABASE_KEY não configurados."}
    return _request("GET", f"{TABLE}?select=id&limit=1")

def save_products(products, source="auto_discovery", category="", keyword=""):
    if not configured():
        return {"ok": False, "saved": 0, "error": "Supabase não configurado."}
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for p in products or []:
        if not isinstance(p, dict):
            continue
        rows.append({
            "product_key": product_key(p),
            "collected_at": now,
            "source": source,
            "category": str(category or p.get("categorias_descoberta") or p.get("categoria") or ""),
            "keyword": str(keyword or p.get("termos_descoberta") or ""),
            "payload": p,
        })
    if not rows:
        return {"ok": True, "saved": 0}
    result = _request(
        "POST",
        TABLE,
        payload=rows,
        headers={"Prefer": "return=minimal"},
        timeout=45,
    )
    result["saved"] = len(rows) if result.get("ok") else 0
    return result

def load_latest_products(limit=2000):
    if not configured():
        return {"ok": False, "products": [], "error": "Supabase não configurado."}

    path = (
        f"{TABLE}?select=product_key,collected_at,payload"
        f"&order=collected_at.desc&limit={int(limit)}"
    )
    result = _request("GET", path, timeout=45)
    if not result.get("ok"):
        return {"ok": False, "products": [], "error": result.get("error","erro")}

    latest = {}
    for row in result.get("data") or []:
        k = row.get("product_key")
        if not k or k in latest:
            continue
        payload = row.get("payload")
        if isinstance(payload, dict):
            latest[k] = payload
    return {
        "ok": True,
        "products": list(latest.values()),
        "rows_scanned": len(result.get("data") or []),
        "unique_products": len(latest),
    }

def snapshot_count(limit=5000):
    if not configured():
        return {"ok": False, "count": 0, "error": "Supabase não configurado."}
    result = _request(
        "GET",
        f"{TABLE}?select=id&limit={int(limit)}",
        headers={"Prefer": "count=exact"},
    )
    # PostgREST exact count is in Content-Range header, not body; keep simple fallback.
    if not result.get("ok"):
        return {"ok": False, "count": 0, "error": result.get("error","erro")}
    return {"ok": True, "count": len(result.get("data") or [])}
