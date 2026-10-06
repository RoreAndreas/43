"""Le bêta des comparables est désendetté société par société.

    gearing          = dette totale / fonds propres
    bêta désendetté  = bêta coté / (1 + (1 − t) × gearing)

`t` est le taux d'IS légal du pays de la société, publié par Damodaran. Le taux
effectif que publie S&P est embarqué à côté, pour un usage ultérieur, sans
entrer dans le calcul. La page ré-endette ensuite la médiane du secteur au
gearing retenu et au taux d'IS du pays valorisé.

Ces tests relisent le jeu de données embarqué : la règle doit tenir pour chaque
société, pas seulement pour la médiane qu'on affiche.
"""

import pytest

from conftest import choisir, mode_comparables

EXPORTS = ["43 AF.xlsx", "43 EU.xlsx", "43 ME.xlsx", "43 US.xlsx"]


def societes(donnees):
    return donnees["comparables"]["societes"].values()


def test_l_univers_vient_des_quatre_exports(donnees):
    assert donnees["comparables"]["source"].split(", ") == EXPORTS


def test_le_moyen_orient_est_peuple(donnees):
    zones = {s["zone"] for s in societes(donnees)}
    assert "Moyen-Orient" in zones


def test_le_gearing_rapporte_la_dette_aux_fonds_propres(donnees):
    """Fonds propres et dette sont embarqués au dixième de million : sur des
    fonds propres quasi nuls, cet arrondi suffit à fausser le rapport. On le
    vérifie là où il est négligeable — au-delà de cent millions."""
    for s in societes(donnees):
        assert s["fonds_propres"] > 0, s["nom"]
        if s["fonds_propres"] >= 100:
            assert s["gearing"] == pytest.approx(s["dette"] / s["fonds_propres"],
                                                 rel=1e-3, abs=1e-3), s["nom"]


def test_chaque_beta_est_desendette_a_son_propre_levier(donnees):
    for s in societes(donnees):
        beta = s["beta_3ans"] if s["beta_horizon"] == "3 ans" else s["beta_1an"]
        attendu = beta / (1 + (1 - s["is_desendettement"]) * s["gearing"])
        assert s["beta_u"] == pytest.approx(attendu, abs=1e-5), s["nom"]


def test_le_taux_de_desendettement_est_le_taux_legal_du_pays(donnees):
    """Les comparables américains — plus de la moitié de l'univers — prennent le
    taux Damodaran des États-Unis, qu'un libellé onusien privait de taux."""
    us = donnees["pays"]["United States"]["tax"]
    americaines = [s for s in societes(donnees) if s["pays"] in ("USA", "United States")]
    assert americaines
    assert {s["is_desendettement"] for s in americaines} == {us}


def test_le_taux_effectif_est_conserve_mais_pas_utilise(donnees):
    ecarts = [s for s in societes(donnees)
              if s["is_effectif"] is not None
              and abs(s["is_effectif"] - s["is_desendettement"]) > 0.05]
    assert ecarts, "aucune société où les deux taux diffèrent : le test perd son objet"
    # Le bêta désendetté suit le taux légal, pas le taux effectif.
    for s in ecarts[:50]:
        beta = s["beta_3ans"] if s["beta_horizon"] == "3 ans" else s["beta_1an"]
        avec_effectif = beta / (1 + (1 - s["is_effectif"]) * s["gearing"])
        if s["gearing"] > 0.05:
            assert s["beta_u"] != pytest.approx(avec_effectif, abs=1e-4), s["nom"]


def test_la_page_reendette_la_mediane(page):
    mode_comparables(page)
    choisir(page, "secteur", "Banks")
    cc = page.evaluate("cmpcComparables()")
    assert cc["beta"] == pytest.approx(cc["betaU"] * (1 + (1 - cc["tax"]) * cc["gearing"]))
    assert cc["betaU"] == page.evaluate("statsSecteur('Banks').beta_u")
