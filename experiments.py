
from db import create_experiment,experiments

def suggest_experiments(product_id,product_name):
    ideas=[
        ("Capa principal","Imagem de uso real aumenta CTR","Foto produto","Foto problema→solução","CTR"),
        ("Oferta em kit","Kit aumenta ticket e margem","1 unidade","Kit 2/4 unidades","Lucro por visita"),
        ("Preço","Preço psicológico melhora conversão","Preço atual","Preço -5%","Conversão"),
    ]
    for name,h,a,b,m in ideas:
        create_experiment(product_id,f"{product_name} — {name}",h,a,b,m)
    return experiments()
