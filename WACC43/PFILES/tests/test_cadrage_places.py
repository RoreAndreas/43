"""Présentation des places de cotation dans le cadre Cadrage.

Les places tiennent sur leur propre ligne, sous la ligne de titre, et cette
ligne défile au lieu de s'allonger. Sans cela le cadre changerait de hauteur
selon l'industrie choisie, et la carte sauterait à chaque changement de secteur.
"""

from conftest import choisir, mode_comparables

PLACES = "#paramsMain .places"


def hauteur(page, selecteur):
    return page.eval_on_selector(selecteur, "e => e.getBoundingClientRect().height")


def test_les_places_sont_sous_la_ligne_de_titre(page):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")

    titre = page.eval_on_selector("#paramsMain .block-head", "e => e.getBoundingClientRect().bottom")
    places = page.eval_on_selector(PLACES, "e => e.getBoundingClientRect().top")
    assert places >= titre - 8, "les places doivent rester sous la ligne de titre"
    # La bulle de périmètre, elle, reste sur la ligne de titre.
    assert page.query_selector("#paramsMain .block-head .chip") is not None


def test_la_ligne_defile_au_lieu_de_passer_a_la_ligne(page):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")
    avant = hauteur(page, PLACES)

    # On rétrécit le conteneur pour simuler une liste bien plus longue.
    page.add_style_tag(content=".places { max-width: 140px; }")
    large, visible = page.eval_on_selector(PLACES, "e => [e.scrollWidth, e.clientWidth]")

    assert large > visible, "la ligne devrait déborder et donc défiler"
    assert abs(hauteur(page, PLACES) - avant) < 2, "la ligne s'est repliée au lieu de défiler"

    page.eval_on_selector(PLACES, "e => e.scrollLeft = 9999")
    assert page.eval_on_selector(PLACES, "e => e.scrollLeft") > 0


def test_la_page_ne_deborde_pas_horizontalement(page):
    """Une ligne qui déborde ne doit jamais élargir la page elle-même."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")

    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth")


def test_aucune_ligne_de_places_sur_un_perimetre_vide(page):
    mode_comparables(page)
    choisir(page, "continent", "Europe")
    choisir(page, "industrie_brvm", "Banks")
    assert page.query_selector(PLACES) is None
