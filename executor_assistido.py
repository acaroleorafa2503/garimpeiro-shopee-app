
import json
from pathlib import Path
from db import (
    orchestrator_tasks, latest_snapshots, inventory, suppliers,
    portfolio_actions, create_action_draft, action_drafts,
    update_action_draft_status, save_decision
)

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))

def latest_snapshot_map():
    return {r["product_id"]:r for r in latest_snapshots()}

def inventory_map():
    return {r["product_id"]:r for r in inventory()}

def supplier_map():
    out={}
    for r in suppliers():
        out.setdefault(r["product_id"],[]).append(r)
    return out

def existing_task_uids():
    return {d["task_uid"] for d in action_drafts(limit=5000)}

def purchase_order_draft(task, snap, inv, sups):
    stock=float((inv or {}).get("stock_on_hand") or 0)
    inbound=float((inv or {}).get("stock_inbound") or 0)
    lead=float((inv or {}).get("reorder_lead_days") or 0)
    supplier=sorted(sups,key=lambda x: float(x.get("unit_cost") or 999999))[0] if sups else None
    unit_cost=float((supplier or {}).get("unit_cost") or snap.get("supplier_cost") or 0)
    suggested_units=max(10, int(max(0, 30-stock-inbound)))
    total=suggested_units*unit_cost
    content=f"""PEDIDO DE COMPRA — RASCUNHO

Produto: {task.get('name') or ''}
Quantidade sugerida: {suggested_units} unidades
Custo unitário estimado: R$ {unit_cost:.2f}
Valor estimado do pedido: R$ {total:.2f}
Estoque atual: {stock:.0f}
Estoque a caminho: {inbound:.0f}
Prazo de reposição informado: {lead:.0f} dias
Fornecedor sugerido: {(supplier or {}).get('supplier_name','A definir')}

Observação:
Confirmar preço, disponibilidade, prazo e frete antes de fechar o pedido.
"""
    return "pedido_compra","Pedido de compra — "+(task.get("name") or ""),content

def supplier_message_draft(task, sups):
    best=sorted(sups,key=lambda x: float(x.get("unit_cost") or 999999))[0] if sups else None
    name=(best or {}).get("supplier_name","Fornecedor")
    product=task.get("name") or ""
    content=f"""Olá, {name}.

Tenho interesse em comprar {product} para revenda e gostaria de uma cotação atualizada.

Por favor, envie:
- preço para 20, 50, 100 e 300 unidades;
- pedido mínimo;
- prazo de envio;
- valor do frete;
- disponibilidade imediata;
- condição de pagamento;
- possibilidade de melhor preço para recompra recorrente.

Se houver catálogo, ficha técnica ou fotos atualizadas, pode enviar também.

Obrigada.
"""
    return "mensagem_fornecedor","Cotação para fornecedor — "+product,content

def ads_plan_draft(task, snap):
    target_roas=snap.get("roas_target")
    cac=snap.get("cac_max_target")
    content=f"""PLANO DE AJUSTE DE ADS — RASCUNHO

Produto: {task.get('name') or ''}
Score atual: {snap.get('score')}
ROAS alvo: {target_roas}
CAC máximo alvo: R$ {float(cac or 0):.2f}

Ação sugerida:
1. Revisar gasto atual e ROAS real.
2. Evitar aumento brusco de orçamento.
3. Se ROAS estiver acima do alvo, aumentar orçamento em pequeno degrau.
4. Se ROAS estiver abaixo do alvo, reduzir exposição e revisar preço/oferta/criativo.
5. Reavaliar após novo volume de dados.

Nenhuma alteração deve ser aplicada sem aprovação final.
"""
    return "plano_ads","Plano de Ads — "+(task.get("name") or ""),content

def seasonal_checklist_draft(task):
    product=task.get("name") or ""
    content=f"""CHECKLIST SAZONAL — {product}

[ ] Confirmar mês de início da alta
[ ] Confirmar fornecedor e prazo
[ ] Definir estoque inicial
[ ] Atualizar preço
[ ] Revisar título e imagens
[ ] Preparar vídeo
[ ] Preparar kit/oferta
[ ] Definir orçamento inicial de Ads
[ ] Definir ROAS mínimo
[ ] Criar data de revisão
[ ] Definir plano de saída para evitar encalhe
"""
    return "checklist_sazonal","Checklist sazonal — "+product,content

