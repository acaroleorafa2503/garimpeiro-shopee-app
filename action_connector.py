
import os, json, csv, smtplib, urllib.request, urllib.parse
from pathlib import Path
from email.message import EmailMessage
from db import action_drafts, create_outbound_action, outbound_actions, mark_outbound_sent

BASE=Path(__file__).resolve().parent
EXPORTS=BASE/"exports"
EXPORTS.mkdir(exist_ok=True)

def queue_approved(channel="txt", destination=""):
    created=0
    existing={(r["draft_id"],r["channel"]) for r in outbound_actions(limit=5000)}
    for d in action_drafts(status="aprovado",limit=5000):
        key=(d["id"],channel)
        if key in existing: continue
        create_outbound_action(d["id"],channel,destination)
        created+=1
    return {"queued":created}

def _send_email(item):
    host=os.getenv("SMTP_HOST"); port=int(os.getenv("SMTP_PORT","587"))
    user=os.getenv("SMTP_USER"); password=os.getenv("SMTP_PASSWORD")
    to=item.get("destination") or os.getenv("ACTION_EMAIL_TO")
    if not all([host,user,password,to]):
        return False,"SMTP incompleto."
    msg=EmailMessage()
    msg["Subject"]=item["title"]; msg["From"]=user; msg["To"]=to
    msg.set_content(item["content"])
    with smtplib.SMTP(host,port,timeout=20) as s:
        s.starttls(); s.login(user,password); s.send_message(msg)
    return True,"E-mail enviado."

def _send_telegram(item):
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id=item.get("destination") or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return False,"Telegram incompleto."
    url=f"https://api.telegram.org/bot{token}/sendMessage"
    data=urllib.parse.urlencode({"chat_id":chat_id,"text":item["title"]+"\n\n"+item["content"][:3500]}).encode()
    urllib.request.urlopen(url,data=data,timeout=20).read()
    return True,"Telegram enviado."

def _send_webhook(item):
    url=item.get("destination") or os.getenv("ACTION_WEBHOOK_URL")
    if not url: return False,"Webhook ausente."
    payload=json.dumps({"title":item["title"],"content":item["content"],"action_type":item["action_type"]}).encode()
    req=urllib.request.Request(url,data=payload,headers={"Content-Type":"application/json"})
    urllib.request.urlopen(req,timeout=20).read()
    return True,"Webhook enviado."

def _export_file(item, ext="txt"):
    safe="".join(c for c in item["title"] if c.isalnum() or c in " _-").strip().replace(" ","_")
    p=EXPORTS/f"out_{item['id']}_{safe}.{ext}"
    if ext=="txt":
        p.write_text(item["content"],encoding="utf-8")
    else:
        with p.open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f); w.writerow(["title","content"]); w.writerow([item["title"],item["content"]])
    return True,str(p)

def send_action(action_id, confirm=False):
    if not confirm:
        return {"sent":False,"message":"Confirmação explícita necessária."}
    item=next((x for x in outbound_actions(limit=5000) if x["id"]==action_id),None)
    if not item: return {"sent":False,"message":"Ação não encontrada."}
    ch=item["channel"]
    if ch=="email": ok,msg=_send_email(item)
    elif ch=="telegram": ok,msg=_send_telegram(item)
    elif ch=="webhook": ok,msg=_send_webhook(item)
    elif ch=="csv": ok,msg=_export_file(item,"csv")
    else: ok,msg=_export_file(item,"txt")
    if ok: mark_outbound_sent(action_id,msg)
    return {"sent":ok,"message":msg}
