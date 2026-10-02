
from pathlib import Path
from db import action_drafts, update_action_draft_status

BASE=Path(__file__).resolve().parent
OUT=BASE/"exports"
OUT.mkdir(exist_ok=True)

def export_approved():
    count=0
    files=[]
    for d in action_drafts(status="aprovado",limit=1000):
        safe="".join(c for c in d["title"] if c.isalnum() or c in " _-").strip().replace(" ","_")
        path=OUT/f"{d['id']}_{safe}.txt"
        path.write_text(d["content"],encoding="utf-8")
        update_action_draft_status(d["id"],"exportado")
        count+=1; files.append(str(path))
    return {"exported":count,"files":files}

if __name__=="__main__":
    print(export_approved())
