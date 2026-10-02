
from pathlib import Path
from datetime import datetime
import shutil, sqlite3, json, hashlib

BASE=Path(__file__).resolve().parent
DB=BASE/"data"/"garimpeiro.db"
BACKUPS=BASE/"backups"; BACKUPS.mkdir(exist_ok=True)

def checksum(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(65536),b""): h.update(chunk)
    return h.hexdigest()

def backup():
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    target=BACKUPS/f"garimpeiro_{stamp}.db"
    shutil.copy2(DB,target)
    meta={"created_at":datetime.now().isoformat(),"file":target.name,"sha256":checksum(target)}
    (BACKUPS/f"garimpeiro_{stamp}.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    return target

def integrity_check():
    con=sqlite3.connect(DB)
    result=con.execute("PRAGMA integrity_check").fetchone()[0]
    con.close()
    return result

def list_backups():
    return [p.name for p in sorted(BACKUPS.glob("*.db"),reverse=True)]

if __name__=="__main__":
    print("Integrity:",integrity_check())
    print("Backup:",backup())
