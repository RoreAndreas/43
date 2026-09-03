"""Le bouton flèche demande d'abord si les comparables accompagnent le calcul.

Reprise de l'interaction dessinée dans la maquette : le bouton n'exporte plus
directement, il ouvre une boîte qui demande si la feuille « Sociétés » doit
suivre. Deux raisons de la tester par ses issues plutôt que par son affichage :
un « Annuler » qui téléchargerait quand même serait pire qu'une absence de
boîte, et un « Non » qui joindrait la feuille ferait mentir la question.

La question ne se pose que lorsqu'il y a une feuille à joindre. Sous le
référentiel Damodaran aucune société n'entre dans le calcul : demander à
choisir entre une réponse et rien serait du bruit, et le classeur part
directement.
"""

import pytest

from conftest import choisir, mode_comparables

openpyxl = pytest.importorskip("openpyxl")

FLECHE = "#telecharger"
FOND = "#exportFond"
OUI, NON, ANNULER = "#exportOui", "#exportNon", "#exportAnnuler"


def cadrer(page):
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Telecommunication Services")


def ouvrir(page):
    cadrer(page)
    page.click(FLECHE)
    page.wait_for_selector(FOND, state="visible")


def onglets(page, tmp_path, bouton, nom):
    with page.expect_download() as attente:
        page.click(bouton)
    chemin = tmp_path / nom
    attente.value.save_as(str(chemin))
    return openpyxl.load_workbook(chemin).sheetnames


# ------------------------------------------------------------------ la boîte

def test_la_boite_est_fermee_au_depart(page):
    cadrer(page)
    assert page.is_hidden(FOND)


def test_la_fleche_ouvre_la_boite_au_lieu_d_exporter(page):
    ouvrir(page)
    assert page.is_visible(FOND)
    assert "comparables boursiers" in page.inner_text("#exportTitre")
    # Le détail annonce ce que la feuille contient : on choisit en sachant.
    detail = page.inner_text("#exportDetail")
    for mot in ("capitalisation", "dette", "VE", "EBITDA"):
        assert mot in detail


def test_la_boite_est_un_dialogue_pour_le_lecteur_d_ecran(page):
    ouvrir(page)
    boite = page.query_selector(".export-boite")
    assert boite.get_attribute("role") == "dialog"
    assert boite.get_attribute("aria-modal") == "true"


# ------------------------------------------------------------- les quatre issues

def test_oui_joint_la_feuille_societes(page, tmp_path):
    ouvrir(page)
    assert onglets(page, tmp_path, OUI, "avec.xlsx") == ["WACC", "Sociétés"]
    assert page.is_hidden(FOND)


def test_non_livre_le_seul_onglet_de_calcul(page, tmp_path):
    ouvrir(page)
    assert onglets(page, tmp_path, NON, "sans.xlsx") == ["WACC"]
    assert page.is_hidden(FOND)


def test_annuler_ne_telecharge_rien(page):
    ouvrir(page)
    telechargements = []
    page.on("download", lambda d: telechargements.append(d))
    page.click(ANNULER)
    page.wait_for_timeout(400)
    assert page.is_hidden(FOND)
    assert not telechargements, "« Annuler l'export » a tout de même livré un fichier"


def test_le_fond_ferme_mais_pas_la_boite(page):
    """Sans arrêter la propagation, tout clic sur un bouton remonterait au fond
    et annulerait l'export qu'on vient de demander."""
    ouvrir(page)
    page.click(".export-boite", position={"x": 8, "y": 8})
    assert page.is_visible(FOND)
    page.mouse.click(12, 12)
    assert page.is_hidden(FOND)


def test_echap_ferme_la_boite(page):
    ouvrir(page)
    page.keyboard.press("Escape")
    assert page.is_hidden(FOND)


# ------------------------------------------------------- quand la question ne se pose pas

def test_sous_damodaran_le_telechargement_part_directement(page, tmp_path):
    """Ce référentiel lit des tables sectorielles, pas des sociétés : il n'y a
    aucune feuille à joindre, donc rien à demander."""
    with page.expect_download() as attente:
        page.click(FLECHE)
    chemin = tmp_path / "damodaran.xlsx"
    attente.value.save_as(str(chemin))
    assert page.is_hidden(FOND)
    assert openpyxl.load_workbook(chemin).sheetnames == ["WACC"]
