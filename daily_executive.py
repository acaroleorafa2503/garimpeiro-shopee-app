
import json
from pathlib import Path
from datetime import datetime
from executive_summary import build_executive_summary

BASE=Path(__file__).resolve().parent
REPORTS=BASE/"reports"
REPORTS.mkdir(exist_ok=True)

def generate_daily():
    s=build_executive_summary()
    k=s["kpis"]
    stamp=datetime.now().strftime("%Y-%m-%d")
    path=REPORTS/f"resumo_executivo_{stamp}.html"

    tops="".join(
        f"<tr><td>{p.get('name','')}</td><td>{p.get('score','')}</td><td>{p.get('classification','')}</td>"
        f"<td>{p.get('action','')}</td><td>{p.get('profit_est','')}</td></tr>"
        for p in s["top_products"]
    )
    alerts="".join(
        f"<li><b>{a.get('name','')}</b>: {a.get('message','')}</li>"
        for a in s["critical_alerts"]
    ) or "<li>Nenhum alerta crítico.</li>"

    html=f"""<!doctype html><meta charset='utf-8'><title>Resumo Executivo</title>
    <style>
    body{{font-family:Arial;max-width:1200px;margin:30px auto;padding:0 20px}}
    .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
    .card{{border:1px solid #ddd;border-radius:8px;padding:14px}}
    table{{border-collapse:collapse;width:100%;margin-top:12px}}
    th,td{{border:1px solid #ddd;padding:8px}} th{{background:#f3f3f3}}
    </style>
    <h1>Garimpeiro Shopee V10 — Resumo Executivo</h1>
    <p>{datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
    <div class='kpis'>
      <div class='card'><b>Pedidos</b><br>{k['orders']}</div>
      <div class='card'><b>Faturamento</b><br>R$ {k['revenue']:.2f}</div>
      <div class='card'><b>ROAS</b><br>{k['roas']}</div>
      <div class='card'><b>Lucro</b><br>R$ {k['profit']:.2f}</div>
      <div class='card'><b>Margem</b><br>{k['margin_pct']}%</div>
      <div class='card'><b>Ads</b><br>R$ {k['ad_spend']:.2f}</div>
      <div class='card'><b>Estoque</b><br>R$ {k['stock_value']:.2f}</div>
      <div class='card'><b>Alertas críticos</b><br>{k['critical_alerts']}</div>
    </div>
    <h2>Produtos prioritários</h2>
    <table><tr><th>Produto</th><th>Score</th><th>Classe</th><th>Ação</th><th>Lucro estimado</th></tr>{tops}</table>
    <h2>Alertas críticos</h2><ul>{alerts}</ul>
    """
    path.write_text(html,encoding="utf-8")
    return path

if __name__=="__main__":
    print(generate_daily())
