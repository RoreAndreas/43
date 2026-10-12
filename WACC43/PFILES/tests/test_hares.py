"""HARES : l'échantillon de travail, ses demandes cumulatives, l'envoi vers la
comparaison.

Ce que la spec demande : HARES vit dans son propre onglet, sans panneau
latéral ni filtre classique ; il part de l'échantillon des comparables quand
il y en a un, sinon de la base complète ; chaque demande s'applique au
résultat de la précédente ; ses filtres ne touchent pas les autres onglets, et
seul « Envoyer vers comparaison » transmet le résultat. Les attendus sont
recalculés ici, en Python, sur le jeu de données embarqué.
"""

import statistics

import pytest

from conftest import mode_comparables, ouvrir

TELECOMS = "Telecommunication Services"


def ouvrir_hares(page):
    if not page.is_visible("#panel-hares"):
        page.click('.tabs button[data-groupe="hares"]')


def demander(page, question):
    ouvrir_hares(page)
    page.fill("#haresQuestion", question)
    page.click("#haresDemander")
    page.wait_for_timeout(250)
    assert page.query_selector("#haresReponse .agent-erreur") is None, page.inner_text("#haresReponse")
    return page.inner_text("#haresReponse")


def ids(page):
    return page.evaluate("idsHares()")


def valeur(s, serie, an):
    v = (s.get(serie) or {}).get(str(an))
    return v


def ve_ebitda(s, an):
    eb = valeur(s, "ebitda", an)
    return (s["capitalisation"] + s["dette"]) / eb if eb and eb > 0 else None


def telecoms_du_monde(page):
    """Point de départ commun : toutes les télécoms de la base."""
    ouvrir_hares(page)
    demander(page, "Isole les sociétés de télécom")


# ------------------------------------------------------------- l'onglet

def test_l_onglet_hares_remplace_l_assistant(page):
    noms = [b.inner_text().strip() for b in page.query_selector_all(".tabs button") if b.is_visible()]
    assert "HARES" in noms and "Assistant" not in noms


def test_hares_occupe_toute_la_zone_sans_panneau_lateral_ni_filtre(page):
    ouvrir_hares(page)
    panneau = page.query_selector("#panel-hares")
    assert panneau.query_selector("aside, select, input[type=checkbox], input[type=range]") is None
    largeur = page.evaluate("document.documentElement.clientWidth")
    assert panneau.query_selector(".hares-cadre").bounding_box()["width"] >= largeur - 2 * 40


def test_la_saisie_prend_la_main_a_l_ouverture(page):
    ouvrir_hares(page)
    assert page.evaluate("document.activeElement.id") == "haresQuestion"


# ---------------------------------------------------------- le départ

def test_sans_comparables_hares_part_de_la_base_complete(page, donnees):
    ouvrir_hares(page)
    assert page.evaluate("HARES.depart.type") == "base"
    assert len(ids(page)) == len(donnees["comparables"]["societes"])
    assert "base complète" in page.inner_text("#haresDepart")


def test_sous_comparables_hares_reprend_l_echantillon_et_le_dit(page):
    mode_comparables(page)
    ouvrir_hares(page)
    r = page.evaluate("[HARES.depart.type, idsHares().join(','), societesRetenues().ids.join(','), params.secteur]")
    assert r[0] == "comparables" and r[1] == r[2]
    texte = page.inner_text("#haresDepart")
    assert "Échantillon de départ" in texte and r[3] in texte
    page.click('[data-hares-depart="base"]')
    assert page.evaluate("HARES.depart.type") == "base"


def test_le_depart_suit_les_comparables_jusqu_a_la_premiere_demande(page):
    mode_comparables(page)
    ouvrir_hares(page)
    avant = page.evaluate("idsHares().join(',')")
    ouvrir(page, "params")
    page.evaluate("params.secteur = 'Banks'; apply()")
    ouvrir_hares(page)
    assert page.evaluate("idsHares().join(',') === societesRetenues().ids.join(',')")
    assert page.evaluate("idsHares().join(',')") != avant
    # Une demande appliquée fige le départ : HARES signale sans écraser.
    demander(page, "Fais ressortir uniquement les groupes")
    ouvrir(page, "params")
    page.evaluate("params.secteur = 'Insurance'; apply()")
    ouvrir_hares(page)
    assert page.evaluate("HARES.etapes.length") == 1
    assert "a changé depuis" in page.inner_text("#haresDepart")


# ------------------------------------------------ les demandes de la spec

def test_isoler_un_secteur_et_un_continent(page, donnees):
    ouvrir_hares(page)
    texte = demander(page, "Isole les sociétés de télécom en Afrique")
    soc = donnees["comparables"]["societes"]
    attendu = {i for i, s in soc.items() if s["industrie"] == TELECOMS and s["continent"] == "Afrique"}
    assert set(ids(page)) == attendu
    assert "J'ai compris" in texte and "sans appel réseau" in texte