def scale_plan_draft(task, snap):
    content=f"""PLANO DE ESCALA — RASCUNHO

Produto: {task.get('name') or ''}
Score: {snap.get('score')}
Margem estimada: {snap.get('margin_est_pct')}%
CAC alvo: R$ {float(snap.get('cac_max_target') or 0):.2f}
ROAS alvo: {snap.get('roas_target')}

Passos:
1. Confirmar estoque para pelo menos 14 dias.
2. Confirmar caixa para reposição.
3. Aumentar orçamento em degrau controlado.
4. Monitorar ROAS e CAC.
5. Interromper crescimento se margem cair abaixo do limite.
6. Reavaliar diariamente durante a fase de escala.
"""
    return "plano_escala","Plano de escala — "+(task.get("name") or ""),content

def margin_review_draft(task, snap):
    content=f"""REVISÃO DE MARGEM — RASCUNHO

Produto: {task.get('name') or ''}
Margem estimada atual: {snap.get('margin_est_pct')}%
Lucro estimado por pedido: R$ {float(snap.get('profit_est') or 0):.2f}

Revisar:
- custo do fornecedor;
- frete de entrada;
- embalagem;
- tarifa Shopee;
- descontos/cupons;
- gasto em Ads;
- devoluções;
- preço de venda;
- possibilidade de kit.
"""
    return "revisao_margem","Revisão de margem — "+(task.get("name") or ""),content

def build_for_task(task, snap, inv, sups):
    t=task["task_type"]
    if t=="RECOMPRAR_ESTOQUE":
        return purchase_order_draft(task,snap,inv,sups)
    if t=="TROCAR_FORNECEDOR":
        return supplier_message_draft(task,sups)
    if t in ("REVISAR_ADS","ALTERAR_ORCAMENTO_ADS","REDUZIR","PAUSAR"):
        return ads_plan_draft(task,snap)
    if t=="PREPARAR_SAZONALIDADE":
        return seasonal_checklist_draft(task)
    if t in ("AVALIAR_ESCALA","ESCALAR"):
        return scale_plan_draft(task,snap)
    if t=="REVISAR_MARGEM":
        return margin_review_draft(task,snap)
    return None

def generate_drafts():
    snaps=latest_snapshot_map()
    invs=inventory_map()
    sups=supplier_map()
    existing=existing_task_uids()
    created=0

    # Generate drafts only for approved or non-approval tasks.
    for task in orchestrator_tasks(limit=1000):
        if task["task_uid"] in existing:
            continue
        if task["requires_approval"] and task["status"]!="aprovada":
            continue
        if task["status"] in ("rejeitada","executada"):
            continue
        snap=snaps.get(task.get("product_id"),{})
        result=build_for_task(task,snap,invs.get(task.get("product_id")),sups.get(task.get("product_id"),[]))
        if not result:
            continue
        draft_type,title,content=result
        create_action_draft(task["task_uid"],task.get("product_id"),task["task_type"],draft_type,title,content)
        created+=1
    return {"drafts_created":created}

def approve_draft(draft_id, actor="usuario"):
    drafts=action_drafts(limit=5000)
    d=next((x for x in drafts if x["id"]==draft_id),None)
    if d:
        update_action_draft_status(draft_id,"aprovado")
        save_decision(d.get("product_id"),d["action_type"],"RASCUNHO_APROVADO",actor,d["title"],d["task_uid"])

def reject_draft(draft_id, actor="usuario"):
    drafts=action_drafts(limit=5000)
    d=next((x for x in drafts if x["id"]==draft_id),None)
    if d:
        update_action_draft_status(draft_id,"rejeitado")
        save_decision(d.get("product_id"),d["action_type"],"RASCUNHO_REJEITADO",actor,d["title"],d["task_uid"])

if __name__=="__main__":
    print(generate_drafts())
