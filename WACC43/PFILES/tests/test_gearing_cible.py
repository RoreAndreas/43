"""Cadenas et gearing cible de l'encadré « Secteur comparable ».

Le gearing sectoriel est une donnée observée. Le cadenas existe pour que son
remplacement soit un geste délibéré, et pour que l'état affiché dise lequel des
deux — médiane observée ou cible posée à la main — alimente le CMPC.
"""

import pytest

from conftest import (choisir, ligne_resultat, mode_comparables, nombre_fr,
                      secteur)

CHAMP = "#paramsResult #champGearingCible"
VERROU = "#paramsResult #verrouGearing"


def saisir(page, texte):
    page.fill(CHAMP, texte)
    page.dispatch_event(CHAMP, "change")


def cmpc(page):
    return nombre_fr(page.inner_text("#paramsResult .result-hero-value"))


# ------------------------------------------------------------------ le verrou

def test_cadenas_ferme_par_defaut(page):
    mode_comparables(page)
    assert page.get_attribute(VERROU, "aria-pressed") == "false"
    assert page.query_selector(CHAMP) is None, "le champ ne doit pas être offert verrou fermé"


def test_le_clic_ouvre_le_cadenas_et_revele_le_champ(page):
    mode_comparables(page)
    page.click(VERROU)
    assert page.get_attribute(VERROU, "aria-pressed") == "true"
    assert page.is_visible(CHAMP)


def test_refermer_le_cadenas_efface_la_cible(page, donnees):
    """Re-cliquer est la remise à zéro : retour à la médiane du secteur."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    avant = cmpc(page)

    page.click(VERROU)
    saisir(page, "60")
    assert cmpc(page) != avant, "une cible à 60 % doit déplacer le CMPC"

    page.click(VERROU)
    assert page.get_attribute(VERROU, "aria-pressed") == "false"
    assert page.query_selector(CHAMP) is None
    assert cmpc(page) == avant


def test_la_valeur_saisie_ne_survit_pas_a_une_refermeture(page):
    mode_comparables(page)
    page.click(VERROU)
    saisir(page, "60")
    page.click(VERROU)
    page.click(VERROU)
    assert page.input_value(CHAMP) == ""


# -------------------------------------------------------------- la validation

@pytest.mark.parametrize("saisie, fragment", [
    ("-10", "négatif"),
    ("150", "100"),
    ("100", "fonds propres sont nuls"),
])
def test_saisie_refusee_avec_message_inline(page, saisie, fragment):
    mode_comparables(page)
    page.click(VERROU)
    saisir(page, saisie)

    erreur = page.inner_text("#paramsResult #erreurGearing")
    assert fragment in erreur
    assert page.get_attribute(CHAMP, "aria-invalid") == "true"


def test_une_saisie_refusee_ne_touche_pas_au_calcul(page):
    """Un CMPC recalculé sur une valeur refusée serait pire que pas de CMPC."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    avant = cmpc(page)

    page.click(VERROU)
    saisir(page, "150")
    assert cmpc(page) == avant


@pytest.mark.parametrize("saisie", ["0", "35", "99"])
def test_saisie_acceptee_dans_les_bornes(page, saisie):
    mode_comparables(page)
    page.click(VERROU)
    saisir(page, saisie)

    assert page.query_selector("#paramsResult #erreurGearing") is None
    assert page.get_attribute(CHAMP, "aria-invalid") == "false"


def test_champ_vide_revient_a_la_mediane(page, donnees):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    attendu = secteur(donnees, "Banks")["gearing"]

    page.click(VERROU)
    saisir(page, "60")
    saisir(page, "")

    assert nombre_fr(ligne_resultat(page, "Gearing sectoriel")) == round(attendu, 2)
    assert "médiane du secteur retenue" in page.inner_text("#paramsResult")


# ------------------------------------------------------- effet sur le calcul

def test_la_cible_est_lue_en_poids_de_dette(page):
    """40 % de dette, c'est D/V = 0,40 — donc une structure 60 / 40."""
    mode_comparables(page)
    page.click(VERROU)
    saisir(page, "40")

    structure = ligne_resultat(page, "Fonds propres / dette").replace(" ", " ").replace("\xa0", " ")
    assert structure == "60 % / 40 %"
    assert nombre_fr(ligne_resultat(page, "Équivalent D/E")) == 0.67


def test_le_cmpc_utilise_la_cible_et_non_la_mediane(page, donnees):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    mediane = secteur(donnees, "Banks")["gearing"]
    auto = cmpc(page)

    page.click(VERROU)
    saisir(page, "70")
    cible = cmpc(page)

    assert cible != auto
    # La dette coûte moins cher que les fonds propres : s'endetter plus baisse
    # le CMPC. Le sens du mouvement vaut vérification du branchement.
    assert cible < auto
    assert round(mediane, 2) == nombre_fr(ligne_resultat(page, "Gearing sectoriel"))


def test_le_beta_est_reendette_a_la_cible(page, donnees):
    """Changer la structure sans toucher au risque n'aurait pas de sens."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    page.click(VERROU)
    saisir(page, "70")

    page.click('.tabs button[data-tab="wacc"]')
    page.click('#stack .comp[data-comp="ke"] .comp-head')
    detail = page.inner_text('#frame .detail[data-detail="ke"]')

    b3 = secteur(donnees, "Banks")["beta_3ans"]
    assert "endett" in detail.lower()
    # Le bêta employé n'est plus celui de l'échantillon, ré-endetté qu'il est.
    assert f"Bêta (3 ans) {b3:.3f}".replace(".", ",") not in detail


def test_cible_egale_a_la_mediane_ne_change_rien(page, donnees):
    """Le ré-endettement doit être neutre quand la cible vaut l'observé."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    auto = cmpc(page)

    de = secteur(donnees, "Banks")["gearing"]
    page.click(VERROU)
    saisir(page, f"{de / (1 + de) * 100:.6f}")

    assert abs(cmpc(page) - auto) < 0.01
