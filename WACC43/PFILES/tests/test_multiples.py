"""L'onglet Multiples : le cadre doit suivre la quantité d'information.

Les multiples d'entreprise servent la valorisation par comparables — ils
n'entrent pas dans le coût du capital, mais c'est la même population qui les
produit. Or S&P ne publie pas d'EBITDA pour les banques ni pour les assureurs :
la notion n'a pas de sens pour elles. Un secteur de vingt comparables peut donc
n'en compter qu'une qui en porte un, ou aucune.

D'où la règle que ces tests vérifient, aux trois paliers :

    aucune valeur   -> pas de graphique du tout, une phrase qui dit pourquoi ;
                       les colonnes du tableau disparaissent
    sous le seuil   -> les nombres écrits en clair, sans barres ni médiane :
                       seule, une barre remplit la piste et se lit comme un
                       maximum alors qu'elle n'est comparée à rien
    au-delà         -> graphique, repère de médiane, effectif écrit en clair

C'est le seuil qui gouverne déjà les médianes de zone du CMPC, pour la même
raison : en deçà, la médiane serait cette société.
"""

import pytest

from conftest import choisir, mode_comparables

ONGLET = '.tabs button[data-tab="multiples"]'
GRAPH, CALC = "#multiplesGraph", "#multiplesCalc"
TETE = "#multiplesGraph .multiples-chart-ville"


def cadrer(page, continent, secteur):
    mode_comparables(page)
    choisir(page, "continent", continent)
    choisir(page, "secteur", secteur)
    page.click(ONGLET)
    page.wait_for_timeout(200)


def telecom(page):
    """Onze opérateurs africains, tous publiant un EBITDA."""
    cadrer(page, "Afrique", "Telecommunication Services")


def banques(page):
    """Vingt banques africaines : une seule publie un EBITDA."""
    cadrer(page, "Afrique", "Banks")


def compte(page, selecteur):
    return page.eval_on_selector_all(selecteur, "e => e.length")


def seuil(donnees):
    return (donnees.get("comparables") or {}).get("seuil") or 3


# ------------------------------------------------------------------- l'onglet

def test_l_onglet_n_existe_que_sous_comparables(page):
    """Le référentiel Damodaran ne lit aucune société : il n'y a pas de
    multiple à en tirer."""
    assert page.get_attribute("#tabMultiples", "hidden") is not None
    mode_comparables(page)
    assert page.get_attribute("#tabMultiples", "hidden") is None


def test_les_deux_vues_s_echangent(page):
    telecom(page)
    assert page.is_visible(GRAPH) and page.is_hidden(CALC)
    page.click('#multiplesToggle button[data-view="calc"]')
    page.wait_for_timeout(150)
    assert page.is_hidden(GRAPH) and page.is_visible(CALC)


def test_l_exercice_et_le_perimetre_sont_annonces(page):
    telecom(page)
    barre = page.inner_text("#multiplesExercice")
    assert "Afrique" in barre and "exercice" in barre


# ------------------------------------------- le cadre suit l'information

def test_avec_assez_de_valeurs_le_graphique_porte_sa_mediane(page):
    telecom(page)
    assert compte(page, "#multiplesGraph .multiple-bar-row") > 0
    assert compte(page, "#multiplesGraph .multiple-bar-mediane") > 0
    assert compte(page, "#multiplesGraph .multiples-vide") == 0
    assert all("médiane" in t for t in page.eval_on_selector_all(
        TETE, "e => e.map(x => x.textContent)"))


def test_sous_le_seuil_pas_de_barres_ni_de_mediane(page, donnees):
    """Une valeur ne fait pas un graphique : on écrit le nombre."""
    banques(page)
    tetes = page.eval_on_selector_all(TETE, "e => e.map(x => x.textContent)")
    ebitda = tetes[0]
    assert "médiane" not in ebitda, f"tête inattendue : {ebitda}"
    assert "sur" in ebitda, "l'effectif doit être écrit : « n société sur m »"
    # La section VE/EBITDA rend un texte, pas des barres.
    section = page.query_selector("#multiplesGraph .multiples-chart")
    assert section.query_selector(".multiples-vide") is not None
    assert section.query_selector(".multiple-bar-row") is None


