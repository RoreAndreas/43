"""Vue États financiers : balance générale comparée → SYSCOHADA.

La balance d'essai est fictive et construite pour que les attendus se lisent
à la main : chiffre d'affaires de 120, 132 puis 145,2 M FCFA (+10 % par an),
charges fixes en proportion, et une banque qui équilibre chaque exercice.
L'export est relu par openpyxl : formules présentes, valeurs en cache
cohérentes avec l'écran.
"""

import openpyxl
import pytest

from conftest import mode_comparables

ONGLET = '.tabs button[data-tab="valorisation"]'
ANNEES = [2023, 2024, 2025]
CROISSANCE = [1.0, 1.1, 1.21]

# Soldes signés, en FCFA : débit positif, crédit négatif. La banque équilibre.
COMPTES = [
    ("101000", "Capital social", [-10e6] * 3),
    ("121000", "Report à nouveau", [-2e6] * 3),
    ("162000", "Emprunts bancaires", [-5e6] * 3),
    ("244100", "Matériel de bureau", [8e6] * 3),
    ("284400", "Amortissements du matériel", [-3e6] * 3),
    ("311000", "Marchandises", [4e6] * 3),
    ("401100", "Fournisseurs", [-12e6] * 3),
    ("411100", "Clients", [25e6] * 3),
    ("441000", "État, impôt sur les bénéfices", [-1e6] * 3),
    ("701100", "Ventes de marchandises", [-100e6 * c for c in CROISSANCE]),
    ("706100", "Services vendus", [-20e6 * c for c in CROISSANCE]),
    ("601100", "Achats de marchandises", [60e6 * c for c in CROISSANCE]),
    ("622100", "Locations", [5e6] * 3),
    ("661100", "Salaires", [15e6] * 3),
    ("681300", "Dotations aux amortissements", [3e6] * 3),
    ("671200", "Intérêts des emprunts", [1e6] * 3),
    ("891100", "Impôt sur les bénéfices", [4e6] * 3),
]
CA = [120e6 * c for c in CROISSANCE]
EBITDA = [120e6 * c - 60e6 * c - 5e6 - 15e6 for c in CROISSANCE]
EBIT = [e - 3e6 for e in EBITDA]
RN = [e - 1e6 - 4e6 for e in EBIT]


def balance(chemin, *, comptes=COMPTES, equilibrer=True, sous_total=False, credit_positif=False):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance"
    ws.append(["Balance générale comparée — société fictive"])
    ws.append(["N° compte", "Intitulé"] + [f"FY{str(a)[2:]}" for a in ANNEES])
    lignes = [list(c) for c in comptes]
    if equilibrer:
        banque = [-sum(c[2][t] for c in lignes) for t in range(3)]
        lignes.append(("521000", "Banque", banque))
    if sous_total:
        lignes.append(("70", "Total ventes", [sum(c[2][t] for c in lignes if c[0].startswith("70")) for t in range(3)]))
    for nc, lb, v in lignes:
        ws.append([nc, lb] + [(-x if credit_positif else x) for x in v])
    ws.append(["", "Total"] + [0, 0, 0])
    wb.save(chemin)
    return chemin


def importer_balance(page, chemin):
    page.click(ONGLET)
    page.click('.valo-vues button[data-vue="etats"]')
    page.set_input_files("#valoBgFichier", str(chemin))
    page.wait_for_selector("#valoEtats .etat-table, #valoEtats .valo-erreurs")


def montant(texte):
    t = texte.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    signe = -1 if t.startswith("(") else 1
    return signe * float(t.strip("()"))


def ligne(page, cle):
    cellules = page.query_selector_all(f'#valoEtats tr[data-ligne="{cle}"] td')
    return [c.inner_text() for c in cellules[1:]]


def test_la_vue_invite_a_importer_une_balance(page):
    page.click(ONGLET)
    page.click('.valo-vues button[data-vue="etats"]')
    assert page.is_visible('#valoEtats [data-action="importer-bg"]')
    assert page.is_visible('#valoEtats [data-action="modele-bg"]')


def test_compte_de_resultat_et_actif_net(page, tmp_path):
    importer_balance(page, balance(tmp_path / "bg.xlsx"))
    ca = ligne(page, "ca")
    assert [montant(x) for x in ca[:3]] == [round(v / 1e6, 1) for v in CA]
    assert ca[3].replace(" ", " ") == "10,0 %"            # TCAM FY23–FY25
    assert [montant(x) for x in ligne(page, "ebitda")[:3]] == [round(v / 1e6, 1) for v in EBITDA]
    assert [montant(x) for x in ligne(page, "ebit")[:3]] == [round(v / 1e6, 1) for v in EBIT]
    assert [montant(x) for x in ligne(page, "rn")[:3]] == [round(v / 1e6, 1) for v in RN]
    # Actif net = capitaux propres, exercice par exercice.
    assert ligne(page, "actif_net") == ligne(page, "cp")
    controle = page.inner_text("#valoEtats tr.is-controle")
    assert controle.count("équilibré") == 3
    assert "Équilibrée" in page.inner_text("#valoEtats .valo-import")


