
import os, json, urllib.request, urllib.parse, smtplib
from email.message import EmailMessage
from db import automation_events

def send_email(subject, body):
    host=os.getenv("SMTP_HOST")
    port=int(os.getenv("SMTP_PORT","587"))
    user=os.getenv("SMTP_USER")
    password=os.getenv("SMTP_PASSWORD")
    to=os.getenv("ALERT_EMAIL_TO")
    if not all([host,user,password,to]):
        return False,"SMTP não configurado."
    msg=EmailMessage()
    msg["Subject"]=subject
    msg["From"]=user
    msg["To"]=to
    msg.set_content(body)
    with smtplib.SMTP(host,port,timeout=20) as s:
        s.starttls()
        s.login(user,password)
        s.send_message(msg)
    return True,"E-mail enviado."

def send_telegram(text):
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id=os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False,"Telegram não configurado."
    url=f"https://api.telegram.org/bot{token}/sendMessage"
    data=urllib.parse.urlencode({"chat_id":chat_id,"text":text}).encode()
    with urllib.request.urlopen(url,data=data,timeout=20) as r:
        _=r.read()
    return True,"Telegram enviado."

def send_webhook(payload):
    url=os.getenv("ALERT_WEBHOOK_URL")
    if not url:
        return False,"Webhook não configurado."
    data=json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        _=r.read()
    return True,"Webhook enviado."

def deliver_latest(limit=20):
    events=automation_events(limit=limit)
    results=[]
    for e in events:
        text=f"[{e['severity'].upper()}] {e['title']}\n{e['message']}"
        row={"event_id":e["id"]}
        try: row["email"]=send_email(e["title"],text)
        except Exception as ex: row["email"]=(False,str(ex))
        try: row["telegram"]=send_telegram(text)
        except Exception as ex: row["telegram"]=(False,str(ex))
        try: row["webhook"]=send_webhook(e)
        except Exception as ex: row["webhook"]=(False,str(ex))
        results.append(row)
    return results

if __name__=="__main__":
    print(deliver_latest())
