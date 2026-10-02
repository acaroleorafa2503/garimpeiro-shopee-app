
from db import init_db, upsert_product

def seed():
    init_db()
    rows=[
        ("Arranhador adesivo para gatos","arranhador adesivo gato","Pet","C","Perene",""),
        ("Tapete higiênico para cães","tapete higiênico cachorro","Pet","A","Perene",""),
        ("Organizador ajustável de panelas","organizador panelas tampas","Casa","A","Sazonal leve","1,11")
    ]
    for r in rows:
        upsert_product(*r)
    print("Produtos iniciais carregados.")

if __name__=="__main__":
    seed()
