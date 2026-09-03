"""La feuille « Sociétés » du classeur, au gabarit posé à la main dans WACC43.

Un CMPC par comparables ne se relit pas sans son échantillon. Le classeur porte
donc, à côté de la feuille de calcul, la liste des sociétés retenues : ce que le
coût du capital leur emprunte — bêta et levier — et les agrégats d'exploitation
dont se déduisent les multiples d'EBITDA, qui servent la valorisation sans
entrer dans le taux.

La mise en page n'est pas un choix refait ici : elle vient du fichier
`CMPC_Telecommunication_Services_Côte d'Ivoire_2026 (version 1).xlsx` déposé
dans WACC43, où elle a été arrêtée à la main. Gouttière en colonne A, tableau de
B à O, bandeau de titre, quatre statistiques sous l'échantillon, mention de
source, bloc de paramètres, note de bas de feuille. Ces tests vérifient la
géométrie autant que les nombres : c'est le format dans lequel les notes de
valorisation sont relues, et un décalage d'une colonne suffit à le rompre.

Trois choses doivent tenir. Que la feuille décrive exactement la population que
l'écran marque comme retenue. Que les statistiques soient des formules sur la
plage juste au-dessus, pour que retirer une société les fasse bouger. Et que les
colonnes d'EBITDA suivent la quantité d'information : S&P n'en publie ni pour
les banques ni pour les assureurs.
"""

import pytest

from conftest import (choisir, ligne_resultat, mode_comparables, nombre_fr,
                      recevoir_classeur)

openpyxl = pytest.importorskip("openpyxl")

SECTEUR = "Telecommunication Services"

# Le gabarit : colonne A en gouttière, tableau de B à O.
NOM, TICKER, PLACE, PAYS = 2, 3, 4, 5
CAPI, DETTE, DE, BETA1, BETA3 = 6, 7, 8, 9, 10
CA, EBITDA, MARGE, VE, MULTIPLE = 11, 12, 13, 14, 15
TITRE, ENTETES, PREMIERE = 2, 3, 4
STATS = ("Min", "Moy", "Médiane", "Max")


def telecharger(page, tmp_path, nom="export.xlsx"):
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
    """Les lignes de sociétés, jusqu'à la première statistique exclue."""
    lignes, ligne = [], PREMIERE
    while True:
        nom = f.cell(row=ligne, column=NOM).value
        if not nom or nom in STATS:
            return lignes
        lignes.append(ligne)
        ligne += 1


def ligne_stat(f, nom):
    debut = societes(f)[-1] + 1
    for ligne in range(debut, debut + len(STATS)):
        if f.cell(row=ligne, column=NOM).value == nom:
            return ligne
    raise AssertionError(f"statistique « {nom} » absente")


def ligne_libelle(f, libelle):
    for ligne in range(1, f.max_row + 1):
        if f.cell(row=ligne, column=NOM).value == libelle:
            return ligne
    raise AssertionError(f"ligne « {libelle} » absente")


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


# --------------------------------------------------------------- le gabarit

def test_la_gouttiere_et_les_largeurs_sont_celles_du_gabarit(page, tmp_path):
    """Relevées sur le fichier de référence, à deux exceptions près.

    Dans ce fichier les données étaient remplacées par des « xxx » : « Pays »
    y avait donc été ajusté sur son seul en-tête (5,2) et « EBITDA » laissé à
    la largeur par défaut. Ces deux nombres mesuraient du vide, pas le format —
    voir `test_aucune_colonne_ne_tronque_les_donnees`.
    """
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    largeurs = {c: round(d.width, 2) for c, d in f.column_dimensions.items() if d.width}
    assert largeurs == {
        "A": 3.0, "B": 21.5, "C": 10.0, "D": 8.0, "E": 15.5, "F": 12.7, "G": 12.5,
        "H": 14.6, "I": 9.0, "K": 15.0, "L": 15.0, "M": 11.5, "N": 14.0, "O": 11.5,
    }


