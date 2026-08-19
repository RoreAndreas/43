"""Présentation d'activité : une phrase, et une vraie.

Les descriptions S&P font mille caractères en moyenne et pesaient à elles seules
les deux tiers du jeu de données embarqué. Seule leur première phrase est
retenue — encore faut-il la trouver : prise au premier point suivi d'un espace,
elle tombait sur la forme juridique pour trente pour cent des sociétés, et
« Lesaka Technologies, Inc. » tenait lieu de description d'activité.
"""

import re

import pytest

from conftest import choisir, mode_comparables


@pytest.fixture(scope="session")
def presentations(donnees):
    soc = (donnees.get("comparables") or {}).get("societes") or {}
    trouvees = {k: v["presentation"] for k, v in soc.items() if v.get("presentation")}
    if not trouvees:
        pytest.skip("aucune présentation embarquée")
    return trouvees


# ------------------------------------------------------------- la donnée

def test_presque_toutes_les_societes_en_ont_une(donnees, presentations):
    soc = donnees["comparables"]["societes"]
    assert len(presentations) / len(soc) > 0.98


def test_aucune_ne_se_reduit_au_nom_de_la_societe(donnees, presentations):
    """Le défaut d'origine : trente pour cent coupées sur « , Inc. ».

    Terminer sur une forme juridique n'est pas fautif en soi — « operates as a
    subsidiary of Imperial Tobacco Group plc. » est une phrase entière. Ce qui
    l'est, c'est un résumé qui n'apprend rien de plus que le nom déjà affiché
    sur la carte.
    """
    soc = donnees["comparables"]["societes"]
    muettes = [f"{soc[i]['nom']} -> {t}" for i, t in presentations.items()
               if len(t) <= len(soc[i]["nom"]) + 6]
    assert not muettes, f"{len(muettes)} résumés muets, ex. {muettes[:3]}"


def test_aucune_n_est_reduite_a_un_fragment(presentations):
    """Une « phrase » de vingt caractères est un artefact, pas une description."""
    courtes = [t for t in presentations.values() if len(t) < 25]
    assert not courtes, f"fragments : {courtes[:5]}"


def test_une_seule_phrase(presentations):
    """Deux phrases signifieraient que la coupure a été manquée."""
    trop = [t for t in presentations.values()
            if len(re.findall(r"[a-z]{3,}\.\s+[A-Z]", t)) > 0]
    assert len(trop) / len(presentations) < 0.02, f"ex. {trop[:2]}"


def test_le_plafond_est_respecte(presentations):
    trop_longues = [t for t in presentations.values() if len(t) > 221]
    assert not trop_longues, f"{len(trop_longues)} au-delà du plafond"


# --------------------------------------------------------------- l'écran

def test_la_presentation_s_affiche_dans_le_detail(page, donnees):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Banks")
    page.click('.tabs button[data-tab="societes"]')
    page.click("#stackSoc .comp:first-of-type .comp-head")
    page.wait_for_timeout(400)

    carte = page.query_selector("#stackSoc .comp:first-of-type")
    societe = donnees["comparables"]["societes"][carte.get_attribute("data-comp")]
    detail = page.inner_text("#frameSoc .detail.is-shown")

    assert "PRÉSENTATION" in detail.upper()
    assert societe["presentation"] in detail


def test_le_tableau_financier_defile_au_lieu_de_se_tasser(page):
    """Les montants américains en FCFA font douze chiffres : deux colonnes
    voisines se touchaient au point qu'un tiret se lisait comme un signe moins."""
    mode_comparables(page)
    page.evaluate("""() => { params.continent = 'Amériques';
                             params.zone = 'Amérique du Nord';
                             params.secteur = 'Banks'; apply(); }""")
    page.click('.tabs button[data-tab="societes"]')
    page.click("#stackSoc .comp:first-of-type .comp-head")
    page.wait_for_timeout(400)

    bulle = page.query_selector("#frameSoc .detail.is-shown .bulle-defilante")
    assert bulle is not None, "le tableau n'est pas dans une bulle défilante"
    gouttiere = page.eval_on_selector(
        "#frameSoc .detail.is-shown .fin-table td:nth-child(2)",
        "e => parseFloat(getComputedStyle(e).paddingLeft)")
    assert gouttiere >= 10, f"gouttière de {gouttiere} px entre colonnes"
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth")