def test_classement_syscohada(page):
    """Le préfixe le plus long l'emporte ; à défaut, la classe du compte."""
    page.click(ONGLET)
    attendus = {
        "701100": "ventes", "706200": "production_vendue", "605700": "autres_achats",
        "628100": "telecom", "629000": "autres_services", "787000": "produits_fin",
        "781000": "autres_produits", "797000": "produits_fin", "681300": "dotations",
        "419100": "clients_avances", "411100": "clients", "409100": "fournisseurs_avances",
        "499000": "provisions_ct", "561000": "credits_tresorerie", "521000": "disponibilites",
        "284400": "immo_corp", "297000": "immo_fin", "131000": "ria", "895000": "impot_resultat",
    }
    for nc, cle in attendus.items():
        assert page.evaluate(f"classerCompte('{nc}').cle") == cle, nc
    assert page.evaluate("classerCompte('699999').cle") == "dotations"
    assert page.evaluate("classerCompte('9100')") is None     # classe 9 : hors plan


def test_balance_desequilibree_signalee(page, tmp_path):
    importer_balance(page, balance(tmp_path / "bancale.xlsx", equilibrer=False))
    assert "Déséquilibrée" in page.inner_text("#valoEtats .valo-import")
    assert "déséquilibrée" in page.inner_text("#valoEtats .valo-remarques")
    assert page.query_selector("#valoEtats td.is-ecart") is not None


def test_sous_total_ecarte_et_signes_inverses(page, tmp_path):
    importer_balance(page, balance(tmp_path / "st.xlsx", sous_total=True, credit_positif=True))
    remarques = page.text_content("#valoEtats .valo-remarques")   # repliées : balance équilibrée
    assert "sous-total" in remarques and "70" in remarques
    assert "inversés" in remarques
    assert [montant(x) for x in ligne(page, "ca")[:3]] == [round(v / 1e6, 1) for v in CA]


def test_graphique_historique_et_previsionnel(page, tmp_path):
    """Historique de la balance, prévisionnel du classeur DCF : barres pleines
    puis hachurées, et le TCAM tiré depuis le dernier exercice historique."""
    from test_valorisation import classeur
    importer_balance(page, balance(tmp_path / "bg.xlsx"))
    page.click('.valo-vues button[data-vue="dcf"]')
    page.set_input_files("#valoFichier", str(classeur(tmp_path / "dcf.xlsx", ca=[150000, 160000, 170000, 180000])))
    page.wait_for_selector('#valoDcf [data-o="ve"]')
    page.click('.valo-vues button[data-vue="etats"]')
    page.wait_for_selector("#valoEtats .traj-svg")
    assert page.query_selector_all("#valoEtats .traj-an")[0].inner_html() == "FY23"
    assert len(page.query_selector_all("#valoEtats .traj-an")) == 7        # 3 historiques + 4 prévisionnels
    assert page.query_selector("#valoEtats .traj-zone") is not None
    assert len(page.query_selector_all("#valoEtats .traj-barre.is-prev")) == 8   # CA et EBITDA, 4 exercices
    # Par défaut, le dernier exercice : TCAM du CA de FY25 (145,2) à FY29 (180).
    attendu = (180000 / (CA[2] / 1e6)) ** (1 / 4) - 1
    pastilles = [t.inner_html() for t in page.query_selector_all("#valoEtats .traj-pastille text")]
    assert any(f"{attendu * 100:.1f}".replace(".", ",") in p for p in pastilles)
    assert "FY29" in page.inner_text("#valoEtats .traj-periode")
    # Survol : l'exercice lu change, la couche du dessus suit.
    cadre = page.query_selector("#valoEtats .traj-cadre").bounding_box()
    page.mouse.move(cadre["x"] + 30, cadre["y"] + 150)
    assert "FY23" in page.inner_text("#valoEtats .traj-periode")
    # Une série se masque ; la dernière reste.
    page.click('#valoEtats [data-serie="ebitda"]')
    assert len(page.query_selector_all("#valoEtats .traj-barre.is-prev")) == 4
    page.click('#valoEtats [data-serie="ca"]')
    assert page.get_attribute('#valoEtats [data-serie="ca"]', "aria-pressed") == "true"


