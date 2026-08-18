"""Présentation et défilement des places de cotation dans le cadre Cadrage.

Les places tiennent sur une seule ligne, dans une capsule qui défile. La barre
de défilement native est masquée : c'est un rail — un vrai `input[type=range]` —
qui sert de commande, lié à la bande dans les deux sens. Un rail qui ne suivrait
pas le défilement à la molette indiquerait une position fausse dès le premier
geste.
"""

import pytest

from conftest import choisir, mode_comparables

PISTE = "#placesPiste"
RAIL = "#placesRail"
ETROIT = {"width": 430, "height": 900}


def cadrer(page):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Banks")


def deborde(page):
    return page.eval_on_selector(PISTE, "e => e.scrollWidth > e.clientWidth + 1")


def bouger(page, valeur):
    """Déplace la poignée comme le ferait l'utilisateur, événement compris."""
    page.eval_on_selector(RAIL, """(e, v) => {
        const set = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        set.call(e, String(v));
        e.dispatchEvent(new Event('input', { bubbles: true }));
    }""", valeur)


def defilement(page):
    return page.eval_on_selector(PISTE, "e => Math.round(e.scrollLeft)")


def amplitude(page):
    return page.eval_on_selector(PISTE, "e => e.scrollWidth - e.clientWidth")


# ------------------------------------------------------------- la disposition

def test_les_places_sont_sous_la_ligne_de_titre(page):
    cadrer(page)
    titre = page.eval_on_selector("#paramsMain .block-head", "e => e.getBoundingClientRect().bottom")
    bande = page.eval_on_selector(PISTE, "e => e.getBoundingClientRect().top")
    assert bande >= titre - 8
    assert page.query_selector("#paramsMain .block-head .chip") is not None


def test_chaque_place_est_une_pastille(page):
    cadrer(page)
    pastilles = page.query_selector_all(f"{PISTE} .place")
    assert len(pastilles) >= 2
    rayon = page.eval_on_selector(f"{PISTE} .place", "e => getComputedStyle(e).borderRadius")
    assert rayon.startswith(("999", "9999")) or "px" in rayon and float(rayon.rstrip("px")) > 20


def test_la_barre_native_est_masquee(page):
    """Mesuré en débordement réel : sans masquage, Chromium prendrait ~15 px."""
    cadrer(page)
    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)
    assert deborde(page), "sans débordement aucune barre n'apparaîtrait de toute façon"

    # offsetHeight - clientHeight contient aussi les bordures : on les retranche.
    epaisseur = page.eval_on_selector(PISTE, """e => {
        const s = getComputedStyle(e);
        const bords = parseFloat(s.borderTopWidth) + parseFloat(s.borderBottomWidth);
        return e.offsetHeight - e.clientHeight - bords;
    }""")
    assert epaisseur < 1, f"une barre de défilement native occupe {epaisseur} px"


def test_la_ligne_defile_au_lieu_de_passer_a_la_ligne(page):
    cadrer(page)
    avant = page.eval_on_selector(PISTE, "e => e.getBoundingClientRect().height")

    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)
    assert deborde(page), "la bande devrait déborder à cette largeur"
    apres = page.eval_on_selector(PISTE, "e => e.getBoundingClientRect().height")
    assert abs(apres - avant) < 2, "la bande s'est repliée au lieu de défiler"


def test_la_page_ne_deborde_pas_horizontalement(page):
    cadrer(page)
    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth")


# -------------------------------------------------------------------- le rail

def test_pas_de_rail_sans_debordement(page):
    cadrer(page)
    assert not deborde(page), "la bande tient en largeur ici, le test perdrait son objet"
    assert page.get_attribute(RAIL, "hidden") is not None


def test_le_rail_apparait_au_debordement(page):
    cadrer(page)
    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)
    assert deborde(page)
    assert page.get_attribute(RAIL, "hidden") is None


@pytest.mark.parametrize("position", [0, 50, 100])
def test_la_poignee_commande_le_defilement(page, position):
    cadrer(page)
    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)

    bouger(page, position)
    page.wait_for_timeout(120)
    attendu = round(position / 100 * amplitude(page))
    assert abs(defilement(page) - attendu) <= 1


def test_le_defilement_ramene_la_poignee(page):
    """Liaison dans l'autre sens : molette et doigt doivent bouger le rail."""
    cadrer(page)
    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)

    page.eval_on_selector(PISTE, "e => { e.scrollLeft = (e.scrollWidth - e.clientWidth) / 2; }")
    page.wait_for_timeout(200)
    assert abs(float(page.input_value(RAIL)) - 50) < 2


def test_la_piste_se_remplit_jusqu_a_la_poignee(page):
    cadrer(page)
    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)

    bouger(page, 40)
    page.wait_for_timeout(120)
    rempli = page.eval_on_selector(RAIL, "e => e.style.getPropertyValue('--_p')")
    assert abs(float(rempli.rstrip("%")) - 40) < 1


def test_le_rail_est_utilisable_au_clavier(page):
    """C'est un input range, donc focusable et pilotable aux flèches."""
    cadrer(page)
    page.set_viewport_size(ETROIT)
    page.wait_for_timeout(250)

    page.focus(RAIL)
    depart = defilement(page)
    for _ in range(12):
        page.keyboard.press("ArrowRight")
    page.wait_for_timeout(150)
    assert defilement(page) > depart


def test_aucune_bande_de_places_sur_un_perimetre_vide(page):
    mode_comparables(page)
    choisir(page, "continent", "Europe")
    choisir(page, "secteur", "Banks")
    assert page.query_selector(PISTE) is None
    assert page.query_selector(RAIL) is None