def test_les_demandes_se_cumulent(page, donnees):
    ouvrir_hares(page)
    demander(page, "Isole les sociétés de télécom en Afrique")
    premiere = set(ids(page))
    demander(page, "Garde uniquement les sociétés dont la marge d'EBITDA est comprise entre 20 % et 35 %")
    an = page.evaluate("HARES.an")
    soc = donnees["comparables"]["societes"]

    def marge(s):
        ca, eb = valeur(s, "ca", an), valeur(s, "ebitda", an)
        return eb / ca if ca and ca > 0 and eb is not None else None

    attendu = {i for i in premiere if marge(soc[i]) is not None and 0.2 <= marge(soc[i]) <= 0.35}
    assert set(ids(page)) == attendu
    assert page.evaluate("HARES.etapes.map((e) => [e.avant, e.apres])") == [[len(soc), len(premiere)], [len(premiere), len(attendu)]]


def test_fais_ressortir_uniquement_les_groupes(page, donnees):
    telecoms_du_monde(page)
    avant = ids(page)
    texte = demander(page, "Fais ressortir uniquement les groupes")
    soc = donnees["comparables"]["societes"]
    assert set(ids(page)) == {i for i in avant if soc[i].get("statut") == "groupe"}
    # La règle est dite, et ce qui est écarté est compté.
    assert "Groupe : la description S&P" in texte and "Écartées" in texte


def test_le_levier_s_explique_faute_de_tresorerie(page, donnees):
    telecoms_du_monde(page)
    avant = ids(page)
    texte = demander(page, "Parmi elles, lesquelles ont un endettement net / EBITDA inférieur à 2x ?")
    an = page.evaluate("HARES.an")
    soc = donnees["comparables"]["societes"]

    def levier(s):
        eb = valeur(s, "ebitda", an)
        return s["dette"] / eb if eb and eb > 0 else None

    assert set(ids(page)) == {i for i in avant if levier(soc[i]) is not None and levier(soc[i]) < 2}
    assert "dette totale (brute)" in texte


def test_classer_par_ca_et_quartiles_des_multiples(page, donnees):
    telecoms_du_monde(page)
    demander(page, "Classe-les par chiffre d'affaires et donne-moi la médiane et les quartiles des multiples")
    an = page.evaluate("HARES.an")
    soc = donnees["comparables"]["societes"]
    affiches = page.eval_on_selector_all("#haresEchantillon tbody tr", "trs => trs.map((tr) => tr.dataset.haresId)")
    cas = [valeur(soc[i], "ca", an) for i in affiches]
    connus = [c for c in cas if c is not None]
    assert connus == sorted(connus, reverse=True)
    stats = {s["champ"]: s for s in page.evaluate("HARES.etapes[1].stats")}
    assert set(stats) == {"ve_ebitda", "ve_ca", "pe"}
    multiples = sorted(v for v in (ve_ebitda(soc[i], an) for i in ids(page)) if v is not None)
    q1, mediane, q3 = statistics.quantiles(multiples, n=4, method="inclusive")
    assert stats["ve_ebitda"]["n"] == len(multiples)
    assert stats["ve_ebitda"]["mediane"] == pytest.approx(mediane)
    assert stats["ve_ebitda"]["q1"] == pytest.approx(q1)
    assert stats["ve_ebitda"]["q3"] == pytest.approx(q3)
    assert page.query_selector('#haresReponse [data-hares-stat="ve_ebitda"]') is not None


def test_retirer_les_valeurs_aberrantes_et_dire_pourquoi(page, donnees):
    telecoms_du_monde(page)
    avant = ids(page)
    texte = demander(page, "Retire les valeurs aberrantes de VE / EBITDA et explique pourquoi")
    an = page.evaluate("HARES.an")
    soc = donnees["comparables"]["societes"]
    v = sorted(x for x in (ve_ebitda(soc[i], an) for i in avant) if x is not None)
    q1, _, q3 = statistics.quantiles(v, n=4, method="inclusive")
    bas, haut = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    aberrantes = {i for i in avant if ve_ebitda(soc[i], an) is not None and not bas <= ve_ebitda(soc[i], an) <= haut}
    assert set(ids(page)) == set(avant) - aberrantes
    assert aberrantes, "l'échantillon des télécoms devrait compter au moins une valeur aberrante"
    retirees = page.evaluate("HARES.etapes[1].retirees")
    assert len(retirees) == len(aberrantes)
    assert all("borne" in r["raison"] for r in retirees)
    assert "Règle de Tukey" in texte and "Retirées, et pourquoi".upper() in texte.upper()