def test_l_effectif_annonce_est_celui_du_ratio_pas_de_l_echantillon(page):
    """C'est le défaut d'origine : « médiane de l'échantillon (20 sociétés) »
    au-dessus d'un multiple tiré d'une seule."""
    banques(page)
    ebitda = page.eval_on_selector_all(TETE, "e => e.map(x => x.textContent)")[0]
    total = page.inner_text("#multiplesExercice")
    assert "20" in total
    assert "1 société sur 20" in ebitda


def test_sans_aucune_valeur_le_graphique_cede_la_place_a_une_phrase(page):
    """Sur l'univers, aucune des vingt premières banques ne publie d'EBITDA :
    un cadre vide se lirait comme une panne."""
    cadrer(page, "Tous", "Banks")
    section = page.query_selector("#multiplesGraph .multiples-chart")
    vide = section.query_selector(".multiples-vide")
    assert vide is not None
    texte = vide.inner_text()
    assert "Aucune" in texte and "EBITDA" in texte


def test_les_colonnes_disparaissent_avec_leur_ratio(page):
    """Le tableau ne garde pas trois colonnes vides pour mémoire."""
    cadrer(page, "Tous", "Banks")
    page.click('#multiplesToggle button[data-view="calc"]')
    page.wait_for_timeout(150)
    colonnes = page.eval_on_selector_all("#multiplesCalc th", "e => e.map(x => x.textContent)")
    assert not any("EBITDA" in c for c in colonnes), colonnes
    assert any("VE / CA" in c for c in colonnes)


def test_la_ligne_de_mediane_se_tait_sous_le_seuil(page):
    """Une case vide dit « pas assez de valeurs » ; un nombre dirait l'inverse."""
    banques(page)
    page.click('#multiplesToggle button[data-view="calc"]')
    page.wait_for_timeout(150)
    colonnes = page.eval_on_selector_all("#multiplesCalc th", "e => e.map(x => x.textContent)")
    cases = page.eval_on_selector_all("#multiplesCalc tr.is-mediane td",
                                      "e => e.map(x => x.textContent)")
    assert cases[colonnes.index("VE / EBITDA")] == "—"
    assert cases[colonnes.index("VE / CA")].endswith("x")


def test_la_note_chiffre_ce_qui_manque(page, donnees):
    banques(page)
    page.click('#multiplesToggle button[data-view="calc"]')
    page.wait_for_timeout(150)
    note = page.inner_text("#multiplesCalc .multiples-note")
    assert "VE / EBITDA : 1 société sur 20" in note
    assert str(seuil(donnees)) in note
    assert "n'entrent pas dans le coût du capital" in note


# ------------------------------------------------------------ le fond commun

def test_orange_ci_et_sonatel_figurent_dans_le_meme_graphique(page):
    """Même population que l'onglet Sociétés et que la feuille exportée."""
    telecom(page)
    noms = page.eval_on_selector_all("#multiplesGraph .multiple-bar-label",
                                     "e => e.map(x => x.textContent)")
    assert "Orange CI" in noms and "Sonatel SA" in noms


def test_un_perimetre_sans_societe_le_dit(page, donnees):
    from conftest import continent_vide
    mode_comparables(page)
    choisir(page, "continent", continent_vide(donnees))
    choisir(page, "secteur", "Banks")
    page.click(ONGLET)
    page.wait_for_timeout(200)
    # Le CMPC reste calculé sur un périmètre plus large, mais l'onglet ne doit
    # pas prétendre décrire des sociétés qu'il n'affiche pas.
    assert page.query_selector("#multiplesGraph .multiples-chart, #multiplesGraph .multiples-vide")
