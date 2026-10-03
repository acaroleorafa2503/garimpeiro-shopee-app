def landed_cost_brazil(
    wholesale_cny,
    qty,
    fx_cny_brl,
    intl_freight_brl=0.0,
    import_taxes_brl=0.0,
    customs_brl=0.0,
    domestic_freight_brl=0.0,
    packaging_brl_per_unit=0.0,
    other_fixed_brl=0.0,
    other_unit_brl=0.0,
):
    qty = int(qty or 0)
    if qty <= 0:
        return {"ok": False, "error": "Quantidade inválida."}

    wholesale_cny = float(wholesale_cny or 0)
    fx_cny_brl = float(fx_cny_brl or 0)
    product_total_brl = wholesale_cny * qty * fx_cny_brl

    fixed = (
        float(intl_freight_brl or 0)
        + float(import_taxes_brl or 0)
        + float(customs_brl or 0)
        + float(domestic_freight_brl or 0)
        + float(other_fixed_brl or 0)
    )
    unit_extras = float(packaging_brl_per_unit or 0) + float(other_unit_brl or 0)
    total_brl = product_total_brl + fixed + (unit_extras * qty)
    unit_brl = total_brl / qty

    return {
        "ok": True,
        "qty": qty,
        "product_total_brl": product_total_brl,
        "fixed_total_brl": fixed,
        "unit_extras_brl": unit_extras,
        "landed_total_brl": total_brl,
        "landed_unit_brl": unit_brl,
    }

def profitability(
    sale_price_brl,
    landed_unit_brl,
    marketplace_fee_pct=0.0,
    fixed_fee_brl=0.0,
    tax_pct=0.0,
    ads_pct=0.0,
    returns_pct=0.0,
    target_margin_pct=20.0,
):
    sale = float(sale_price_brl or 0)
    cost = float(landed_unit_brl or 0)
    if sale <= 0 or cost < 0:
        return {"ok": False, "error": "Preço de venda/custo inválido."}

    fee = sale * float(marketplace_fee_pct or 0) / 100
    tax = sale * float(tax_pct or 0) / 100
    ads = sale * float(ads_pct or 0) / 100
    returns = sale * float(returns_pct or 0) / 100
    fixed_fee = float(fixed_fee_brl or 0)

    total_var = cost + fee + fixed_fee + tax + ads + returns
    profit = sale - total_var
    margin = (profit / sale * 100) if sale else 0

    # CAC break-even excludes the current ads assumption so we can show the ad ceiling.
    non_ads_cost = cost + fee + fixed_fee + tax + returns
    cac_break_even = max(0.0, sale - non_ads_cost)
    target_profit = sale * float(target_margin_pct or 0) / 100
    cac_target = max(0.0, sale - non_ads_cost - target_profit)

    roas_break_even = (sale / cac_break_even) if cac_break_even > 0 else None
    roas_target = (sale / cac_target) if cac_target > 0 else None

    if margin < 0:
        decision = "🔴 NEGATIVO — NÃO AVANÇAR"
    elif margin < 10:
        decision = "🟠 MARGEM MUITO APERTADA"
    elif margin < float(target_margin_pct or 0):
        decision = "🟡 ABAIXO DA MARGEM-ALVO"
    else:
        decision = "🟢 VIÁVEL PARA TESTE PEQUENO"

    return {
        "ok": True,
        "fee_brl": fee,
        "tax_brl": tax,
        "ads_brl": ads,
        "returns_brl": returns,
        "total_variable_brl": total_var,
        "profit_brl": profit,
        "margin_pct": margin,
        "cac_break_even_brl": cac_break_even,
        "cac_target_brl": cac_target,
        "roas_break_even": roas_break_even,
        "roas_target": roas_target,
        "decision": decision,
    }
