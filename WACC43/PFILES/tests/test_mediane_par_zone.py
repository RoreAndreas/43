"""La médiane sectorielle se prend sur la zone, avec repli sur le continent.

L'univers est mince : sur les 126 couples zone x secteur, 40 % ne comptent
aucune société et un tiers une seule. Une médiane sur une seule société n'est
pas une médiane, c'est cette société. En deçà de trois, la page reprend donc la
médiane du continent — et l'écrit, faute de quoi une médiane continentale
passerait pour une médiane de zone.

Le pays, lui, ne suit plus la zone. Il désigne l'émetteur valorisé, donc la
courbe souveraine et le taux d'IS ; la zone désigne l'échantillon de
comparables. Les coupler privait de taux sans risque dès qu'on regardait une
zone hors UMOA, soit quatre zones africaines sur cinq.
"""

import pytest

from conftest import choisir, ligne_resultat, mode_comparables, nombre_fr, secteur

ZONES = ["Afrique de l'Ouest", "Afrique de l'Est", "Afrique australe"]


def cadrer(page, zone=None, secteur_nom="Banks"):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", secteur_nom)
    if zone:
        page.click(f'#paramsMain .zone[data-zone="{zone}"]')


def cmpc(page):
    return page.inner_text("#paramsResult .result-hero-value").strip()


def echantillon(page):
    """(libellé du périmètre, effectif) tels qu'affichés."""
    for bloc in page.query_selector_all("#paramsResult .result-row"):
        spans = bloc.query_selector_all("span")
        if spans and spans[0].inner_text().startswith("Sociétés du secteur"):
            libelle = spans[0].inner_text().replace("Sociétés du secteur,", "").strip()
            return libelle, int(nombre_fr(spans[-1].inner_text()))
    raise AssertionError("ligne d'effectif absente")


# ------------------------------------------------- la médiane suit bien la zone

@pytest.mark.parametrize("zone", ZONES)
def test_le_beta_affiche_est_celui_de_la_zone(page, donnees, zone):
    """Les banques n'ont pas le même bêta d'une zone à l'autre : il doit suivre."""
    cadrer(page, zone)
    attendu = secteur(donnees, "Banks", zone)
    assert echantillon(page) == (zone, attendu["societes"])
    assert nombre_fr(ligne_resultat(page, "Bêta médian (3 ans)")) == round(attendu["beta_3ans"], 3)
    assert nombre_fr(ligne_resultat(page, "Gearing sectoriel")) == round(attendu["gearing"], 2)


def test_changer_de_zone_change_le_cmpc(page):
    """Sans cela, restreindre par zone n'aurait aucun effet observable."""
    cadrer(page)
    vus = {}
    for zone in ZONES:
        page.click(f'#paramsMain .zone[data-zone="{zone}"]')
        vus[zone] = cmpc(page)
        page.click(f'#paramsMain .zone[data-zone="{zone}"]')
    assert len(set(vus.values())) > 1, f"CMPC identique partout : {vus}"


def test_sans_zone_la_mediane_porte_sur_le_continent(page, donnees):
    cadrer(page)
    attendu = secteur(donnees, "Banks", "Afrique")
    assert echantillon(page) == ("Afrique", attendu["societes"])


# --------------------------------------------------------------- le repli

def test_une_zone_trop_mince_replie_sur_le_continent(page, donnees):
    """Consumer Finance : une société en Afrique australe, deux sur le continent."""
    cadrer(page, "Afrique australe", "Consumer Finance")

    libelle, n = echantillon(page)
    assert libelle == "Afrique"
    assert n == secteur(donnees, "Consumer Finance", "Afrique")["societes"]


def test_le_repli_est_annonce_a_l_ecran(page):
    """Un repli muet ferait passer une médiane continentale pour une de zone."""
    cadrer(page, "Afrique australe", "Consumer Finance")
    encadre = page.inner_text("#paramsResult")

    assert "sous le seuil de 3" in encadre
    assert "Afrique australe ne compte 1 société" in encadre
    assert "médiane reprise sur Afrique" in encadre


def test_pas_de_repli_annonce_quand_la_zone_suffit(page):
    cadrer(page, "Afrique australe", "Banks")
    assert "sous le seuil" not in page.inner_text("#paramsResult")


def test_une_zone_vide_replie_aussi(page, donnees):
    """Aucune banque en Afrique du Nord : le continent prend le relais."""
    cadrer(page, "Afrique du Nord", "Banks")
    libelle, n = echantillon(page)
    assert libelle == "Afrique"
    assert n == secteur(donnees, "Banks", "Afrique")["societes"]


# ------------------------------------------- le pays ne suit plus la zone

@pytest.mark.parametrize("zone", ZONES + ["Afrique du Nord", "Afrique centrale"])
def test_la_zone_ne_deplace_pas_le_pays(page, zone):
    """Le pays porte la courbe souveraine : la zone ne doit pas la lui prendre."""
    cadrer(page, zone)
    assert page.evaluate("params.country") == "Benin"
    assert cmpc(page) != "—", f"CMPC perdu sur la zone {zone}"


def test_le_continent_filtre_toujours_les_pays(page):
    """Le filtrage par continent, lui, reste : c'est ce qui avait été demandé."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    proposes = page.eval_on_selector_all(
        '#paramsMain select[data-param="country"] option', "e => e.map(o => o.value)")
    assert "Benin" in proposes
    assert "France" not in proposes
    assert len(proposes) < 60, "la liste n'est plus filtrée par continent"


def test_le_champ_pays_dit_son_role(page):
    mode_comparables(page)
    libelles = [e.inner_text() for e in page.query_selector_all("#paramsMain .geo-choix .field-label")]
    assert "Pays de valorisation" in libelles