def test_aucune_colonne_ne_tronque_les_donnees(page, tmp_path):
    """Le pire cas de l'univers : les opérateurs américains, dont les montants
    tiennent sur dix chiffres et les pays sur quatorze lettres. Aux largeurs du
    fichier de référence, la colonne EBITDA rendait ######## et « United
    Kingdom » était coupé — deux colonnes qui y avaient été dimensionnées sur
    des cellules vides."""
    mode_comparables(page)
    choisir(page, "continent", "Tous")
    choisir(page, "secteur", SECTEUR)
    f, v = feuille(page, tmp_path)

    # Un nombre trop large pour sa colonne s'affiche ######## : on compare donc
    # le rendu attendu, séparateurs compris, à la largeur déclarée.
    largeurs = {c: d.width for c, d in f.column_dimensions.items() if d.width}
    for ligne in societes(v):
        for col, cle in ((CAPI, "F"), (DETTE, "G"), (CA, "K"), (EBITDA, "L"), (VE, "N")):
            valeur = v.cell(row=ligne, column=col).value
            if valeur is None:
                continue
            rendu = "{:,.0f}".format(valeur)
            assert len(rendu) <= largeurs[cle], (cle, ligne, rendu, largeurs[cle])
        pays = v.cell(row=ligne, column=PAYS).value or ""
        assert len(pays) <= largeurs["E"], (ligne, pays)


