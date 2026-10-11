"""Règles de prévision, report déficitaire, passage VE → fonds propres, analyste.

Critères d'acceptation du brief, lot 6 :
- cinq dossiers : les règles restent dans les bornes, et les alertes de
  classement se déclenchent sur un dossier volontairement faux ;
- report déficitaire : zéro impôt tant que le stock n'est pas imputé, puis le
  taux plein ; sans `f.impots`, `calculDcf` rend exactement les chiffres
  d'avant (non-régression sur les données de test de la page) ;
- passage VE → fonds propres : un crédit-bail (17) et des titres (26) donnent
  deux lignes au bon signe, et décocher une ligne ramène la valeur des fonds
  propres à la valeur précédente.
L'analyste est joué par `page.route` : aucun modèle n'est appelé.
"""

import json

import pytest

from test_etats_financiers import COMPTES, balance, exporter, importer_balance, montant

openpyxl = pytest.importorskip("openpyxl")

BORNES = {"croissance": (-0.2, 0.3), "marge": (0, 0.6), "g": (0, 0.04),
          "capex_sur_da": (0.8, 2.5), "bfr_sur_ca": (-0.2, 0.5), "da_sur_ca": (0, 0.3)}


def sans(comptes, *numeros):
    return [c for c in comptes if c[0] not in numeros]


# Cinq dossiers : régulier, pertes reportables, exercice atypique, comptes mal
# classés, et passage VE → FP chargé.
DOSSIERS = {
    "regulier": COMPTES,
    "pertes": sans(COMPTES, "661100") + [("661100", "Salaires", [80e6, 60e6, 45e6])],
    "atypique": COMPTES + [("758000", "Produits divers", [0, 70e6, 0])],
    "faux": sans(COMPTES, "681300", "411100") + [("681300", "Dotations (au crédit)", [-3e6] * 3),
                                                  ("411100", "Clients", [150e6] * 3)],
    "passage": COMPTES + [("172000", "Crédit-bail", [-4e6] * 3), ("261000", "Titres de participation", [6e6] * 3),
                          ("194000", "Provisions pour risques", [-2e6] * 3), ("465000", "Dividendes à payer", [-1.5e6] * 3)],
}


def estimer(page, tmp_path, nom="regulier"):
    importer_balance(page, balance(tmp_path / f"{nom}.xlsx", comptes=DOSSIERS[nom]))
    page.click('#valoEtats [data-action="mode-prev"]')
    page.wait_for_selector("#valoEtats .traj-enveloppe .hyp-boulon")


def ouvrir_hypotheses(page):
    page.click("#valoEtats .traj-enveloppe .hyp-boulon")
    page.wait_for_selector("#valoEtats .hyp-panneau .hyp-onglets")


def regles(page, horizon=5):
    return page.evaluate("n => { const h = hypothesesParRegles(VALO.bg, n); return { croissance: h.croissance, marge: h.margeAn, "
                         "capex_sur_da: h.capexSurDa, g: h.g, da_sur_ca: h.da, bfr_sur_ca: h.bfr, meta: h.meta }; }", horizon)


# --------------------------------------------------------------- les règles

@pytest.mark.parametrize("nom", list(DOSSIERS))
def test_les_regles_restent_dans_les_bornes(page, tmp_path, nom):
    estimer(page, tmp_path, nom)
    r = regles(page)
    for cle in ("croissance", "marge", "capex_sur_da"):
        assert len(r[cle]) == 5, cle
        for v in r[cle]:
            assert BORNES[cle][0] - 1e-9 <= v <= BORNES[cle][1] + 1e-9, (cle, v)
    for cle in ("g", "da_sur_ca", "bfr_sur_ca"):
        assert BORNES[cle][0] - 1e-9 <= r[cle] <= BORNES[cle][1] + 1e-9, (cle, r[cle])


def test_la_croissance_part_du_tcam_et_rejoint_g(page, tmp_path):
    """Hors comparables, pas de croissance sectorielle : la cible est g."""
    estimer(page, tmp_path)
    r = regles(page)
    assert r["croissance"][0] == pytest.approx(0.1, abs=1e-4)        # TCAM 2023-2025 : +10 %
    assert r["croissance"][-1] == pytest.approx(r["g"], abs=1e-4)
    pas = [b - a for a, b in zip(r["croissance"], r["croissance"][1:])]
    assert max(pas) - min(pas) < 1e-3, "convergence linéaire"


