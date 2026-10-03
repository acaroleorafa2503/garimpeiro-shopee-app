from math import ceil

def _f(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def evaluate_product(
    sale_price,
    product_cost,
    inbound_freight=0,
    packaging=0,
    marketplace_fee_pct=0,
    fixed_fee=0,
    tax_pct=0,
    ad_pct=0,
    return_loss_pct=0,
    target_margin_pct=15,
    supplier_confirmed=False,
    shopee_evidence=False,
    investigation_score=0,
    radar_score=0,
    moq=0,
    test_budget=500,
):
    sale=_f(sale_price)
    cost=_f(product_cost)
    inbound=_f(inbound_freight)
    pack=_f(packaging)
    fee_pct=_f(marketplace_fee_pct)
    fixed=_f(fixed_fee)
    tax=_f(tax_pct)
    ads=_f(ad_pct)
    loss=_f(return_loss_pct)
    target=_f(target_margin_pct)
    budget=_f(test_budget)
    moq_i=max(0,int(_f(moq)))

    missing=[]
    if sale <= 0: missing.append("preço de venda")
    if cost <= 0: missing.append("custo do produto")

    if missing:
        return {
            "ready":False,
            "missing":missing,
            "decision":"🟡 DADOS INSUFICIENTES",
            "reason":"Preencha os dados essenciais antes da decisão financeira."
        }

    marketplace_fee = sale * fee_pct/100
    taxes = sale * tax/100
    ad_cost = sale * ads/100
    return_loss = sale * loss/100

    total_variable = cost + inbound + pack + marketplace_fee + fixed + taxes + ad_cost + return_loss
    profit = sale - total_variable
    margin_pct = (profit/sale*100) if sale else 0
    contribution_before_ads = sale - (cost+inbound+pack+marketplace_fee+fixed+taxes+return_loss)
    cac_break_even = max(0, contribution_before_ads)
    target_profit = sale * target/100
    cac_target = max(0, contribution_before_ads - target_profit)
    roas_break_even = sale/cac_break_even if cac_break_even > 0 else None
    roas_target = sale/cac_target if cac_target > 0 else None

    # Test sizing: cap by budget and keep the test intentionally small.
    unit_landed = max(0.01, cost+inbound+pack)
    by_budget = max(1, int(budget // unit_landed))
    test_units = min(30, max(5, by_budget))
    if moq_i > 0:
        test_units = max(test_units, moq_i)
    capital = round(test_units * unit_landed,2)
    expected_test_profit = round(test_units * profit,2)

    risk_points=0
    reasons=[]
    if not shopee_evidence:
        risk_points += 3; reasons.append("sem evidência Shopee")
    if not supplier_confirmed:
        risk_points += 3; reasons.append("fornecedor ainda não confirmado")
    if margin_pct < 10:
        risk_points += 4; reasons.append("margem muito baixa")
    elif margin_pct < target:
        risk_points += 2; reasons.append("margem abaixo da meta")
    if _f(investigation_score) < 50:
        risk_points += 2; reasons.append("investigação fraca")
    if _f(radar_score) < 70:
        risk_points += 1; reasons.append("score radar moderado")

    if profit <= 0:
        decision="🔴 DESCARTAR / RENEGOCIAR CUSTO"
    elif not supplier_confirmed:
        decision="🟡 COTAR FORNECEDOR"
    elif margin_pct < target:
        decision="🟠 INVESTIGAR / RENEGOCIAR"
    elif shopee_evidence and _f(investigation_score) >= 60:
        decision="🟢 TESTE PEQUENO"
    else:
        decision="🟡 INVESTIGAR"

    return {
        "ready":True,
        "decision":decision,
        "sale_price":round(sale,2),
        "product_cost":round(cost,2),
        "total_variable_cost":round(total_variable,2),
        "profit_per_unit":round(profit,2),
        "margin_pct":round(margin_pct,2),
        "cac_break_even":round(cac_break_even,2),
        "cac_target":round(cac_target,2),
        "roas_break_even":round(roas_break_even,2) if roas_break_even else None,
        "roas_target":round(roas_target,2) if roas_target else None,
        "test_units":test_units,
        "test_capital":capital,
        "expected_test_profit":expected_test_profit,
        "risk_points":risk_points,
        "reasons":reasons,
        "assumptions":{
            "marketplace_fee_pct":fee_pct,
            "tax_pct":tax,
            "ad_pct":ads,
            "return_loss_pct":loss,
            "target_margin_pct":target,
        }
    }