def test_export_au_format_du_modele(page, tmp_path):
    importer_balance(page, balance(tmp_path / "bg.xlsx"))
    with page.expect_download() as dl:
        page.click('#valoEtats [data-action="exporter-etats"]')
    chemin = tmp_path / "etats.xlsx"
    dl.value.save_as(chemin)
    wb = openpyxl.load_workbook(chemin)
    assert wb.sheetnames == ["BG COMP", "Cdr", "Bilan", "Plan SYSCOHADA"]
    bg = wb["BG COMP"]
    assert [c.value for c in bg[1][:7]] == ["Mapping", "C1", "C2", "C3", "C4", "NC", "LB"]
    assert bg["B2"].value == "=LEFT($F2,1)"
    cdr = wb["Cdr"]
    formules = [c.value for row in cdr.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith("=") and "SUMIF" in c.value]
    assert formules and all("'BG COMP'!$A:$A" in f for f in formules)
    # Valeurs en cache : les mêmes que l'écran.
    wv = openpyxl.load_workbook(chemin, data_only=True)
    lib = {wv["Cdr"].cell(r, 2).value: r for r in range(1, wv["Cdr"].max_row + 1)}
    assert [wv["Cdr"].cell(lib["Chiffre d'affaires"], c).value for c in (3, 4, 5)] == pytest.approx(CA)
    assert [wv["Cdr"].cell(lib["Résultat net"], c).value for c in (3, 4, 5)] == pytest.approx(RN)
    blib = {wv["Bilan"].cell(r, 2).value: r for r in range(1, wv["Bilan"].max_row + 1)}
    controle = blib["Contrôle : actif net − capitaux propres"]
    assert [wv["Bilan"].cell(controle, c).value for c in (3, 4, 5)] == pytest.approx([0, 0, 0], abs=1e-9)
    assert wb["Bilan"].cell(blib["Résultat net de l'exercice"], 3).value.startswith("=Cdr!")


def test_modele_de_balance_se_reimporte(page, tmp_path):
    page.click(ONGLET)
    page.click('.valo-vues button[data-vue="etats"]')
    with page.expect_download() as dl:
        page.click('#valoEtats [data-action="modele-bg"]')
    chemin = tmp_path / "modele.xlsx"
    dl.value.save_as(chemin)
    wb = openpyxl.load_workbook(chemin)
    ws = wb["Balance"]
    assert ws["A1"].value == "N° compte"
    for i, (nc, lb, v) in enumerate(COMPTES + [("521000", "Banque", [-sum(c[2][t] for c in COMPTES) for t in range(3)])]):
        ws.append([nc, lb] + v)
    wb.save(chemin)
    page.set_input_files("#valoBgFichier", str(chemin))
    page.wait_for_selector("#valoEtats .etat-table")
    assert page.inner_text("#valoEtats tr.is-controle").count("équilibré") == 3


def test_l_ebitda_des_comparables_vient_de_la_balance(page, tmp_path):
    """La balance est la source comptable : son dernier EBITDA sert aux
    comparables, même sans partie historique dans le classeur."""
    mode_comparables(page)
    secteurs = page.evaluate("(DATA.comparables.industries || []).map(i => i.nom)")
    med = None
    for nom in secteurs:
        page.select_option('#paramsMain select[data-param="secteur"]', nom)
        if page.evaluate("multipleComparables()"):
            med = page.evaluate("multipleComparables().med")
            break
    if med is None:
        pytest.skip("aucun secteur avec multiple VE / EBITDA")
    importer_balance(page, balance(tmp_path / "bg.xlsx"))
    page.click('.valo-vues button[data-vue="comparables"]')
    ve = montant(page.inner_text('#valoCompVe [data-o="comp-ve"]'))
    assert abs(ve - EBITDA[2] / 1e6 * med) < 1
    assert "balance générale" in page.inner_text("#valoCompVe")


def test_le_graphique_suit_la_largeur_de_la_fenetre(page, tmp_path):
    """Dessiné sur ordinateur puis rétréci : le SVG se redessine à la largeur
    du téléphone au lieu d'élargir la page."""
    importer_balance(page, balance(tmp_path / "bg.xlsx"))
    page.wait_for_selector("#valoEtats .traj-svg")
    page.set_viewport_size({"width": 390, "height": 900})
    page.wait_for_function("document.documentElement.scrollWidth <= 390")
    largeur = page.eval_on_selector("#valoEtats .traj-svg", "e => e.getBoundingClientRect().width")
    assert largeur <= 390