def test_les_exemples_sont_reconnus_sur_place(page):
    ouvrir_hares(page)
    exemples = page.eval_on_selector_all("#haresExemples [data-agent-question]", "els => els.map((e) => e.dataset.agentQuestion)")
    assert len(exemples) == 6
    for q in exemples:
        assert "J'ai compris" in demander(page, q), q


# ------------------------------------------------- annuler, reprendre, retirer

def test_annuler_reprendre_et_repartir(page):
    telecoms_du_monde(page)
    n1 = len(ids(page))
    demander(page, "Fais ressortir uniquement les groupes")
    demander(page, "les 5 plus grosses")
    assert len(ids(page)) == 5
    page.click("[data-hares-annuler]")
    assert page.evaluate("HARES.etapes.length") == 2
    page.click('[data-hares-etape="0"]')
    page.click("[data-hares-reprendre]")
    assert page.evaluate("HARES.etapes.length") == 1 and len(ids(page)) == n1
    texte = demander(page, "repars de zéro")
    assert page.evaluate("HARES.etapes.length") == 0 and "Retour à l'échantillon de départ" in texte


def test_retirer_une_societe_nommee(page):
    telecoms_du_monde(page)
    nom = page.evaluate("ligneHares(idsHares()[0]).nom")
    demander(page, "retire " + nom)
    assert nom not in page.evaluate("idsHares().map((id) => ligneHares(id).nom)")


def test_le_tableau_s_arrete_a_cent_lignes(page):
    ouvrir_hares(page)
    assert len(page.query_selector_all("#haresEchantillon tbody tr")) == 100
    assert "Les 100 premières" in page.inner_text("#haresEchantillon")


# ------------------------------------------- les autres onglets, et l'envoi

def test_les_filtres_de_hares_ne_touchent_pas_les_comparables(page):
    mode_comparables(page)
    avant = page.evaluate("[societesRetenues().ids.join(','), JSON.stringify(multipleComparables())]")
    demander(page, "Fais ressortir uniquement les groupes")
    demander(page, "les 3 plus grosses")
    assert page.evaluate("[societesRetenues().ids.join(','), JSON.stringify(multipleComparables())]") == avant
    assert page.evaluate("ENVOI_HARES") is None
    ouvrir(page, "valorisation")
    page.click('.valo-vues button[data-vue="comparables"]')
    assert page.query_selector("#noticeHares") is None


def test_envoyer_vers_comparaison_puis_revenir(page):
    mode_comparables(page)
    cmpc = page.evaluate("JSON.stringify(multipleComparables())")
    demander(page, "Fais ressortir uniquement les groupes")
    echantillon = ids(page)
    page.click("[data-hares-envoyer]")
    attendu = page.evaluate("""(ids) => {
        const an = exerciceReference(ids.map((id) => COMPARABLES[id]));
        return ids.filter((id) => (COMPARABLES[id].ebitda || {})[String(an)] > 0).length;
    }""", echantillon)
    assert page.evaluate("multipleComparables().n") == attendu
    assert "envoyé vers Valorisation" in page.inner_text("#haresEchantillon")
    page.click("[data-hares-voir]")
    assert page.is_visible("#valoComparables")
    assert "Échantillon envoyé par HARES" in page.inner_text("#noticeHares")
    page.click('#noticeHares [data-action="hares-oublier"]')
    assert page.evaluate("ENVOI_HARES") is None
    assert page.query_selector("#noticeHares") is None
    # Retour à l'échantillon du CMPC : le multiple redevient celui d'avant l'envoi.
    assert page.evaluate("JSON.stringify(multipleComparables())") == cmpc


def test_l_envoi_ouvre_la_comparaison_meme_sous_damodaran(page):
    ouvrir_hares(page)
    demander(page, "Isole les sociétés de télécom en Afrique")
    page.click("[data-hares-envoyer]")
    page.click("[data-hares-voir]")
    assert page.is_visible("#comparablesMain")
    assert not page.is_visible("#comparablesAbsents")
    assert "HARES" in page.inner_text("#comparablesMain")


def test_sur_telephone_la_page_ne_defile_pas_en_largeur(navigateur):
    from conftest import PAGE
    onglet = navigateur.new_page(viewport={"width": 390, "height": 844})
    onglet.goto(PAGE.resolve().as_uri(), timeout=90000)
    onglet.wait_for_selector("#paramsMain .card-block")
    ouvrir_hares(onglet)
    demander(onglet, "Isole les sociétés de télécom en Afrique")
    assert onglet.evaluate("document.documentElement.scrollWidth") <= 390
    onglet.close()
