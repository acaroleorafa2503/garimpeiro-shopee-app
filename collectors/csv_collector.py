
import csv
from pathlib import Path
from .base import Collector

class CSVCollector(Collector):
    """
    Safe/manual collector:
    reads latest public/operational signals from data/coleta_atual.csv.
    Expected columns:
    name,price_avg,demand_signal,competitor_count,review_signal,supplier_cost,
    shipping_in,packaging,marketplace_pct,tax_pct,discount_pct,ads_pct,losses_pct
    """
    def __init__(self, path):
        self.path=Path(path)

    def collect(self, product):
        if not self.path.exists():
            return {}
        with self.path.open("r",encoding="utf-8-sig",newline="") as f:
            for row in csv.DictReader(f):
                if row.get("name","").strip().lower()==product["name"].strip().lower():
                    out={}
                    for k,v in row.items():
                        if k=="name": continue
                        if v is None or v=="": out[k]=None
                        else:
                            try: out[k]=float(v)
                            except: out[k]=v
                    return out
        return {}
