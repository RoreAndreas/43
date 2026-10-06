"""Le coût de la dette prend le spread de défaut du pays, pas sa prime de risque.

    taux de la dette = US Bond (année, maturité) + spread de défaut pays

Damodaran publie les deux dans la même feuille de `ctryprem.xlsx` : la prime
de risque pays est le spread de défaut tiré de la notation souveraine,
multiplié par la volatilité relative des actions. C'est une grandeur de fonds
propres. Un prêteur exige le spread tel quel : la reporter sur la dette
compterait deux fois l'aversion propre aux actionnaires.

Les fonds propres, eux, gardent la prime pays : ce fichier vérifie aussi que
rien n'a bougé de ce côté-là.
"""

import pytest

from conftest import choisir, mode_comparables, ouvrir, recevoir_classeur

openpyxl = pytest.importorskip("openpyxl")

BENIN = "Benin"
ETATS_UNIS = "United States"     # Damodaran y pose prime = spread


def test_chaque_pays_publie_son_spread_de_defaut(donnees):
    sans = [nom for nom, pays in donnees["pays"].items() if pays.get("ds") is None]
    assert sans == [], f"{len(sans)} pays sans spread de défaut, ex. {sans[:5]}"


def test_le_spread_est_plus_faible_que_la_prime(donnees):
    """La prime pays multiplie le spread par une volatilité relative ≥ 1."""
    for nom, pays in donnees["pays"].items():
        assert pays["ds"] <= pays["crp"] + 1e-12, nom


def test_le_taux_de_la_dette_est_le_us_bond_plus_le_spread(page, donnees):
    mode_comparables(page, BENIN)
    rf = page.evaluate("tauxSansRisque()")
    assert rf["spreadPays"] == pytest.approx(donnees["pays"][BENIN]["ds"])
    assert rf["tauxDette"] == pytest.approx(rf["socle"] + rf["spreadPays"])
    # Le taux des fonds propres n'a pas changé de règle.
    assert rf["taux"] == pytest.approx(rf["socle"] + donnees["pays"][BENIN]["crp"])


def test_sous_comparables_la_dette_ne_porte_que_le_spread(page):
    mode_comparables(page, BENIN)
    choisir(page, "secteur", "Banks")
    cc = page.evaluate("cmpcComparables()")
    rf = cc["rf"]
    assert cc["kdPre"] == pytest.approx(rf["socle"] + rf["spreadPays"])
    assert cc["kd"] == pytest.approx(cc["kdPre"] * (1 - cc["tax"]))
    assert cc["ke"] > rf["taux"], "le coût des fonds propres a perdu la prime pays"


def test_sous_damodaran_la_dette_ajoute_le_spread_sectoriel(page):
    choisir(page, "referentiel", "damodaran")
    choisir(page, "country", BENIN)
    b = page.evaluate("model.brut")
    assert b["kdPre"] == pytest.approx(b["socle"] + b["spreadPays"] + b["spread"])
    assert b["kd"] == pytest.approx(b["kdPre"] * (1 - b["tax"]))
    assert b["a"] == pytest.approx(b["socle"] + b["prime"])


def test_la_carte_kd_affiche_le_spread_pays(page):
    mode_comparables(page, BENIN)
    choisir(page, "secteur", "Banks")
    ouvrir(page, "wacc")
    lignes = page.inner_text('#stack .comp[data-comp="kd"] .sub-rows')
    assert "Spread de défaut pays" in lignes
    assert "Prime de risque pays" not in lignes


def test_le_classeur_porte_le_spread_pays(page, tmp_path):
    mode_comparables(page, BENIN)
    choisir(page, "secteur", "Banks")
    chemin = tmp_path / "spread.xlsx"
    recevoir_classeur(page, chemin)
    feuille = openpyxl.load_workbook(chemin).active
    spread = page.evaluate("tauxSansRisque().spreadPays")

    assert feuille.cell(row=15, column=3).value == pytest.approx(spread)
    assert "Rating-based Default Spread" in feuille.cell(row=15, column=5).value
    # Kd_pre repart du taux US, pas du taux sans risque local qui porte la CRP.
    assert feuille.cell(row=17, column=3).value == "=C3+C15+C16"


def test_aux_etats_unis_prime_et_spread_se_confondent(page, donnees):
    """Seul pays où Damodaran ne multiplie pas : la dette et les fonds propres
    partent alors du même taux, ce qui sert de témoin."""
    pays = donnees["pays"][ETATS_UNIS]
    if pays["crp"] != pytest.approx(pays["ds"]):
        pytest.skip("Damodaran distingue désormais prime et spread aux États-Unis")
    mode_comparables(page, ETATS_UNIS)
    rf = page.evaluate("tauxSansRisque()")
    assert rf["tauxDette"] == pytest.approx(rf["taux"])
