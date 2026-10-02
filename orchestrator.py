
import json, uuid
from pathlib import Path
from datetime import datetime, timedelta
from db import (
    automation_events, portfolio_actions, orchestrator_tasks,
    create_orchestrator_task, update_task_status, save_orchestrator_run,
    save_decision
)

BASE=Path(__file__).resolve().parent
CONFIG=json.loads((BASE/"config.json").read_text(encoding="utf-8"))
CFG=CONFIG["orchestrator"]

ALERT_TO_TASK = {
    "ESTOQUE_BAIXO": ("RECOMPRAR_ESTOQUE","alta"),
    "ROAS_BAIXO": ("REVISAR_ADS","alta"),
    "MARGEM_DERRETENDO": ("REVISAR_MARGEM","alta"),
    "FORNECEDOR_MELHOR": ("TROCAR_FORNECEDOR","media"),
    "JANELA_SAZONAL": ("PREPARAR_SAZONALIDADE","alta"),
    "SCORE_FORTE": ("AVALIAR_ESCALA","media")
}

def requires_approval(task_type):
    return task_type in CFG["require_approval_for"]

def task_uid(source_type, source_id, task_type):
    return f"{source_type}:{source_id}:{task_type}"

def expires_at():
    return (datetime.now()+timedelta(days=CFG["default_task_ttl_days"])).isoformat(timespec="seconds")

def create_tasks_from_alerts():
    existing={t["task_uid"] for t in orchestrator_tasks(limit=5000)}
    created=0
    for e in automation_events(limit=1000):
        mapping=ALERT_TO_TASK.get(e["event_type"])
        if not mapping:
            continue
        task_type,priority=mapping
        uid=task_uid("alert",e["id"],task_type)
        if uid in existing:
            continue
        create_orchestrator_task(
            uid,e.get("product_id"),"alert",e["id"],task_type,
            e["title"],e["message"],priority,
            1 if requires_approval(task_type) else 0,expires_at()
        )
        existing.add(uid); created+=1
    return created

def create_tasks_from_portfolio():
    existing={t["task_uid"] for t in orchestrator_tasks(limit=5000)}
    created=0
    latest={}
    for a in portfolio_actions(limit=1000):
        if a["product_id"] not in latest:
            latest[a["product_id"]]=a
    for pid,a in latest.items():
        task_type=a["action"]
        uid=task_uid("portfolio",a["id"],task_type)
        if uid in existing:
            continue
        priority="alta" if a["priority"]=="alta" else "media"
        create_orchestrator_task(
            uid,pid,"portfolio",a["id"],task_type,
            f"{task_type} — {a['name']}",a["reason"],priority,
            1 if requires_approval(task_type) else 0,expires_at()
        )
        existing.add(uid); created+=1
    return created

def run_orchestrator():
    created=0
    if CFG["auto_create_tasks_from_alerts"]:
        created+=create_tasks_from_alerts()
    created+=create_tasks_from_portfolio()
    save_orchestrator_run("generate_tasks",created,0,"Geração de tarefas a partir de alertas e portfólio.")
    return {"tasks_created":created}

def approve_task(uid, actor="usuario"):
    update_task_status(uid,"aprovada")
    task=next((t for t in orchestrator_tasks(limit=5000) if t["task_uid"]==uid),None)
    if task:
        save_decision(task.get("product_id"),task["task_type"],"APROVADA",actor,task.get("description",""),uid)

def reject_task(uid, actor="usuario", rationale=""):
    update_task_status(uid,"rejeitada",rationale)
    task=next((t for t in orchestrator_tasks(limit=5000) if t["task_uid"]==uid),None)
    if task:
        save_decision(task.get("product_id"),task["task_type"],"REJEITADA",actor,rationale or task.get("description",""),uid)

def execute_approved():
    executed=0
    for t in orchestrator_tasks(status="aprovada",limit=1000):
        # V12 intentionally executes only internal bookkeeping.
        # External irreversible actions remain human-controlled.
        result=f"Tarefa marcada como executada internamente: {t['task_type']}."
        update_task_status(t["task_uid"],"executada",result)
        save_decision(t.get("product_id"),t["task_type"],"EXECUTADA","orquestrador",result,t["task_uid"])
        executed+=1
    save_orchestrator_run("execute_approved",0,executed,"Execução interna de tarefas previamente aprovadas.")
    return {"tasks_executed":executed}

if __name__=="__main__":
    print(run_orchestrator())
