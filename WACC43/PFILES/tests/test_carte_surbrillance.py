"""La carte ne met en avant que ce qui existe.

Une zone sans société pour l'industrie retenue n'a rien à montrer : elle est
tracée en neutre et la sélection ne l'allume pas. Garder la surbrillance sur une
zone vide laissait croire qu'un résultat s'y trouvait.
"""

import pytest

from conftest import choisir, mode_comparables

ZONES = "#paramsMain .zone"


def etats(page):
    """{zone: classes} tel que rendu sur la carte."""
    lu = page.eval_on_selector_all(
        ZONES, "els => els.map(e => [e.dataset.zone, e.getAttribute('class')])")
    return dict(lu)


def peuplement(donnees, industrie):
    """{zone: effectif} d'après le jeu de données embarqué."""
    source = donnees["comparables"]["zones"]
    zones = [z[0] for z in donnees["options"]["zones_par_continent"]["Afrique"]]
    return {
        zone: ((source.get(zone, {}).get("industries") or {}).get(industrie) or {}).get("n", 0)
        for zone in zones
    }


@pytest.mark.parametrize("industrie", ["Banks", "Air Freight and Logistics", "Capital Markets"])
def test_les_zones_vides_sont_tracees_en_neutre(page, donnees, industrie):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", industrie)

    attendu = peuplement(donnees, industrie)
    for zone, classes in etats(page).items():
        vide = "is-vide" in classes
        assert vide == (attendu[zone] == 0), f"{zone} : effectif {attendu[zone]}, classes « {classes} »"


def test_cliquer_une_zone_vide_ne_l_allume_pas(page, donnees):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")

    vides = [z for z, n in peuplement(donnees, "Banks").items() if n == 0]
    assert vides, "aucune zone vide : le test perdrait son objet"

    page.click(f'{ZONES}[data-zone="{vides[0]}"]')
    classes = etats(page)[vides[0]]
    assert "is-on" not in classes
    assert "is-vide" in classes


def test_cliquer_une_zone_peuplee_l_allume(page, donnees):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")

    pleines = [z for z, n in peuplement(donnees, "Banks").items() if n]
    page.click(f'{ZONES}[data-zone="{pleines[0]}"]')

    apres = etats(page)
    assert "is-on" in apres[pleines[0]]
    for autre in pleines[1:]:
        assert "is-on" not in apres[autre], "une seule zone à la fois doit être allumée"


def test_la_surbrillance_tombe_quand_l_industrie_vide_la_zone(page, donnees):
    """Le nettoyage se fait au même rafraîchissement que l'onglet Sociétés."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")

    zone = "Afrique australe"
    assert peuplement(donnees, "Banks")[zone] > 0
    page.click(f'{ZONES}[data-zone="{zone}"]')
    assert "is-on" in etats(page)[zone]

    # Ce secteur n'a aucune société en Afrique australe : la zone reste le
    # cadrage retenu, mais plus rien n'y est mis en avant.
    choisir(page, "industrie_brvm", "Air Freight and Logistics")
    assert peuplement(donnees, "Air Freight and Logistics")[zone] == 0

    classes = etats(page)[zone]
    assert "is-on" not in classes
    assert "is-vide" in classes
    assert "aucune société" in page.inner_text("#paramsMain .block-head .chip")

    # Et l'onglet Sociétés est vide au même instant, sans surbrillance résiduelle.
    page.click('.tabs button[data-tab="societes"]')
    assert page.query_selector("#stackSoc .vide404") is not None
    assert "is-on" not in (page.get_attribute("#frameColSoc", "class") or "")


def test_l_infobulle_dit_l_effectif(page, donnees):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "industrie_brvm", "Banks")

    titres = dict(page.eval_on_selector_all(
        ZONES, "els => els.map(e => [e.dataset.zone, e.querySelector('title').textContent])"))
    attendu = peuplement(donnees, "Banks")
    for zone, titre in titres.items():
        if attendu[zone]:
            assert f"{attendu[zone]} société" in titre
        else:
            assert "aucune société" in titre
