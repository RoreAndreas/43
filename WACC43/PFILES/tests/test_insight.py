"""Onglets CMPC, Comparables et Valorisation, et le sous-onglet Insight.

CMPC ouvre sur Paramètres et Calcul, Comparables sur Sociétés et Insight ;
Comparables n'existe qu'en référentiel Comparables. Insight lit le secteur en
médiane et quartiles — recalculés ici depuis les données de la page — et place
la société de la balance générale dans ces quartiles.
"""

import statistics

from conftest import choisir, mode_comparables, ouvrir
from test_etats_financiers import CA, EBITDA, balance, importer_balance


def onglets(page):
    return [b.inner_text().strip() for b in page.query_selector_all(".tabs button") if b.is_visible()]


def sous_onglets(page):
    return [b.inner_text().strip() for b in page.query_selector_all(".sous-vues button") if b.is_visible()]


def pourcent(texte):
    return float(texte.replace("%", "").replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")) / 100


def case(page, libelle):
    for c in page.query_selector_all("#insightCorps .dcf-case"):
        if c.query_selector(".dcf-case-label").text_content().strip() == libelle:
            return c.query_selector(".dcf-case-valeur").text_content().strip()
    raise AssertionError(f"case « {libelle} » absente")


# ------------------------------------------------ navigation

def test_trois_onglets_et_leurs_sous_onglets(page):
    assert onglets(page) == ["CMPC", "Valorisation"]                     # Damodaran : pas de Comparables
    assert sous_onglets(page) == ["Paramètres", "Calcul"]
    mode_comparables(page)
    assert onglets(page) == ["CMPC", "Comparables", "Valorisation"]
    ouvrir(page, "societes")
    assert sous_onglets(page) == ["Sociétés", "Insight"]
    assert page.is_visible("#panel-societes")
    ouvrir(page, "valorisation")
    assert sous_onglets(page) == []                                      # la Valorisation a ses propres vues
    assert page.is_visible("#panel-valorisation")


def test_un_onglet_se_rouvre_sur_sa_derniere_vue(page):
    ouvrir(page, "wacc")
    assert page.is_visible("#panel-wacc")
    page.click('.tabs button[data-groupe="valorisation"]')
    page.click('.tabs button[data-groupe="cmpc"]')
    assert page.is_visible("#panel-wacc") and page.is_hidden("#panel-params")


def test_repasser_en_damodaran_quitte_les_comparables(page):
    mode_comparables(page)
    ouvrir(page, "insight")
    page.evaluate("params.referentiel = 'damodaran'; renderAll()")
    assert page.is_visible("#panel-params")
    assert onglets(page) == ["CMPC", "Valorisation"]


# ------------------------------------------------ Insight

def echantillon(page, donnees):
    ids = page.evaluate("societesRetenues().ids")
    return [donnees["comparables"]["societes"][i] for i in ids]


def exercices(liste):
    annees = sorted({a for s in liste for a in s.get("annees", [])})
    return [a for a in annees if 2 * sum(1 for s in liste if str(a) in (s.get("ca") or {})) >= len(liste)]


def test_insight_resume_l_echantillon(page, donnees):
    mode_comparables(page)
    ouvrir(page, "insight")
    liste = echantillon(page, donnees)
    assert int(case(page, "Sociétés")) == len(liste)
    an = str(exercices(liste)[-1])
    marges = [s["ebitda"][an] / s["ca"][an] for s in liste
              if (s.get("ca") or {}).get(an, 0) > 0 and (s.get("ebitda") or {}).get(an) is not None]
    assert abs(pourcent(case(page, "Marge d'EBITDA médiane")) - statistics.median(marges)) < 0.0006
    # Graphique : bande interquartile et médiane, un point par exercice.
    assert page.query_selector("#insightGraphe svg polygon.ins-bande") is not None
    assert len(page.query_selector_all("#insightGraphe .ins-med-point")) == len(exercices(liste))


def test_insight_sur_tout_le_secteur(page, donnees):
    mode_comparables(page)
    ouvrir(page, "insight")
    page.click('#insightCorps [data-portee="secteur"]')
    nom = page.evaluate("params.secteur")
    total = sum(1 for s in donnees["comparables"]["societes"].values() if s["industrie"] == nom)
    assert int(case(page, "Sociétés")) == total


def test_changer_d_indicateur_redessine(page):
    mode_comparables(page)
    ouvrir(page, "insight")
    page.click('#insightCorps [data-indicateur="croissance"]')
    assert "is-active" in page.get_attribute('#insightCorps [data-indicateur="croissance"]', "class")
    assert "Croissance du CA" in page.get_attribute("#insightGraphe svg", "aria-label")


def test_la_societe_evaluee_se_place_dans_les_quartiles(page, tmp_path):
    mode_comparables(page)
    ouvrir(page, "insight")
    assert "Importez la balance générale" in page.inner_text("#insightCorps .ins-invite")
    importer_balance(page, balance(tmp_path / "bg.xlsx"))
    ouvrir(page, "insight")
    reglettes = page.query_selector_all("#insightCorps .ins-reglette")
    assert len(reglettes) == 3
    marge = reglettes[1].inner_text()
    assert f"{EBITDA[-1] / CA[-1] * 100:.1f}".replace(".", ",") in marge
    assert any(mot in marge for mot in ("quartile", "médiane"))
    # La société apparaît aussi sur le graphique.
    assert len(page.query_selector_all("#insightGraphe .ins-cible-point")) == 3


def test_composition_et_principales_capitalisations(page, donnees):
    mode_comparables(page)
    ouvrir(page, "insight")
    liste = echantillon(page, donnees)
    lignes = page.query_selector_all("#insightCorps .ins-table tbody tr")
    assert len(lignes) == min(8, len(liste))
    plus_grosse = max(liste, key=lambda s: s.get("capitalisation") or 0)
    assert plus_grosse["nom"] in lignes[0].inner_text()
    zones = {s["zone"] for s in liste}
    assert len(page.query_selector_all("#insightCorps .ins-compo > div:first-child .ins-barre")) == min(8, len(zones))


def test_insight_suit_le_secteur_choisi(page, donnees):
    mode_comparables(page)
    ouvrir(page, "insight")
    avant = page.inner_text("#insightCorps .ins-titre")
    autres = [i["nom"] for i in donnees["comparables"]["industries"] if i["nom"] != avant]
    ouvrir(page, "params")
    choisir(page, "secteur", autres[0])
    ouvrir(page, "insight")
    assert page.inner_text("#insightCorps .ins-titre") == autres[0]