@pytest.mark.parametrize("inflation, attendu", [(0.025, 0.025), (0.06, 0.04), (-0.01, 0.0)])
def test_g_suit_l_inflation_locale_plafonnee(page, tmp_path, inflation, attendu):
    estimer(page, tmp_path)
    page.evaluate("x => { params.inflation_local = x; }", inflation)
    assert regles(page)["g"] == pytest.approx(attendu)


def test_le_capex_suit_la_croissance(page, tmp_path):
    estimer(page, tmp_path)
    r = regles(page)
    for c, ratio in zip(r["croissance"], r["capex_sur_da"]):
        assert ratio == pytest.approx(min(2.5, max(0.8, 1 + 3 * c)), abs=1e-4)


def test_l_exercice_atypique_est_ecarte_de_la_normalisation(page, tmp_path):
    estimer(page, tmp_path, "atypique")
    meta = regles(page)["meta"]
    assert meta["normalise"]["exercices"] == [2023, 2025]
    assert any(a.startswith("FY24") for a in meta["anomalies"])


def test_un_compte_mal_classe_est_signale(page, tmp_path):
    estimer(page, tmp_path, "faux")
    alertes = " ".join(regles(page)["meta"]["alertes"])
    assert "mal classé" in alertes
    assert "classe 68" in alertes and "classe 4" in alertes


def test_un_dossier_sain_ne_declenche_aucune_alerte_de_classement(page, tmp_path):
    estimer(page, tmp_path)
    assert not any("mal classé" in a for a in regles(page)["meta"]["alertes"])


def test_en_comparables_la_marge_converge_vers_le_secteur(page, tmp_path):
    from conftest import choisir, mode_comparables
    mode_comparables(page)
    choisir(page, "secteur", "Food Products")
    estimer(page, tmp_path)
    r = regles(page)
    s = r["meta"]["secteur"]
    assert s and s["n"] > 0 and s["marge_mediane"] is not None
    m0, med = r["marge"][0], s["marge_mediane"]
    cible = med + (m0 - med) / 2 if abs(m0 - med) > 0.1 else med
    assert r["marge"][-1] == pytest.approx(min(0.6, max(0, cible)), abs=1e-3)


# ------------------------------------------------- les onglets et le DCF

def test_les_onglets_changent_le_jeu_qui_alimente_le_dcf(page, tmp_path):
    estimer(page, tmp_path)
    ouvrir_hypotheses(page)
    ve_defaut = page.evaluate("(() => { const f = fluxActif(); return calculDcf(f, cmpcAuto(), f.g, impotRetenu(f)).ve; })()")
    page.click('#valoEtats [data-action="hyp-regles"]')
    assert page.evaluate("VALO.jeu") == "regles"
    ve_regles = page.evaluate("(() => { const f = fluxActif(); return calculDcf(f, cmpcAuto(), f.g, impotRetenu(f)).ve; })()")
    assert ve_regles != pytest.approx(ve_defaut)
    # Le comparatif montre les deux jeux et leur VE.
    # En-têtes en capitales par le style : on compare sans casse.
    comparaison = page.inner_text("#valoEtats .hyp-comparaison").upper()
    assert "DÉFAUT" in comparaison and "RÈGLES" in comparaison and "VE DU DCF" in comparaison
    page.click('#valoEtats [data-action="hyp-jeu"][data-jeu="defaut"]')
    assert page.evaluate("(() => { const f = fluxActif(); return calculDcf(f, cmpcAuto(), f.g, impotRetenu(f)).ve; })()") \
        == pytest.approx(ve_defaut)


def test_l_onglet_analyste_attend_une_analyse(page, tmp_path):
    estimer(page, tmp_path)
    ouvrir_hypotheses(page)
    assert page.is_disabled('#valoEtats [data-jeu="analyste"]')


def test_la_marge_par_exercice_se_saisit(page, tmp_path):
    estimer(page, tmp_path)
    ouvrir_hypotheses(page)
    page.click('#valoEtats [data-action="hyp-regles"]')
    page.fill('#valoEtats input[data-hyp-an="marge"][data-i="0"]', "50")
    f = page.evaluate("estimerPrevisionnel()")
    assert f["ebitda"][0] == pytest.approx(f["ca"][0] * 0.5)


