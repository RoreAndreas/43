"""Wireless et Diversified Telecommunication Services ne font plus qu'un.

S&P distingue deux Industry GICS pour un même Industry Group, et la frontière
n'est pas fiable sur les télécoms africains : Orange CI et Sonatel, deux
opérateurs du même groupe au même modèle d'affaires, se retrouvaient de part et
d'autre — tout comme MTN Group et MTN Uganda. La fusion se fait à la lecture de
l'export (`comparables.py`), donc pour toutes les sociétés, pas seulement ces
deux-là.
"""

from conftest import choisir, ligne_resultat, mode_comparables, nombre_fr, secteur

FUSIONNE = "Telecommunication Services"
DISPARUS = ("Wireless Telecommunication Services", "Diversified Telecommunication Services")


def test_les_deux_anciens_intitules_ont_disparu(donnees):
    secteurs = (donnees.get("comparables") or {}).get("secteurs") or {}
    for nom in DISPARUS:
        assert nom not in secteurs, f"« {nom} » ne devrait plus exister comme secteur"


def test_le_secteur_fusionne_existe(donnees):
    secteurs = (donnees.get("comparables") or {}).get("secteurs") or {}
    assert FUSIONNE in secteurs


def test_orange_ci_et_sonatel_partagent_le_meme_secteur(donnees):
    societes = (donnees.get("comparables") or {}).get("societes") or {}
    noms = {s["nom"]: s for s in societes.values()}
    assert "Orange CI" in noms and "Sonatel SA" in noms
    assert noms["Orange CI"]["industrie"] == FUSIONNE
    assert noms["Sonatel SA"]["industrie"] == FUSIONNE


def test_le_menu_secteur_ne_propose_plus_les_deux_anciens(page):
    mode_comparables(page)
    options = page.eval_on_selector_all(
        '#paramsMain select[data-param="secteur"] option', "e => e.map(o => o.value)")
    for nom in DISPARUS:
        assert nom not in options
    assert FUSIONNE in options


def test_orange_ci_et_sonatel_comptent_dans_la_meme_mediane(page, donnees):
    """La médiane du secteur fusionné doit refléter l'échantillon combiné, pas
    un seul des deux anciens sous-secteurs."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", FUSIONNE)

    attendu = secteur(donnees, FUSIONNE, perimetre="Afrique")
    assert nombre_fr(ligne_resultat(page, "Bêta médian (3 ans)")) == round(attendu["beta_3ans"], 3)
    assert nombre_fr(ligne_resultat(page, "Sociétés du secteur")) == attendu["societes"]
