"""L'onglet Sociétés doit se réécrire à chaque changement de périmètre.

Deux défauts se cachaient derrière « l'onglet ne s'actualise pas » :

- une industrie sans société cotée retombait sur la première industrie de la
  liste, et l'onglet montrait alors les sociétés d'un autre secteur ;
- le filtre géographique n'était pas appliqué du tout : les quatorze banques
  ivoiriennes restaient à l'écran avec l'Europe sélectionnée.

Dans les deux cas l'écran affichait quelque chose de plausible, donc personne ne
voyait qu'il répondait à une autre question.
"""

import pytest

from conftest import choisir, mode_comparables

VIDE = "#stackSoc .vide404"


def ouvrir_societes(page):
    page.click('.tabs button[data-tab="societes"]')


def revenir_aux_parametres(page):
    page.click('.tabs button[data-tab="params"]')


def cartes(page):
    ouvrir_societes(page)
    noms = [e.inner_text().strip() for e in page.query_selector_all("#stackSoc .comp-title")]
    revenir_aux_parametres(page)
    return noms


def etat_vide(page):
    ouvrir_societes(page)
    present = page.query_selector(VIDE) is not None
    revenir_aux_parametres(page)
    return present


# ------------------------------------------------ le repli sur une autre industrie

def test_une_industrie_sans_societe_cotee_n_emprunte_pas_celles_d_une_autre(page):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Air Freight and Logistics")
    air = cartes(page)
    assert air, "cette industrie a bien une société cotée, le test perdrait son sens"

    choisir(page, "industrie_brvm", "Capital Markets")
    assert cartes(page) == []
    assert etat_vide(page)


def test_l_onglet_suit_chaque_changement_d_industrie(page):
    mode_comparables(page)
    vus = []
    for industrie in ["Banks", "Capital Markets", "Tobacco", "Banks"]:
        choisir(page, "industrie_brvm", industrie)
        vus.append(tuple(cartes(page)))

    assert vus[0] != vus[1], "passage à un secteur vide sans effet à l'écran"
    assert vus[1] != vus[2], "passage d'un secteur vide à un secteur peuplé sans effet"
    assert vus[0] == vus[3], "le retour au secteur d'origine doit redonner la même liste"


# ------------------------------------------------------- le filtre géographique

@pytest.mark.parametrize("continent", ["Europe", "Asie", "Amériques"])
def test_un_continent_sans_societe_cotee_vide_la_liste(page, continent):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    assert cartes(page), "les banques doivent être listées avant de filtrer"

    choisir(page, "continent", continent)
    assert cartes(page) == []
    assert etat_vide(page)


def test_le_retour_sur_l_afrique_rend_la_liste(page):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    attendu = cartes(page)

    choisir(page, "continent", "Europe")
    assert cartes(page) == []

    choisir(page, "continent", "Afrique")
    assert cartes(page) == attendu


def test_les_societes_listees_sont_dans_le_perimetre(page, donnees):
    """Chaque société affichée doit appartenir à une zone du filtre courant."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    choisir(page, "continent", "Afrique")

    ouvrir_societes(page)
    tickers = [e.get_attribute("data-comp") for e in page.query_selector_all("#stackSoc .comp")]
    revenir_aux_parametres(page)

    assert tickers, "aucune société lue"
    for ticker in tickers:
        pays = donnees["brvm"]["societes"][ticker]["pays"]
        zone = zone_du_pays(donnees, pays)
        assert zone is not None, f"{ticker} ({pays}) n'est rattachée à aucune zone"
        assert continent_du_pays(donnees, pays) == "Afrique"


def _sans_accent(texte: str) -> str:
    import unicodedata
    decompose = unicodedata.normalize("NFD", str(texte))
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").lower().strip()


def _entree_pays(donnees: dict, nom: str):
    cible = _sans_accent(nom)
    for cle, entree in donnees["pays"].items():
        if _sans_accent(cle) == cible:
            return entree
    return None


def zone_du_pays(donnees, nom):
    entree = _entree_pays(donnees, nom)
    return entree.get("zone") if entree else None


def continent_du_pays(donnees, nom):
    entree = _entree_pays(donnees, nom)
    return entree.get("continent") if entree else None


# --------------------------------------------------------------- l'état vide

def test_l_etat_vide_est_explicite_et_situe(page):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    choisir(page, "continent", "Europe")

    ouvrir_societes(page)
    texte = page.inner_text(VIDE)
    assert "404" in texte
    assert "Aucune société trouvée" in texte
    # Il doit dire *où* et *quoi*, sans quoi l'utilisateur ne sait pas quoi changer.
    assert "Banks" in texte
    assert "Europe" in texte
    assert page.query_selector(f"{VIDE} .vide404-img") is not None


def test_l_etat_vide_ne_laisse_aucune_carte_derriere_lui(page):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    choisir(page, "continent", "Europe")

    ouvrir_societes(page)
    assert page.query_selector_all("#stackSoc .comp") == []
    assert page.inner_html("#frameSoc").strip() == ""
    assert "is-on" not in (page.get_attribute("#frameColSoc", "class") or "")
