"""Le bouton flèche : le calcul rendu dans le gabarit d'origine.

Le classeur est écrit dans le navigateur, la page étant servie en statique.
Deux choses doivent tenir : que le fichier s'ouvre vraiment — un .xlsx est une
archive, et une archive mal formée ne se voit qu'à l'ouverture — et qu'il porte
les mêmes nombres que l'écran. Un export qui dérive de la page est pire qu'une
absence d'export : il fait autorité par écrit.

Les tests cliquent donc le bouton et relisent le fichier reçu, plutôt que
d'appeler les fonctions d'export directement.
"""

import pytest

from conftest import choisir, ligne_resultat, mode_comparables, nombre_fr

openpyxl = pytest.importorskip("openpyxl")

BOUTON = "#telecharger"

# Les lignes du gabarit, à leur place d'origine dans le fichier de départ.
KE, KD, CMPC, CMPC_LOCAL = 12, 18, 23, 30
BETA_U, GEARING, SPREAD, POIDS_DETTE = 6, 8, 16, 22
SYNTHESE, RETENU = 34, 35
VALEUR, COMMENTAIRE = 3, 5


def classeur(page, tmp_path, nom="export.xlsx"):
    """Clique le bouton et rend le classeur reçu, formules et valeurs."""
    with page.expect_download() as attente:
        page.click(BOUTON)
    chemin = tmp_path / nom
    attente.value.save_as(str(chemin))
    formules = openpyxl.load_workbook(chemin)
    valeurs = openpyxl.load_workbook(chemin, data_only=True)
    return attente.value.suggested_filename, formules.active, valeurs.active


def pct(feuille, ligne):
    """Valeur en pourcentage arrondie comme la page l'affiche."""
    return round(feuille.cell(row=ligne, column=VALEUR).value * 100, 2)


def commentaire(feuille, ligne):
    return feuille.cell(row=ligne, column=COMMENTAIRE).value or ""


# ------------------------------------------------------------------ le fichier

def test_le_bouton_livre_un_classeur_lisible(page, tmp_path):
    nom, feuille, _ = classeur(page, tmp_path)
    assert nom.startswith("CMPC_") and nom.endswith(".xlsx")
    assert feuille.title == "WACC"
    assert feuille["A1"].value == "COÛT DES FONDS PROPRES (Ke) EN USD"


def test_le_gabarit_est_respecte(page, tmp_path):
    """Mêmes libellés aux mêmes lignes : les formules y renvoient."""
    _, feuille, _ = classeur(page, tmp_path)
    attendus = {
        3: "Taux sans risque US (Rf)",
        5: "Taux sans risque local (Rf + CRP)",
        9: "Beta endetté (βL) = βu × [1 + (1−t) × D/E]",
        KE: "Coût des fonds propres Ke = Rf_local + βL × ERP + Prime taille",
        KD: "Coût de la dette après IS Kd = Kd_pre × (1 − t)",
        CMPC: "WACC monnaie taux sans risque = (E/V) × Ke + (D/V) × Kd",
        RETENU: "WACC en monnaie locale (retenu pour DCF)",
    }
    for ligne, libelle in attendus.items():
        assert feuille.cell(row=ligne, column=1).value == libelle, f"ligne {ligne}"
    assert [str(r) for r in feuille.merged_cells.ranges].count("A1:E1") == 1


def test_les_cellules_calculees_gardent_leur_formule(page, tmp_path):
    """Un classeur de valeurs figées ne se tire pas : on veut un modèle."""
    _, feuille, _ = classeur(page, tmp_path)
    formule = lambda ligne: feuille.cell(row=ligne, column=VALEUR).value
    assert formule(5) == "=C3+C4"
    assert formule(9) == "=C6*(1+(1-C7)*C8)"
    assert formule(KE) == "=C5+C9*C10+C11"
    assert formule(CMPC) == "=C21*C12+C22*C18"
    assert formule(CMPC_LOCAL) == "=(1+C23)*(1+C28)/(1+C27)-1"
    assert formule(RETENU) == "=C30"


# ---------------------------------------------------- l'écran et le fichier
# Les valeurs sont écrites en cache à côté des formules : sans elles, un
# tableur qui ne recalcule pas afficherait un classeur vide.

def test_le_classeur_porte_les_chiffres_de_la_page(page, tmp_path):
    """Sous Damodaran, l'encadré met en avant le CMPC en dollar et donne le
    CMPC local en ligne ; les deux doivent se retrouver à leurs lignes."""
    _, _, valeurs = classeur(page, tmp_path)
    assert pct(valeurs, KE) == nombre_fr(ligne_resultat(page, "Ke, capitaux propres"))
    assert pct(valeurs, KD) == nombre_fr(ligne_resultat(page, "Kd, dette après impôt"))
    assert pct(valeurs, CMPC) == nombre_fr(page.inner_text("#paramsResult .result-hero-value"))
    assert pct(valeurs, CMPC_LOCAL) == nombre_fr(ligne_resultat(page, "CMPC monnaie locale"))
    assert pct(valeurs, SYNTHESE) == pct(valeurs, CMPC)
    assert pct(valeurs, RETENU) == pct(valeurs, CMPC_LOCAL)


def test_le_classeur_suit_les_comparables(page, tmp_path):
    mode_comparables(page)
    choisir(page, "secteur", "Banks")
    _, feuille, valeurs = classeur(page, tmp_path, "comparables.xlsx")

    assert pct(valeurs, KE) == nombre_fr(ligne_resultat(page, "Coût des fonds propres"))
    assert pct(valeurs, KD) == nombre_fr(ligne_resultat(page, "Coût de la dette après IS"))
    assert pct(valeurs, RETENU) == nombre_fr(page.inner_text("#paramsResult .result-hero-value"))
    # Le bêta vient des sociétés cotées, et le commentaire dit lesquelles.
    assert "bêtas cotés à trois ans" in commentaire(feuille, BETA_U)
    # La dette est levée au taux souverain : le spread est nul, et la colonne
    # des commentaires le dit plutôt que de laisser croire à une donnée absente.
    assert feuille.cell(row=SPREAD, column=VALEUR).value == 0
    assert "taux souverain" in commentaire(feuille, SPREAD)


def test_le_gearing_cible_passe_dans_le_classeur(page, tmp_path):
    """Ce que le cadenas déplace à l'écran doit se retrouver dans le fichier."""
    mode_comparables(page)
    choisir(page, "secteur", "Banks")
    page.click("#paramsResult #verrouGearing")
    page.fill("#paramsResult #champGearingCible", "60")
    page.dispatch_event("#paramsResult #champGearingCible", "change")

    _, feuille, valeurs = classeur(page, tmp_path, "cible.xlsx")
    assert round(valeurs.cell(row=POIDS_DETTE, column=VALEUR).value, 2) == 0.60
    assert "Gearing cible" in commentaire(feuille, GEARING)
    assert pct(valeurs, RETENU) == nombre_fr(page.inner_text("#paramsResult .result-hero-value"))