# ------------------------------------------------------ report déficitaire

def test_report_deficitaire_zero_impot_puis_taux_plein(page):
    """Stock de 40 : 25 imputés la première année, 15 la deuxième, puis plus rien."""
    impots = page.evaluate("""() => impotsAvecReport({ annees: [2026, 2027, 2028], ebit: [25, 25, 25] }, 0.25,
                                                     [{ an: 2024, montant: 30 }, { an: 2025, montant: 10 }], 5)""")
    assert impots == pytest.approx([0, -(25 - 15) * 0.25, -25 * 0.25])


def test_un_deficit_expire_au_bout_de_la_duree(page):
    impots = page.evaluate("""() => impotsAvecReport({ annees: [2030], ebit: [20] }, 0.3, [{ an: 2020, montant: 50 }], 5)""")
    assert impots == pytest.approx([-20 * 0.3])


def test_une_perte_previsionnelle_nourrit_le_stock(page):
    impots = page.evaluate("""() => impotsAvecReport({ annees: [2026, 2027], ebit: [-10, 30] }, 0.25, [], 5)""")
    assert impots == pytest.approx([0, -(30 - 10) * 0.25])


def test_le_previsionnel_impute_les_pertes_de_l_historique(page, tmp_path):
    estimer(page, tmp_path, "pertes")
    f = page.evaluate("estimerPrevisionnel()")
    stock = sum(d["montant"] for d in f["deficits"])
    # Pertes de 28 et 2 en 2023-2024, bénéfice de 19,6 en 2025 : 10,4 restent.
    assert stock == pytest.approx(10.4, abs=0.05)
    taux = page.evaluate("impotAuto()")
    assert f["impots"][0] == pytest.approx(-(f["ebit"][0] - stock) * taux, abs=0.01)
    assert f["impots"][1] == pytest.approx(-f["ebit"][1] * taux, abs=0.01)


def test_sans_deficit_le_previsionnel_n_a_pas_d_impots_propres(page, tmp_path):
    estimer(page, tmp_path)
    assert page.evaluate("estimerPrevisionnel().impots") is None


def dcf_reference(f, wacc, g, impot):
    """Le calcul d'avant la modification, réécrit : impôt au taux sur l'EBIT
    positif, valeur terminale sur l'exercice normatif, BFR prolongé faute de CA."""
    n = len(f["ebit"])
    fcff = [e - max(0, e) * impot + d - c + b for e, d, c, b in zip(f["ebit"], f["da"], f["capex"], f["bfr"])]
    fac = [(1 + wacc) ** -(t + 1) for t in range(n)]
    ebit = f["ebit"][-1] * (1 + g)
    da = f["da"][-1] * (1 + g)
    normatif = ebit - max(0, ebit) * impot + da - da * (1 + g) + f["bfr"][-1] * (1 + g)
    return sum(x * y for x, y in zip(fcff, fac)) + normatif / (wacc - g) * fac[-1]


@pytest.mark.parametrize("wacc", [0.09, 0.12, 0.15])
def test_sans_impots_le_dcf_rend_les_chiffres_d_avant(page, wacc):
    f = page.evaluate("FLUX_TEST")
    ve = page.evaluate("w => calculDcf(FLUX_TEST, w, FLUX_TEST.g, 0.25).ve", wacc)
    assert ve == pytest.approx(dcf_reference(f, wacc, f["g"], 0.25), rel=1e-12)
    # Et un tableau d'impôts égal au calcul par défaut ne change rien non plus.
    meme = page.evaluate("""w => { const f = Object.assign({}, FLUX_TEST, { impots: FLUX_TEST.ebit.map((e) => -Math.max(0, e) * 0.25) });
                                   return calculDcf(f, w, f.g, 0.25).ve; }""", wacc)
    assert meme == pytest.approx(ve, rel=1e-12)


# ------------------------------------------------- passage VE → fonds propres

def lignes_passage(page):
    return {l["cle"]: l for l in page.evaluate("passageVeFp(VALO.bg).lignes")}


def test_sans_poste_particulier_le_passage_refait_la_dette_du_bilan(page, tmp_path):
    estimer(page, tmp_path)
    r = page.evaluate("[passageVeFp(VALO.bg).dette, baseEstimation(VALO.bg).dette]")
    assert r[0] == pytest.approx(r[1])


