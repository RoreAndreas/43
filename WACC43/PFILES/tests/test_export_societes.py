"""Le second onglet du classeur : les comparables qui produisent la médiane.

Un CMPC par comparables ne se relit pas sans son échantillon. Le classeur
exporté porte donc, à côté de la feuille de calcul, la liste des sociétés
retenues : ce que le coût du capital leur emprunte — bêta et levier — et les
agrégats d'exploitation dont se déduisent les multiples d'EBITDA, qui servent
la valorisation sans entrer dans le taux.

Deux choses doivent tenir. Que la feuille décrive exactement la population que
l'écran marque comme retenue : deux listes qui divergent feraient dire au
fichier autre chose qu'à la page. Et que les médianes y soient des formules sur
la plage juste au-dessus, pour que retirer une société fasse bouger le bêta au
lieu de laisser un nombre figé qui ne correspond plus à rien.
"""

import pytest

from conftest import (choisir, ligne_resultat, mode_comparables, nombre_fr,
                      recevoir_classeur)

openpyxl = pytest.importorskip("openpyxl")

BOUTON = "#telecharger"
SECTEUR = "Telecommunication Services"

# La feuille Sociétés, colonne par colonne.
NOM, TICKER, PLACE, PAYS = 1, 2, 3, 4
CAPI, DETTE, DE, BETA1, BETA3 = 5, 6, 7, 8, 9
CA, EBITDA, MARGE, VE, MULTIPLE = 10, 11, 12, 13, 14
PREMIERE = 5

# Le bloc de report réutilise la grille : le libellé court sur A:D, la valeur
# tient en E, le commentaire sur F:N.
VALEUR_REPORT, COMMENTAIRE_REPORT = 5, 6


def telecharger(page, tmp_path, nom="export.xlsx"):
    """Clique le bouton et rend le classeur reçu, formules et valeurs."""
    chemin = tmp_path / nom
    recevoir_classeur(page, chemin)
    return (openpyxl.load_workbook(chemin),
            openpyxl.load_workbook(chemin, data_only=True))


def cadrer(page):
    """Un secteur peuplé, où toutes les sociétés publient un EBITDA."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", SECTEUR)


def feuille(page, tmp_path):
    formules, valeurs = telecharger(page, tmp_path)
    return formules["Sociétés"], valeurs["Sociétés"]


def societes(f):
    """Les lignes de sociétés, jusqu'à la ligne des médianes exclue."""
    lignes = []
    ligne = PREMIERE
    while f.cell(row=ligne, column=NOM).value and not str(
            f.cell(row=ligne, column=NOM).value).startswith("Médiane"):
        lignes.append(ligne)
        ligne += 1
    return lignes


def ligne_mediane(f):
    return societes(f)[-1] + 1


def ligne_report(f, debut):
    """Le numéro de ligne du bloc de report, cherché par son libellé."""
    for ligne in range(ligne_mediane(f), f.max_row + 1):
        libelle = f.cell(row=ligne, column=NOM).value
        if libelle and str(libelle).startswith(debut):
            return ligne
    raise AssertionError(f"ligne de report « {debut} » absente")


def report(f, debut):
    return f.cell(row=ligne_report(f, debut), column=VALEUR_REPORT).value


# ------------------------------------------------------------------ l'onglet

def test_le_classeur_porte_les_deux_feuilles(page, tmp_path):
    cadrer(page)
    formules, _ = telecharger(page, tmp_path)
    assert formules.sheetnames == ["WACC", "Sociétés"]


def test_pas_de_feuille_societes_sous_damodaran(page, tmp_path):
    """Ce référentiel lit des tables sectorielles, pas des sociétés : joindre
    une liste de comparables donnerait à lire des chiffres qui n'entrent pas
    dans ce calcul-là."""
    formules, _ = telecharger(page, tmp_path)
    assert formules.sheetnames == ["WACC"]


