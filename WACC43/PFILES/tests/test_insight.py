"""Onglets CMPC, Insight et Valorisation.

Le CMPC ouvre sur Paramètres, Calcul et Sociétés ; Sociétés et Insight
n'existent qu'en référentiel Comparables. Insight répond à une question : à
quel niveau se tient la marge d'EBITDA du secteur, et de combien évolue-t-elle
par an — face à la société évaluée. Les moyennes sont recalculées ici depuis
les données de la page.
"""

from conftest import mode_comparables, ouvrir
from test_etats_financiers import ANNEES, CA, EBITDA, balance, importer_balance


def onglets(page):
    return [b.inner_text().strip() for b in page.query_selector_all(".tabs button") if b.is_visible()]


def sous_onglets(page):
    return [b.inner_text().strip() for b in page.query_selector_all(".sous-vues button") if b.is_visible()]


def pourcent(texte):
    net = texte.replace("%", "").replace("pt", "").replace(" ", "").replace(" ", "").replace(" ", "")
    return float(net.replace("−", "-").replace("+", "").replace(",", ".")) / 100


def ligne_table(page, libelle):
    for tr in page.query_selector_all("#insightCorps .ins-table tbody tr"):
        cellules = [td.text_content().strip() for td in tr.query_selector_all("td")]
        if cellules[0] == libelle:
            return cellules[1:]
    raise AssertionError(f"ligne « {libelle} » absente")


# ------------------------------------------------ navigation

def test_trois_onglets(page):
    assert onglets(page) == ["CMPC", "Valorisation"]                     # Damodaran : ni Insight ni Sociétés
    assert sous_onglets(page) == ["Paramètres", "Calcul"]
    mode_comparables(page)
    assert onglets(page) == ["CMPC", "Insight", "Valorisation"]
    assert sous_onglets(page) == ["Paramètres", "Calcul", "Sociétés"]
    ouvrir(page, "societes")
    assert page.is_visible("#panel-societes")
    ouvrir(page, "insight")
    assert sous_onglets(page) == []
    assert page.is_visible("#panel-insight")


def test_un_onglet_se_rouvre_sur_sa_derniere_vue(page):
    ouvrir(page, "wacc")
    page.click('.tabs button[data-groupe="valorisation"]')
    page.click('.tabs button[data-groupe="cmpc"]')
    assert page.is_visible("#panel-wacc") and page.is_hidden("#panel-params")


def test_repasser_en_damodaran_quitte_insight_et_societes(page):
    mode_comparables(page)
    ouvrir(page, "societes")
    ouvrir(page, "insight")
    page.evaluate("params.referentiel = 'damodaran'; renderAll()")
    assert page.is_visible("#panel-params")
    assert onglets(page) == ["CMPC", "Valorisation"]
    page.click('.tabs button[data-groupe="cmpc"]')                         # pas de retour sur Sociétés
    assert page.is_visible("#panel-params")


# ------------------------------------------------ Insight : deux blocs

def moyennes_secteur(page, donnees):
    """Moyenne simple des marges des sociétés présentes à tous les exercices."""
    liste = [donnees["comparables"]["societes"][i] for i in page.evaluate("societesRetenues().ids")]
    annees = sorted({a for s in liste for a in s.get("annees", [])})
    annees = [a for a in annees if 2 * sum(1 for s in liste if str(a) in (s.get("ca") or {})) >= len(liste)]

    def marge(s, a):
        ca, eb = (s.get("ca") or {}).get(str(a)), (s.get("ebitda") or {}).get(str(a))
        return eb / ca if ca and ca > 0 and eb is not None else None

    completes = [s for s in liste if all(marge(s, a) is not None for a in annees)]
    assert len(completes) >= max(3, len(liste) / 2), "le test suppose un panel constant"
    return annees, [sum(marge(s, a) for s in completes) / len(completes) for a in annees]


def test_deux_blocs_seulement(page):
    mode_comparables(page)
    ouvrir(page, "insight")
    assert len(page.query_selector_all("#insightCorps .ins-bloc")) == 2
    assert page.query_selector("#insightGraphe svg path.ins-med") is not None


def test_marge_moyenne_du_secteur_et_son_evolution(page, donnees):
    mode_comparables(page)
    ouvrir(page, "insight")
    annees, moyennes = moyennes_secteur(page, donnees)
    secteur = ligne_table(page, "Secteur, moyenne")
    for texte, attendu in zip(secteur[:-1], moyennes):
        assert abs(pourcent(texte) - attendu) < 0.0006
    evolution = (moyennes[-1] - moyennes[0]) / (annees[-1] - annees[0])
    assert abs(pourcent(secteur[-1]) - evolution) < 0.0006                 # en points par an
    niveau = sum(moyennes) / len(moyennes)
    assert abs(pourcent(page.text_content("#insightCorps .ins-chiffre.is-secteur strong")) - niveau) < 0.0006


def test_la_societe_evaluee_face_au_secteur(page, tmp_path, donnees):
    mode_comparables(page)
    ouvrir(page, "insight")
    assert "balance non importée" in page.text_content("#insightCorps .ins-chiffre.is-cible")
    importer_balance(page, balance(tmp_path / "bg.xlsx"))
    ouvrir(page, "insight")
    marges = [e / c for e, c in zip(EBITDA, CA)]
    cible = ligne_table(page, "Société évaluée")
    annees, moyennes = moyennes_secteur(page, donnees)
    colonnes = sorted(set(annees) | set(ANNEES))
    for a, m in zip(ANNEES, marges):
        assert abs(pourcent(cible[colonnes.index(a)]) - m) < 0.0006
    evolution = (marges[-1] - marges[0]) / (ANNEES[-1] - ANNEES[0])
    assert abs(pourcent(cible[-1]) - evolution) < 0.0006
    # L'écart d'un exercice commun : la société moins le secteur, en points.
    ecart = ligne_table(page, "Écart")
    a = ANNEES[-1]
    assert abs(pourcent(ecart[colonnes.index(a)]) - (marges[-1] - moyennes[annees.index(a)])) < 0.0006
    assert len(page.query_selector_all("#insightGraphe .ins-cible-point")) == len(ANNEES)


def test_insight_suit_le_secteur_choisi(page, donnees):
    mode_comparables(page)
    ouvrir(page, "insight")
    avant = page.inner_text("#insightCorps .ins-titre")
    autre = next(i["nom"] for i in donnees["comparables"]["industries"] if i["nom"] != avant)
    ouvrir(page, "params")
    page.select_option('#paramsMain select[data-param="secteur"]', autre)
    ouvrir(page, "insight")
    assert page.inner_text("#insightCorps .ins-titre") == autre