def test_credit_bail_et_titres_ont_le_bon_signe(page, tmp_path):
    estimer(page, tmp_path, "passage")
    lignes = lignes_passage(page)
    assert lignes["credit_bail"]["montant"] == pytest.approx(-4)      # dette : se retranche
    assert lignes["titres"]["montant"] == pytest.approx(6)            # actif : s'ajoute
    assert lignes["provisions"]["montant"] == pytest.approx(-2)
    assert lignes["dividendes"]["montant"] == pytest.approx(-1.5)
    assert all(lignes[k]["retenu"] for k in ("credit_bail", "titres", "provisions", "dividendes"))


def test_decocher_une_ligne_ramene_la_valeur_des_fonds_propres(page, tmp_path):
    estimer(page, tmp_path, "passage")
    page.click('.valo-vues button[data-vue="synthese"]')
    page.wait_for_selector('#valoSynthese [data-passage-retenu="titres"]')
    vfp = lambda: montant(page.inner_text('#valoSynthese [data-o="vfp"]'))
    avant = vfp()
    page.click('#valoSynthese [data-passage-retenu="titres"]')
    page.wait_for_timeout(150)
    assert vfp() == pytest.approx(avant - 6, abs=1)
    page.click('#valoSynthese [data-passage-retenu="titres"]')
    page.wait_for_timeout(150)
    assert vfp() == pytest.approx(avant, abs=0.5)


def test_les_minoritaires_saisis_se_deduisent(page, tmp_path):
    estimer(page, tmp_path, "passage")
    page.click('.valo-vues button[data-vue="synthese"]')
    page.wait_for_selector('#valoSynthese [data-passage-montant="minoritaires"]')
    avant = page.evaluate("fluxActif().detteNette")
    page.fill('#valoSynthese [data-passage-montant="minoritaires"]', "3")
    assert page.evaluate("fluxActif().detteNette") == pytest.approx(avant + 3)


def test_l_export_porte_les_hypotheses_et_le_passage(page, tmp_path):
    estimer(page, tmp_path, "passage")
    ouvrir_hypotheses(page)
    page.click('#valoEtats [data-action="hyp-regles"]')
    page.click("#valoEtats .hyp-panneau .hyp-boulon")
    chemin = exporter(page, tmp_path / "valo.xlsx", methodes={"dcf"})
    wb = openpyxl.load_workbook(chemin)
    assert wb.sheetnames.index("Hypothèses") == wb.sheetnames.index("DCF") + 1
    textes = [c.value for row in wb["Hypothèses"].iter_rows() for c in row if isinstance(c.value, str)]
    assert "Jeu Règles (retenu)" in textes and "Jeu Défaut" in textes
    syn = wb["Synthèse"]
    libelles = [syn.cell(r, 2).value for r in range(1, syn.max_row + 1)]
    assert any((x or "").startswith("Passage VE → fonds propres") for x in libelles)
    total = next(r for r in range(1, syn.max_row + 1) if (syn.cell(r, 2).value or "").startswith("Total retenu"))
    assert syn.cell(total, 3).value.startswith("=SUMIF(")


# ----------------------------------------------------- l'analyste, simulé

def analyse_simulee(horizon=5, g=0.03):
    serie = lambda v: [v] * horizon
    return {"ok": True, "modele": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "analyse": {
        "hypotheses": {"croissance": serie(0.06), "marge": serie(0.3), "da_sur_ca": 0.025,
                       "capex_sur_da": serie(1.2), "bfr_sur_ca": 0.12, "g": g},
        "justifications": {"croissance": "TCAM de 10 % ramené vers 6 %.", "marge": "Marge normalisée de 34,8 %.",
                           "capex": "1,2 fois les D&A.", "bfr": "12 % du CA.", "g": "Inflation locale de 3 %."},
        "alertes": ["Un seul secteur de référence."], "confiance": "moyenne",
        "resume": "Croissance ramenée vers le secteur, marge prudente."}}


def estimer_http(page, tmp_path):
    page.click('.tabs button[data-groupe="valorisation"]')
    page.click('.valo-vues button[data-vue="etats"]')
    page.set_input_files("#valoBgFichier", str(balance(tmp_path / "bg.xlsx")))
    page.wait_for_selector("#valoEtats .etat-table")
    page.click('#valoEtats [data-action="mode-prev"]')
    page.wait_for_selector("#valoEtats .traj-enveloppe .hyp-boulon")
    ouvrir_hypotheses(page)
    page.click('#valoEtats [data-action="hyp-regles"]')


