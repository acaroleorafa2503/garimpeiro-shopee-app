
import csv
from pathlib import Path
from db import init_db, products, add_performance

BASE=Path(__file__).resolve().parent

def import_performance(path=None):
    init_db()
    path=Path(path or BASE/"data"/"desempenho_real.csv")
    if not path.exists():
        return {"imported":0,"message":"Arquivo não encontrado."}

    pmap={p["name"].strip().lower():p for p in products()}
    imported=0
    errors=[]
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        for i,row in enumerate(csv.DictReader(f),start=2):
            name=(row.get("name") or "").strip().lower()
            if name not in pmap:
                errors.append(f"Linha {i}: produto não cadastrado: {row.get('name')}")
                continue
            p=pmap[name]
            try:
                add_performance(
                    p["id"], row.get("date"),
                    row.get("impressions",0),row.get("clicks",0),row.get("orders",0),
                    row.get("revenue",0),row.get("ad_spend",0),row.get("returns",0),
                    row.get("cogs",0),row.get("shipping_cost",0),row.get("marketplace_fees",0),
                    row.get("taxes",0),row.get("other_costs",0)
                )
                imported+=1
            except Exception as e:
                errors.append(f"Linha {i}: {e}")
    return {"imported":imported,"errors":errors}

if __name__=="__main__":
    print(import_performance())
