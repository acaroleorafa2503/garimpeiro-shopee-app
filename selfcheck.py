def run_selfcheck():
    checks=[]
    for name in ["auto_discovery","scale_radar","nexscope_shopee"]:
        try:
            __import__(name)
            checks.append({"name":name,"ok":True,"detail":"ok"})
        except Exception as e:
            checks.append({"name":name,"ok":False,"detail":str(e)})
    return {"ok":all(x["ok"] for x in checks),"checks":checks}
