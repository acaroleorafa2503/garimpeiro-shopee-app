
from datetime import datetime,timedelta
from db import scheduled_jobs,upsert_scheduled_job,mark_job_run
from run_daily import run as run_daily
from automation_center import run_alert_center
from orchestrator import run_orchestrator
from executive_summary import build_executive_summary
from daily_executive import generate_daily

def seed_jobs():
    upsert_scheduled_job("Análise diária","analysis","daily",8,notes="Score e histórico")
    upsert_scheduled_job("Alertas diários","alerts","daily",9,notes="Varredura de gatilhos")
    upsert_scheduled_job("Orquestrador diário","orchestrator","daily",10)
    upsert_scheduled_job("Resumo executivo","summary","daily",18)

def due(job,now):
    if not job["enabled"]: return False
    if job["cadence"]=="daily":
        return now.hour >= (job["hour"] or 0) and (not job["last_run"] or job["last_run"][:10]!=now.date().isoformat())
    if job["cadence"]=="weekly":
        return now.weekday()==(job["weekday"] or 0) and now.hour >= (job["hour"] or 0) and (not job["last_run"] or job["last_run"][:10]!=now.date().isoformat())
    return False

def execute_job(job):
    jt=job["job_type"]
    if jt=="analysis": result=run_daily()
    elif jt=="alerts": result=run_alert_center()
    elif jt=="orchestrator": result=run_orchestrator()
    elif jt=="summary": result=str(generate_daily())
    else: result="Job desconhecido"
    mark_job_run(job["id"])
    return result

def run_due():
    seed_jobs()
    now=datetime.now()
    results=[]
    for job in scheduled_jobs():
        if due(job,now):
            results.append((job["name"],execute_job(job)))
    return results

if __name__=="__main__":
    print(run_due())
