
import csv
from pathlib import Path
from db import init_db, products, upsert_inventory

BASE=Path(__file__).resolve().parent

def import_inventory(path=None):
    init_db()
    path=Path(path or BASE/"data"/"estoque_atual.csv")
    if not path.exists():
        return {"imported":0,"errors":["Arquivo não encontrado."]}

    pmap={p["name"].strip().lower():p for p in products()}
    imported=0; errors=[]
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        for i,row in enumerate(csv.DictReader(f),start=2):
            key=(row.get("name") or "").strip().lower()
            if key not in pmap:
                errors.append(f"Linha {i}: produto não cadastrado: {row.get('name')}")
                continue
            p=pmap[key]
            try:
                upsert_inventory(
                    p["id"],
                    float(row.get("stock_on_hand") or 0),
                    float(row.get("stock_inbound") or 0),
                    float(row.get("unit_cost") or 0),
                    float(row.get("reorder_lead_days") or 0),
                    float(row.get("safety_stock_days") or 7),
                )
                imported+=1
            except Exception as e:
                errors.append(f"Linha {i}: {e}")
    return {"imported":imported,"errors":errors}

if __name__=="__main__":
    print(import_inventory())
