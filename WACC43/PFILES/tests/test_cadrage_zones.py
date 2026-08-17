"""Le cadrage doit décrire la sélection, pas le continent entier.

Le défaut : une zone sans société de l'industrie choisie continuait d'apporter
ses places de cotation au résumé, parce que le code retombait sur les places de
la zone toutes industries confondues. Sur « Air Freight and Logistics » en
Afrique, trois sociétés étaient annoncées et dix marchés listés — ceux
d'Afrique australe et de l'Est en tête, qui n'en cotent aucune.
"""

import pytest

from conftest import choisir, mode_comparables


def chips(page):
    return [e.inner_text().strip() for e in page.query_selector_all("#paramsMain .block-head .chip")]


def places(page):
    """Les places affichées sur la ligne de marchés, si elle existe."""
    return sorted(
        e.inner_text().strip()
        for e in page.query_selector_all("#paramsMain .places .place")
    )


def places_attendues(donnees, industrie, zones):
    """Les places réellement porteuses de cette industrie dans ces zones."""
    source = donnees["comparables"]["zones"]
    trouve = set()
    for zone in zones:
        detail = (source.get(zone, {}).get("industries") or {}).get(industrie)
        if detail:
            trouve |= set(detail["places"])
    return sorted(trouve)


def zones_du_continent(donnees, continent):
    return [z[0] for z in donnees["options"]["zones_par_continent"][continent]]


# ---------------------------------------------------------- les places listées

@pytest.mark.parametrize("industrie", ["Air Freight and Logistics", "Capital Markets", "Banks"])
def test_seules_les_places_porteuses_sont_listees(page, donnees, industrie):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", industrie)

    attendu = places_attendues(donnees, industrie, zones_du_continent(donnees, "Afrique"))
    assert places(page) == attendu


def test_une_zone_vide_n_apporte_aucune_place(page, donnees):
    """Le cas exact du rapport : trois sociétés, deux marchés, pas dix."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Air Freight and Logistics")

    source = donnees["comparables"]["zones"]
    vides = [
        zone for zone in zones_du_continent(donnees, "Afrique")
        if not (source.get(zone, {}).get("industries") or {}).get("Air Freight and Logistics")
    ]
    assert vides, "aucune zone vide : le test perdrait son objet"

    interdites = set()
    for zone in vides:
        interdites |= set(source.get(zone, {}).get("places") or {})
    interdites -= set(places_attendues(donnees, "Air Freight and Logistics",
                                       zones_du_continent(donnees, "Afrique")))

    assert not (set(places(page)) & interdites), (
        "des marchés de zones sans société de ce secteur restent affichés")


# ------------------------------------------------------------ le décompte

@pytest.mark.parametrize("industrie", ["Air Freight and Logistics", "Capital Markets", "Banks"])
def test_l_effectif_annonce_est_la_somme_des_zones(page, donnees, industrie):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", industrie)

    source = donnees["comparables"]["zones"]
    attendu = sum(
        ((source.get(zone, {}).get("industries") or {}).get(industrie) or {}).get("n", 0)
        for zone in zones_du_continent(donnees, "Afrique")
    )
    assert f"{attendu} société" in chips(page)[0]


def test_une_zone_selectionnee_restreint_le_resume(page, donnees):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")
    continent = chips(page)[0]

    page.click('#paramsMain .zone[data-zone="Afrique de l\'Ouest"]')
    zone = chips(page)[0]

    assert "Afrique de l'Ouest" in zone
    assert zone != continent

    source = donnees["comparables"]["zones"]
    attendu = source["Afrique de l'Ouest"]["industries"]["Banks"]["n"]
    assert f"{attendu} société" in zone


def test_une_zone_sans_societe_le_dit(page, donnees):
    """« aucune société » plutôt qu'un tiret qu'on lirait comme une lacune."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")

    page.click('#paramsMain .zone[data-zone="Afrique du Nord"]')
    resume = chips(page)[0]
    assert "aucune société" in resume
    assert places(page) == [], "aucune place affichée sur un périmètre vide"
