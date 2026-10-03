import re

GENERIC_HEADS = {
    "coleira pet","coleira pets","acessórios pet","acessorios pet","produto pet",
    "organizador casa","organizador cozinha","kit ferramentas","jogo ferramentas",
    "suporte cozinha","utilidade doméstica","utilidade domestica"
}

ATTRIBUTE_GROUPS = {
    "tipo": [
        "retrátil","retratil","personalizada","personalizado","adesiva","adesivo",
        "ajustável","ajustavel","automática","automatica","elétrica","eletrica",
        "magnética","magnetica","dobrável","dobravel","portátil","portatil"
    ],
    "recurso": [
        "lanterna","nome","telefone","gps","led","pérolas","perolas","miçangas","micangas",
        "refletiva","refletivo","antipulgas","anti pulgas","antiparasitária","antiparasitaria",
        "dupla","duplo","3 em 1","2 em 1"
    ],
    "material": [
        "nylon","couro","silicone","metal","aço","aco","plástico","plastico","tecido","corda"
    ],
    "publico": [
        "cachorro","cães","caes","gato","gatos","filhote","grande porte","pequeno porte"
    ],
    "quantidade": [
        "kit","jogo","par","unidade","peças","pecas"
    ]
}

PRODUCT_NOUNS = [
    "coleira","guia","peitoral","tapete","arranhador","comedouro","bebedouro","brinquedo",
    "organizador","escorredor","suporte","kit","jogo","broca","alicate","chave","cabo",
    "adaptador","garrafa","pote","caixa","bolsa","escova","refil"
]

STOPWORDS = {
    "de","da","do","das","dos","para","com","em","na","no","nas","nos","e","a","o",
    "the","brasil","oferta","promoção","promocao","frete","grátis","gratis","novo","premium"
}

def _norm(s):
    s=(s or "").lower()
    s=re.sub(r"[^a-z0-9áàâãéêíóôõúç\s]", " ", s)
    return re.sub(r"\s+"," ",s).strip()

def extract_identity(name, description=""):
    text=_norm(f"{name} {description}")
    title=_norm(name)

    nouns=[n for n in PRODUCT_NOUNS if n in text]
    noun=nouns[0] if nouns else ""

    attrs=[]
    for group,vals in ATTRIBUTE_GROUPS.items():
        for v in vals:
            if v in text and v not in attrs:
                attrs.append(v)

    # keep commercial qualifiers that matter
    tokens=[t for t in title.split() if t not in STOPWORDS and len(t)>2]
    core=[]
    if noun:
        core.append(noun)
    for a in attrs:
        if a not in core:
            core.append(a)

    # If identity is too generic, add a few meaningful title tokens
    if len(core) < 2:
        for t in tokens:
            if t not in core and t not in ("pet","pets","casa","cozinha","produto"):
                core.append(t)
            if len(core) >= 4:
                break

    canonical=" ".join(core[:6]).strip()
    generic = canonical in GENERIC_HEADS or len(core) < 2

    return {
        "canonical": canonical or title[:80],
        "noun": noun,
        "attributes": attrs,
        "generic": generic,
        "tokens": list(dict.fromkeys(core))
    }

def compatibility_score(reference_name, candidate_name, candidate_desc=""):
    ref=extract_identity(reference_name)
    cand=extract_identity(candidate_name,candidate_desc)

    if not ref["noun"] or not cand["noun"] or ref["noun"] != cand["noun"]:
        return 0

    score=50
    ref_attrs=set(ref["attributes"])
    cand_attrs=set(cand["attributes"])

    # Matching specific attributes strongly increases compatibility.
    shared=ref_attrs & cand_attrs
    score += min(35, len(shared)*12)

    # Missing a reference-defining attribute is a penalty.
    missing=ref_attrs - cand_attrs
    score -= min(30, len(missing)*10)

    # Conflicting strong attributes should reduce match.
    specific_words=set(sum(ATTRIBUTE_GROUPS.values(),[]))
    conflicting=(cand_attrs - ref_attrs) & specific_words
    if ref_attrs and conflicting:
        score -= min(20, len(conflicting)*7)

    return max(0,min(100,score))

def is_compatible(reference_name, candidate_name, candidate_desc="", min_score=60):
    return compatibility_score(reference_name,candidate_name,candidate_desc) >= min_score