def test_rien_ne_part_sans_la_case_de_consentement(page_http, tmp_path):
    appels = []
    page_http.route("**/api/forecast", lambda route: (appels.append(1), route.fulfill(status=200, body=json.dumps(analyse_simulee()))))
    estimer_http(page_http, tmp_path)
    bouton = '#valoEtats [data-action="hyp-analyste"]'
    assert page_http.is_disabled(bouton)
    assert "service externe" in page_http.inner_text("#valoEtats .hyp-consentement")
    page_http.check("#hypConsentement")
    assert not page_http.is_disabled(bouton)
    page_http.uncheck("#hypConsentement")
    assert page_http.is_disabled(bouton)
    assert appels == []


def test_l_analyste_est_applique_apres_validation(page_http, tmp_path):
    envoyes = []

    def repondre(route):
        envoyes.append(json.loads(route.request.post_data))
        # g hors bornes : la page doit le ramener à 4 %, quoi que dise le serveur.
        route.fulfill(status=200, content_type="application/json", body=json.dumps(analyse_simulee(g=0.09)))

    page_http.route("**/api/forecast", repondre)
    estimer_http(page_http, tmp_path)
    page_http.fill("#hypActivite", "Négoce de produits de grande consommation")
    page_http.check("#hypConsentement")
    page_http.click('#valoEtats [data-action="hyp-analyste"]')
    page_http.wait_for_selector("#valoEtats .hyp-analyse")
    assert len(envoyes) == 1
    dossier = envoyes[0]
    assert set(dossier) == {"societe", "historique", "normalise", "secteur", "macro", "defauts", "regles", "bornes"}
    assert dossier["societe"]["activite"] == "Négoce de produits de grande consommation"
    assert "comptes" not in json.dumps(dossier), "la balance ne quitte pas la page"
    assert page_http.evaluate("VALO.jeu") == "analyste"
    assert page_http.evaluate("VALO.jeux.analyste.g") == pytest.approx(0.04)
    texte = page_http.inner_text("#valoEtats .hyp-analyse")
    assert "Croissance ramenée vers le secteur" in texte and "Confiance moyenne" in texte
    assert "Un seul secteur de référence." in texte
    assert not page_http.is_disabled('#valoEtats [data-jeu="analyste"]')


def test_un_quota_atteint_laisse_les_regles_en_place(page_http, tmp_path):
    page_http.route("**/api/forecast", lambda route: route.fulfill(status=429, content_type="application/json",
                                                                   body=json.dumps({"ok": False, "code": "quota"})))
    estimer_http(page_http, tmp_path)
    page_http.check("#hypConsentement")
    page_http.click('#valoEtats [data-action="hyp-analyste"]')
    page_http.wait_for_selector("#valoEtats .hyp-erreur")
    assert "Quota" in page_http.inner_text("#valoEtats .hyp-erreur")
    assert page_http.evaluate("VALO.jeu") == "regles"

def test_le_dcf_exporte_suit_la_marge_par_exercice_et_le_report(page, tmp_path):
    """Le classeur ne doit pas recalculer autre chose que la page : marge par
    exercice des règles, impôt après report des déficits."""
    estimer(page, tmp_path, "pertes")
    ouvrir_hypotheses(page)
    page.click('#valoEtats [data-action="hyp-regles"]')
    page.click("#valoEtats .hyp-panneau .hyp-boulon")
    f = page.evaluate("fluxActif()")
    chemin = exporter(page, tmp_path / "valo.xlsx", methodes={"dcf"})
    dcf = openpyxl.load_workbook(chemin)["DCF"]
    lib = {dcf.cell(r, 2).value: r for r in range(1, dcf.max_row + 1)}
    ligne_marge = lib["Marge d'EBITDA"]
    ebitda = dcf.cell(lib["EBITDA"], 3).value
    assert ebitda.startswith("=") and "C" + str(ligne_marge) in ebitda.replace("$", "")
    impot = lib["(−) Impôt sur l'EBIT, après report des déficits"]
    valeurs = [dcf.cell(impot, 3 + t).value for t in range(len(f["impots"]))]
    assert valeurs == pytest.approx(f["impots"], abs=1e-6)
