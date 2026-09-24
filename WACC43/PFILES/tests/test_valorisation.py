"""Onglet Valorisation : DCF et multiples réunis.

Le DCF de référence est celui de la note de valorisation qui a servi de
modèle : quatre exercices, CMPC 12,02 %, g 2 %, flux en milieu d'année. Ses
totaux — 164 452 de flux actualisés, 574 888 de valeur terminale actualisée,
739 340 de VE — sont recalculés ici en Python plutôt que recopiés, et comparés
à l'écran.
"""

from conftest import mode_comparables

ONGLET = '.tabs button[data-tab="valorisation"]'

EBIT = [54463, 63821, 76624, 106636]
DA = [63230, 80311, 100131, 82320]
CAPEX = [86641, 79152, 77427, 77427]
BFR = [-2723, -4404, -5212, -850]
DETTE_NETTE = 129455


def ve_attendue(wacc: float, g: float, impot: float = 0.25) -> float:
    fcff = [e - max(0, e) * impot + d - c + b for e, d, c, b in zip(EBIT, DA, CAPEX, BFR)]
    facteurs = [(1 + wacc) ** -(t + 0.5) for t in range(len(fcff))]
    somme = sum(f * a for f, a in zip(fcff, facteurs))
    vt = fcff[-1] * (1 + g) / (wacc - g)
    return somme + vt * facteurs[-1]


def montant(texte: str) -> float:
    t = texte.strip().replace(" ", "").replace(" ", "")
    signe = -1 if t.startswith("(") else 1
    return signe * float(t.strip("()"))


def cellule(page, cle: str) -> str:
    return page.inner_text(f'#valoDcf [data-o="{cle}"]')


def poser_cmpc(page, valeur: str) -> None:
    page.click('#valoDcf [data-verrou="wacc"]')
    champ = page.locator('#valoDcf input[data-pct="wacc"]')
    champ.fill(valeur)


def poser_impot(page, valeur: str) -> None:
    page.click('#valoDcf [data-verrou="impot"]')
    page.locator('#valoDcf input[data-pct="impot"]').fill(valeur)


def test_l_onglet_existe_sans_referentiel_comparables(page):
    """Le DCF ne dépend pas de l'échantillon : l'onglet reste visible en
    Damodaran, et la vue Comparables y explique ce qui lui manque."""
    assert page.is_visible(ONGLET)
    assert page.query_selector('.tabs button[data-tab="comparables"]') is None
    page.click(ONGLET)
    assert page.is_visible("#valoDcf .dcf-table")
    page.click('.valo-vues button[data-vue="comparables"]')
    assert page.is_visible("#comparablesAbsents")
    assert page.is_hidden("#valoDcf")


def test_le_dcf_retrouve_la_note_de_reference(page):
    page.click(ONGLET)
    poser_cmpc(page, "12,02")
    poser_impot(page, "25")
    ve = montant(cellule(page, "ve"))
    assert abs(ve - ve_attendue(0.1202, 0.02)) < 1
    # Les totaux de la note, à l'arrondi de ses propres entrées près.
    assert abs(ve - 739340) < 60
    assert abs(montant(cellule(page, "somme")) - 164452) < 10
    assert abs(montant(cellule(page, "vtact")) - 574888) < 60
    # 14 713,25 : la note affiche 14 714 parce que ses lignes sont arrondies
    # avant d'être additionnées.
    assert cellule(page, "fcff-0") == "14 713"
    assert cellule(page, "impot-0") == "(13 616)"
    assert cellule(page, "tcam").replace(" ", " ") == "25,1 %"


def test_sensibilite_et_passage_a_la_vfp_concordent(page):
    """Le centre de la grille est la VE du tableau ; les trois colonnes du
    passage à la VFP sont les trois cases marquées de la grille."""
    page.click(ONGLET)
    poser_cmpc(page, "12,02")
    poser_impot(page, "25")
    ve = cellule(page, "ve")
    cles = [c.inner_text() for c in page.query_selector_all("#valoDcf .sens-table td.is-cle")]
    assert len(cles) == 3 and ve in cles
    lignes = page.query_selector_all("#valoDcf .pont-table tbody tr")
    ves = [montant(td.inner_text()) for td in lignes[0].query_selector_all("td")[1:]]
    vfps = [montant(td.inner_text()) for td in lignes[2].query_selector_all("td")[1:]]
    assert ves[1] == montant(ve)
    assert sorted(ves) == ves, "Min ≤ Méd ≤ Max"
    assert sorted(montant(c) for c in cles) == ves
    for v, f in zip(ves, vfps):
        assert abs(v - DETTE_NETTE - f) <= 1
    assert abs(ves[0] - ve_attendue(0.1302, 0.017)) < 1
    assert abs(ves[2] - ve_attendue(0.1102, 0.023)) < 1


def test_une_saisie_recalcule_sans_perdre_le_champ(page):
    page.click(ONGLET)
    poser_cmpc(page, "12")
    avant = cellule(page, "ve")
    champ = page.locator('#valoDcf input[data-ligne="ebit"][data-i="3"]')
    champ.fill("120000")
    assert cellule(page, "ve") != avant
    assert page.evaluate("document.activeElement.dataset.i") == "3"
    assert page.is_hidden('#valoDcf [data-o="exemple"]')
    # À la sortie, la saisie reprend le format du tableau.
    champ.press("Tab")
    assert champ.input_value() == "120 000"


def test_le_cmpc_auto_suit_l_onglet_cmpc(page):
    """Cadenas fermé, le DCF prend le CMPC en monnaie locale affiché dans
    l'onglet Paramètres ; l'ouvrir puis le refermer y revient."""
    mode_comparables(page)
    attendu = page.inner_text("#paramsResult .result-hero-value")
    page.click(ONGLET)
    assert cellule(page, "wacc-auto") == attendu
    poser_cmpc(page, "15")
    assert page.query_selector('#valoDcf [data-o="wacc-auto"]') is None
    page.click('#valoDcf [data-verrou="wacc"]')
    assert cellule(page, "wacc-auto") == attendu


def test_cmpc_inferieur_a_g_est_signale(page):
    page.click(ONGLET)
    poser_cmpc(page, "1,5")
    assert page.is_visible('#valoDcf [data-o="alerte"]')
    assert cellule(page, "ve") == "—"


def test_ajouter_un_exercice(page):
    page.click(ONGLET)
    page.click('#valoDcf [data-annees="1"]')
    entetes = [th.inner_text() for th in page.query_selector_all("#valoDcf .dcf-table thead th")]
    assert entetes[1:6] == ["FY26", "FY27", "FY28", "FY29", "FY30"]
    assert entetes[6] == "TCAM 26-30"


def test_la_vue_comparables_montre_les_multiples(page):
    mode_comparables(page)
    page.click(ONGLET)
    page.click('.valo-vues button[data-vue="comparables"]')
    assert page.is_hidden("#comparablesAbsents")
    assert "VE / EBITDA" in page.inner_text("#comparablesMain")