def test_le_tableau_commence_en_B(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    assert f.cell(row=TITRE, column=NOM).value == "Comparables boursiers"
    assert f.cell(row=TITRE, column=1).value is None, "la colonne A est une gouttière"
    assert f.cell(row=PREMIERE, column=1).value is None


def test_les_entetes_sont_ceux_du_gabarit(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    lus = [f.cell(row=ENTETES, column=c).value for c in range(NOM, MULTIPLE + 1)]
    assert lus[:4] == ["Société", "Ticker", "Place", "Pays"]
    assert lus[4:9] == ["Capitalisation", "Dette totale", "Dette / capi (D/E)",
                        "Bêta 1 an", "Bêta 3 ans"]
    assert lus[9].startswith("Chiffre d'affaires") and lus[10].startswith("EBITDA")
    assert lus[11] == "Marge d'EBITDA" and lus[12].startswith("VE ")
    assert lus[13] == "VE / EBITDA"
    assert f.row_dimensions[ENTETES].height == 26.0


def test_les_formats_de_nombre_sont_ceux_du_gabarit(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    ligne = societes(f)[0]
    attendus = {CAPI: "#,##0", DETTE: "#,##0", DE: "0.00", BETA1: "0.000",
                BETA3: "0.000", CA: "#,##0", EBITDA: "#,##0", MARGE: "0.0%",
                VE: "#,##0", MULTIPLE: '0.0"x"'}
    for col, fmt in attendus.items():
        assert f.cell(row=ligne, column=col).number_format == fmt, col


# ------------------------------------------------------------ la population

def test_la_feuille_liste_les_societes_retenues(page, tmp_path):
    """Exactement celles que l'onglet Sociétés marque comme alimentant la
    médiane : le fichier et l'écran ne peuvent pas décrire deux populations."""
    cadrer(page)
    attendu = nombre_fr(ligne_resultat(page, "Sociétés du secteur"))
    f, _ = feuille(page, tmp_path)
    assert len(societes(f)) == attendu


def test_orange_ci_et_sonatel_figurent_ensemble(page, tmp_path):
    """Le cas qui a motivé la fusion des deux intitulés télécoms."""
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    noms = [f.cell(row=l, column=NOM).value for l in societes(f)]
    assert "Orange CI" in noms and "Sonatel SA" in noms


def test_les_chiffres_sont_ceux_du_jeu_de_donnees(page, tmp_path, donnees):
    """Capitalisation et dette viennent de l'export S&P, pas d'un recalcul."""
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    source = {s["nom"]: s for s in donnees["comparables"]["societes"].values()}
    for ligne in societes(f):
        s = source[f.cell(row=ligne, column=NOM).value]
        assert f.cell(row=ligne, column=CAPI).value == pytest.approx(s["capitalisation"])
        assert f.cell(row=ligne, column=DETTE).value == pytest.approx(s["dette"])
        assert f.cell(row=ligne, column=BETA3).value == pytest.approx(s["beta_3ans"])


def test_les_societes_sont_classees_par_taille(page, tmp_path):
    cadrer(page)
    _, v = feuille(page, tmp_path)
    tailles = [v.cell(row=l, column=CAPI).value for l in societes(v)]
    assert tailles == sorted(tailles, reverse=True)


# -------------------------------------------------------- les multiples d'EBITDA

def test_ve_et_multiple_sont_des_formules(page, tmp_path):
    """Le classeur reste un modèle qu'on peut tirer, pas une photographie."""
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    ligne = societes(f)[0]
    assert f.cell(row=ligne, column=VE).value == f"=F{ligne}+G{ligne}"
    assert f.cell(row=ligne, column=MULTIPLE).value == f"=N{ligne}/L{ligne}"
    assert f.cell(row=ligne, column=MARGE).value == f"=L{ligne}/K{ligne}"
    assert f.cell(row=ligne, column=DE).value == f"=G{ligne}/F{ligne}"


def test_le_multiple_vaut_bien_ve_sur_ebitda(page, tmp_path):
    """Les valeurs en cache doivent dire la même chose que les formules."""
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


def test_les_colonnes_d_ebitda_disparaissent_quand_nul_ne_le_publie(page, tmp_path):
    """Un en-tête au-dessus de vingt cases vides est un cadre sans information,
    pas une donnée manquante."""
    mode_comparables(page)
    choisir(page, "continent", "Tous")
    choisir(page, "secteur", "Banks")
    f, _ = feuille(page, tmp_path)
    entetes = [f.cell(row=ENTETES, column=c).value
               for c in range(NOM, f.max_column + 1)]
    entetes = [e for e in entetes if e]
    assert not any(e.startswith("EBITDA") for e in entetes), entetes
    assert "VE / EBITDA" not in entetes
    assert "Marge d'EBITDA" not in entetes
    assert any(e.startswith("VE ") for e in entetes), "la VE ne dépend pas de l'EBITDA"


# ------------------------------------------------------------ les statistiques

@pytest.mark.parametrize("nom, fonction",
                         list(zip(STATS, ("MIN", "AVERAGE", "MEDIAN", "MAX"))))
def test_chaque_statistique_est_une_formule_sur_la_plage(page, tmp_path, nom, fonction):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    lignes = societes(f)
    ligne = ligne_stat(f, nom)
    assert f.cell(row=ligne, column=BETA3).value == \
        f"={fonction}(J{lignes[0]}:J{lignes[-1]})"


def test_les_quatre_statistiques_se_suivent_sous_l_echantillon(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    debut = societes(f)[-1] + 1
    lus = [f.cell(row=debut + i, column=NOM).value for i in range(4)]
    assert lus == list(STATS)


def test_la_mediane_du_beta_est_celle_du_cmpc(page, tmp_path):
    """La feuille et l'encadré portent le même bêta : même échantillon, même
    règle."""
    cadrer(page)
    affiche = nombre_fr(ligne_resultat(page, "Bêta médian (3 ans)"))
    f, v = feuille(page, tmp_path)
    ligne = ligne_stat(f, "Médiane")
    assert round(v.cell(row=ligne, column=BETA3).value, 3) == affiche


def test_min_et_max_encadrent_la_mediane(page, tmp_path):
    cadrer(page)
    f, v = feuille(page, tmp_path)
    lus = {nom: v.cell(row=ligne_stat(f, nom), column=MULTIPLE).value for nom in STATS}
    assert lus["Min"] <= lus["Médiane"] <= lus["Max"]
    assert lus["Min"] <= lus["Moy"] <= lus["Max"]


# ------------------------------------------------- source, paramètres et note

def test_la_source_suit_les_statistiques(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    ligne = ligne_stat(f, "Max") + 1
    assert f.cell(row=ligne, column=NOM).value == "Source: Capital IQ Pro | 43WACC"


def test_le_bloc_parametres_consigne_le_cadrage(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    debut = ligne_libelle(f, "Paramètres")
    assert f.cell(row=debut + 1, column=NOM).value == "Intitulé"
    assert f.row_dimensions[debut + 1].height == 12.0
    lus = {f.cell(row=debut + 2 + i, column=NOM).value:
           f.cell(row=debut + 2 + i, column=TICKER).value for i in range(3)}
    assert lus["Continent"] == "Afrique"
    assert lus["Industrie"] == SECTEUR
    assert "Zone" in lus


def test_la_note_ferme_la_feuille_et_court_sur_toute_sa_largeur(page, tmp_path):
    cadrer(page)
    f, _ = feuille(page, tmp_path)
    ligne = ligne_libelle(f, "Paramètres") + 6
    note = f.cell(row=ligne, column=NOM).value
    assert "EBITDA" in note
    assert f"B{ligne}:O{ligne}" in [str(m) for m in f.merged_cells.ranges]


def test_la_note_chiffre_ce_que_l_ebitda_couvre(page, tmp_path):
    """Sur les banques africaines, une seule des vingt retenues en publie : la
    note doit le dire plutôt que de laisser lire des colonnes à trous."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Banks")
    f, _ = feuille(page, tmp_path)
    note = f.cell(row=ligne_libelle(f, "Paramètres") + 6, column=NOM).value
    assert "EBITDA publié pour" in note
    assert "sociétés retenues" in note
