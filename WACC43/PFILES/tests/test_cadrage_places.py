"""Présentation et défilement des places de cotation dans le cadre Cadrage.

Les places tiennent sur une seule ligne, dans une capsule qui défile. La barre
de défilement native est masquée : c'est un rail — un vrai `input[type=range]` —
qui sert de commande, lié à la bande dans les deux sens. Un rail qui ne suivrait
pas le défilement à la molette indiquerait une position fausse dès le premier
geste.
"""

import pytest

from conftest import choisir, continent_vide, ligne_resultat, mode_comparables, nombre_fr

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


def test_aucune_bande_de_places_sur_un_perimetre_vide(page, donnees):
    mode_comparables(page)
    choisir(page, "continent", continent_vide(donnees))
    choisir(page, "secteur", "Banks")
    assert page.query_selector(PISTE) is None
    assert page.query_selector(RAIL) is None


# --------------------------------------------------------- le focus sur une place
# Même mécanique que le cadenas du gearing : fermé par défaut, il faut l'ouvrir
# avant de pouvoir restreindre le calcul à une place précise.

VERROU = "#verrouPlace"


def cadrer_telecom(page):
    """Un secteur avec plusieurs places, dont une (BRVM) qui dépasse le seuil —
    c'est le cas qui a motivé le focus : Orange CI et Sonatel n'y comptaient
    pas ensemble avant la fusion des deux intitulés télécoms."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Telecommunication Services")


def test_le_cadenas_est_ferme_par_defaut(page):
    cadrer_telecom(page)
    assert page.get_attribute(VERROU, "aria-pressed") == "false"
    assert page.query_selector(f"{PISTE} .place[data-place]") is None, \
        "les pastilles ne doivent pas être cliquables verrou fermé"


def test_le_cadenas_n_apparait_pas_sous_damodaran(page):
    """Il n'y a rien à restreindre : le référentiel Damodaran ne calcule pas
    de médiane sur l'univers de comparables."""
    page.select_option('#paramsMain select[data-param="continent"]', "Afrique")
    assert page.query_selector(PISTE) is not None, "les places restent affichées, à titre informatif"
    assert page.query_selector(VERROU) is None


def test_ouvrir_le_cadenas_rend_les_pastilles_cliquables(page):
    cadrer_telecom(page)
    page.click(VERROU)
    assert page.get_attribute(VERROU, "aria-pressed") == "true"
    assert page.query_selector(f'{PISTE} .place[data-place="BRVM"]') is not None


def test_cliquer_une_place_restreint_le_calcul(page):
    cadrer_telecom(page)
    avant = nombre_fr(ligne_resultat(page, "Sociétés du secteur"))

    page.click(VERROU)
    page.click(f'{PISTE} .place[data-place="BRVM"]')

    assert "is-actif" in page.get_attribute(f'{PISTE} .place[data-place="BRVM"]', "class")
    apres = nombre_fr(ligne_resultat(page, "Sociétés du secteur"))
    assert apres < avant, "le focus doit réduire l'échantillon à la seule place choisie"
    # Le libellé de la ligne porte le périmètre retenu, comme il le fait déjà
    # pour une zone : « Sociétés du secteur, BRVM ».
    lignes = page.eval_on_selector_all(
        "#paramsResult .result-row > span:first-child", "els => els.map(e => e.textContent)")
    assert any("BRVM" in l for l in lignes)


def test_orange_ci_et_sonatel_comptent_ensemble_sur_brvm(page):
    """Le cas qui a motivé la demande : les deux sociétés du même groupe,
    listées sur la même place, doivent désormais peser dans la même médiane."""
    cadrer_telecom(page)
    page.click(VERROU)
    page.click(f'{PISTE} .place[data-place="BRVM"]')
    assert nombre_fr(ligne_resultat(page, "Sociétés du secteur")) >= 2


def test_recliquer_la_meme_place_annule_le_focus(page):
    cadrer_telecom(page)
    avant = nombre_fr(ligne_resultat(page, "Sociétés du secteur"))

    page.click(VERROU)
    page.click(f'{PISTE} .place[data-place="BRVM"]')
    page.click(f'{PISTE} .place[data-place="BRVM"]')

    assert "is-actif" not in page.get_attribute(f'{PISTE} .place[data-place="BRVM"]', "class")
    assert nombre_fr(ligne_resultat(page, "Sociétés du secteur")) == avant


def test_refermer_le_cadenas_efface_le_focus(page):
    cadrer_telecom(page)
    avant = nombre_fr(ligne_resultat(page, "Sociétés du secteur"))

    page.click(VERROU)
    page.click(f'{PISTE} .place[data-place="BRVM"]')
    page.click(VERROU)

    assert page.get_attribute(VERROU, "aria-pressed") == "false"
    assert page.query_selector(f"{PISTE} .place[data-place]") is None
    assert nombre_fr(ligne_resultat(page, "Sociétés du secteur")) == avant


def test_le_clavier_active_une_place(page):
    """Les pastilles cliquables sont aussi des boutons au clavier (Entrée/Espace)."""
    cadrer_telecom(page)
    page.click(VERROU)
    page.focus(f'{PISTE} .place[data-place="BRVM"]')
    page.keyboard.press("Enter")
    assert "is-actif" in page.get_attribute(f'{PISTE} .place[data-place="BRVM"]', "class")