def test_l_entete_annonce_le_secteur_et_le_perimetre(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    assert f["A1"].value.startswith("COMPARABLES DU SECTEUR")
    assert SECTEUR in f["A1"].value
    assert "Afrique" in f["A1"].value


# ------------------------------------------------------------ la population

def test_la_feuille_liste_les_societes_retenues(page, tmp_path):
    """Exactement celles que l'onglet Sociétés marque comme alimentant la
    médiane : le fichier et l'écran ne peuvent pas décrire deux populations."""
    cadrer(page)
    attendu = nombre_fr(ligne_resultat(page, "Sociétés du secteur"))
    f, _ = feuille(page, tmp_path)
    assert len(societes(f)) == attendu


def test_orange_ci_et_sonatel_figurent_ensemble(page, tmp_path):
    """Le cas qui a motivé la fusion des deux intitulés télécoms : les deux
    filiales du même groupe doivent se lire dans le même échantillon."""
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    noms = [f.cell(row=l, column=NOM).value for l in societes(f)]
    assert "Orange CI" in noms and "Sonatel SA" in noms


def test_chaque_societe_porte_son_identite(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    for ligne in societes(f):
        for colonne in (NOM, TICKER, PLACE, PAYS):
            assert f.cell(row=ligne, column=colonne).value


def test_les_chiffres_sont_ceux_du_jeu_de_donnees(page, tmp_path, donnees):
    """Capitalisation et dette viennent de l'export S&P, pas d'un recalcul."""
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    source = {s["nom"]: s
              for s in (donnees["comparables"]["societes"]).values()}
    for ligne in societes(f):
        s = source[f.cell(row=ligne, column=NOM).value]
        assert f.cell(row=ligne, column=CAPI).value == pytest.approx(s["capitalisation"])
        assert f.cell(row=ligne, column=DETTE).value == pytest.approx(s["dette"])
        assert f.cell(row=ligne, column=BETA3).value == pytest.approx(s["beta_3ans"])


def test_les_societes_sont_classees_par_taille(page, tmp_path):
    """Même ordre que l'onglet Sociétés — les plus grosses capitalisations
    d'abord, puisque ce sont elles qui portent le secteur."""
    cadrer(page)
    _, v = feuille(page, tmp_path)
    tailles = [v.cell(row=l, column=CAPI).value for l in societes(v)]
    assert tailles == sorted(tailles, reverse=True)


# -------------------------------------------------------- les comparables EBITDA

def test_le_multiple_d_ebitda_est_une_formule(page, tmp_path):
    """VE et VE/EBITDA se recalculent : le classeur reste un modèle qu'on peut
    tirer, pas une photographie."""
    cadrer(page)
    f, v = feuille(page, tmp_path)
    ligne = societes(f)[0]
    assert f.cell(row=ligne, column=VE).value == f"=E{ligne}+F{ligne}"
    assert f.cell(row=ligne, column=MULTIPLE).value == f"=M{ligne}/K{ligne}"
    assert f.cell(row=ligne, column=MARGE).value == f"=K{ligne}/J{ligne}"


def test_le_multiple_vaut_bien_ve_sur_ebitda(page, tmp_path):
    """Les valeurs en cache — ce qu'affichent les tableurs qui ne recalculent
    pas — doivent dire la même chose que les formules."""
    cadrer(page)
    _, v = feuille(page, tmp_path)
    for ligne in societes(v):
        ebitda = v.cell(row=ligne, column=EBITDA).value
        if not ebitda or ebitda <= 0:
            continue
        capi = v.cell(row=ligne, column=CAPI).value
        dette = v.cell(row=ligne, column=DETTE).value
        assert v.cell(row=ligne, column=VE).value == pytest.approx(capi + dette)
        assert v.cell(row=ligne, column=MULTIPLE).value == pytest.approx(
            (capi + dette) / ebitda, rel=1e-9)


def test_sans_ebitda_publie_les_colonnes_restent_vides(page, tmp_path):
    """S&P n'en publie pas pour les banques ni les assureurs : la notion n'a
    pas de sens pour elles, et un zéro s'y lirait comme une donnée."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Banks")
    f, v = feuille(page, tmp_path)
    sans = [l for l in societes(v) if v.cell(row=l, column=EBITDA).value is None]
    if not sans:
        pytest.skip("toutes les banques du périmètre publient un EBITDA")
    for ligne in sans:
        assert v.cell(row=ligne, column=MARGE).value is None
        assert v.cell(row=ligne, column=MULTIPLE).value is None
        assert f.cell(row=ligne, column=MULTIPLE).value is None


# ------------------------------------------------------------- les médianes

def test_la_mediane_est_une_formule_sur_la_plage(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    lignes = societes(f)
    m = ligne_mediane(f)
    attendu = f"=MEDIAN(I{lignes[0]}:I{lignes[-1]})"
    assert f.cell(row=m, column=BETA3).value == attendu
    assert f.cell(row=m, column=MULTIPLE).value == f"=MEDIAN(N{lignes[0]}:N{lignes[-1]})"


def test_la_mediane_du_beta_est_celle_du_cmpc(page, tmp_path):
    """La feuille et l'encadré doivent porter le même bêta : c'est le même
    échantillon, calculé par la même règle."""
    cadrer(page)
    affiche = nombre_fr(ligne_resultat(page, "Bêta médian (3 ans)"))
    _, v = feuille(page, tmp_path)
    assert round(v.cell(row=ligne_mediane(v), column=BETA3).value, 3) == affiche


# ------------------------------------------------- le report vers la feuille WACC

def test_le_report_reprend_la_ligne_des_medianes(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    m = ligne_mediane(f)
    assert report(f, "Bêta (3 ans) médian") == f"=I{m}"
    assert report(f, "Gearing médian") == f"=G{m}"
    assert report(f, "VE / EBITDA médian") == f"=N{m}"


def test_le_beta_desendette_est_celui_de_la_feuille_wacc(page, tmp_path):
    """C'est la valeur qui part en WACC!C6 : si les deux feuilles divergent,
    le classeur documente un calcul qu'il ne fait pas."""
    cadrer(page)
    formules, valeurs = telecharger(page, tmp_path)
    assert report(valeurs["Sociétés"], "Bêta désendetté") == pytest.approx(
        valeurs["WACC"]["C6"].value, rel=1e-3)
    # La formule va chercher le taux d'IS sur l'autre feuille plutôt que d'en
    # recopier le nombre : les deux onglets restent liés si on le change.
    assert "WACC!C7" in report(formules["Sociétés"], "Bêta désendetté")


def test_le_gearing_retenu_est_celui_de_la_feuille_wacc(page, tmp_path):
    cadrer(page)
    _, valeurs = telecharger(page, tmp_path)
    retenu = report(valeurs["Sociétés"], "Gearing retenu")
    assert retenu == pytest.approx(valeurs["WACC"]["C8"].value, rel=1e-3)


def test_un_gearing_cible_remplace_la_mediane_dans_le_report(page, tmp_path):
    """Cible saisie : le report n'est plus la médiane de l'échantillon, et le
    commentaire doit le dire — sans quoi on croirait lire le levier observé."""
    cadrer(page)
    page.click("#paramsResult #verrouGearing")
    page.fill("#paramsResult #champGearingCible", "40")
    page.dispatch_event("#paramsResult #champGearingCible", "change")

    formules, valeurs = telecharger(page, tmp_path, "cible.xlsx")
    soc = formules["Sociétés"]
    ligne = ligne_report(soc, "Gearing retenu")
    assert "cible" in soc.cell(row=ligne, column=COMMENTAIRE_REPORT).value
    assert valeurs["Sociétés"].cell(row=ligne, column=VALEUR_REPORT).value == pytest.approx(
        valeurs["WACC"]["C8"].value, rel=1e-3)
