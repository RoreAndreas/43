"""Le taux sans risque, commun aux deux référentiels.

    taux sans risque = US Bond (année, maturité) + prime de risque pays

Le MEDAF repose sur le taux des US Bonds quelle que soit la méthode : la prime
de marché qui multiplie le bêta est mesurée sur le marché américain, et lui
adosser un rendement souverain local additionnerait les conditions de deux
marchés dans une même formule. Le risque du pays valorisé entre par la prime de
risque pays, explicitement.

Ce fichier vérifie les deux moitiés de cette phrase, puis ce qu'elles
entraînent. D'abord la couverture : la prime existe pour les cent cinquante-sept
pays, donc le CMPC aussi — là où une seule source souveraine n'en desservait
que sept. Ensuite la monnaie : le taux est en dollar, le CMPC qui en découle
aussi, et il est ramené en monnaie locale par le différentiel d'inflation —
sauf là où le dollar a cours légal, où les deux curseurs ajouteraient un écart
sans objet.
"""

import pytest

from conftest import choisir, ligne_resultat, mode_comparables, nombre_fr

# Un pays par branche, choisi pour ce qu'il exerce.
BENIN = "Benin"                  # prime forte, conversion nécessaire
FRANCE = "France"                # prime faible, conversion nécessaire
ETATS_UNIS = "United States"     # dollar local, et pas de taux d'IS publié
NIGERIA = "Nigeria"              # le cas ordinaire des 127 pays du socle dollar


def taux(page):
    """Ce que la page calcule, tel qu'elle le calcule."""
    return page.evaluate("tauxSansRisque()")


def cmpc(page):
    return nombre_fr(page.inner_text("#paramsResult .result-hero-value"))


def cartes(page):
    page.click('.tabs button[data-tab="wacc"]')
    return page.eval_on_selector_all(
        "#stack .comp", "els => els.map(e => e.dataset.comp)")


# --------------------------------------------------------------- la formule

@pytest.mark.parametrize("pays", [BENIN, FRANCE, ETATS_UNIS, NIGERIA])
def test_le_taux_est_le_us_bond_plus_la_prime_pays(page, donnees, pays):
    mode_comparables(page, pays)
    rf = taux(page)
    annee, maturite = page.evaluate("[params.year, params.maturity]")

    attendu_socle = donnees["rf"][f"{annee}-{'30' if maturite == '30Y' else '10'}"] / 100
    attendu_prime = donnees["pays"][pays]["crp"]

    assert rf["socle"] == pytest.approx(attendu_socle)
    assert rf["prime"] == pytest.approx(attendu_prime)
    assert rf["taux"] == pytest.approx(attendu_socle + attendu_prime)
    assert rf["monnaie"] == "dollar"


def test_les_deux_referentiels_retiennent_le_meme_taux(page):
    """« Quelle que soit la méthode » : c'est l'objet même de ce fichier.

    Les deux référentiels appellent la même fonction ; ce test vaut contre le
    jour où l'un des deux se remettra à calculer son taux dans son coin.
    """
    mode_comparables(page, FRANCE)
    sous_comparables = taux(page)["taux"]

    choisir(page, "referentiel", "damodaran")
    assert taux(page)["taux"] == pytest.approx(sous_comparables)


def test_le_taux_affiche_est_celui_qui_sert(page):
    mode_comparables(page, NIGERIA)
    rf = taux(page)
    assert nombre_fr(ligne_resultat(page, "Taux US Bond")) == pytest.approx(
        round(rf["socle"] * 100, 2))
    assert nombre_fr(ligne_resultat(page, "Prime de risque pays")) == pytest.approx(
        round(rf["prime"] * 100, 2))
    assert nombre_fr(ligne_resultat(page, "Taux sans risque, en dollar")) == pytest.approx(
        round(rf["taux"] * 100, 2))


def test_la_maturite_est_partagee_par_les_deux_referentiels(page):
    """Le menu propre à la courbe souveraine a disparu avec elle."""
    mode_comparables(page)
    libelles = [e.inner_text() for e in page.query_selector_all("#paramsMain .field-label")]
    assert "Maturité du taux sans risque" in libelles
    assert not any("courbe souveraine" in libelle for libelle in libelles)


def test_changer_de_maturite_deplace_le_cmpc(page):
    """Sans cela, le sélecteur de maturité ne servirait à rien sous Comparables."""
    mode_comparables(page)
    choisir(page, "maturity", "30Y")
    long = cmpc(page)
    choisir(page, "maturity", "10Y")
    assert cmpc(page) != long


def test_changer_de_pays_deplace_le_cmpc(page):
    """Le pays n'entre plus que par sa prime de risque et son taux d'IS."""
    mode_comparables(page, FRANCE)
    vu = cmpc(page)
    choisir(page, "country", BENIN)
    assert cmpc(page) != vu


# -------------------------------------------------------------- la couverture

def test_les_157_pays_donnent_un_cmpc(page, donnees):
    """Le motif du chantier : sept pays sur cent cinquante-sept en donnaient un.

    La boucle est faite dans le navigateur — cent cinquante-sept allers-retours
    par l'interface prendraient trois minutes pour vérifier une seule chose.
    """
    mode_comparables(page)
    sans = page.evaluate("""() => {
      const avant = params.country;
      const manquants = [];
      for (const nom of Object.keys(DATA.pays)) {
        params.country = nom;
        if (!cmpcComparables()) manquants.push(nom);
      }
      params.country = avant;
      return manquants;
    }""")
    assert sans == [], f"{len(sans)} pays sans CMPC, ex. {sans[:5]}"
    assert len(donnees["pays"]) >= 150, "le référentiel a maigri, le test perd son objet"


def test_aucune_courbe_souveraine_ne_subsiste(donnees):
    """UMOA-Titres et la BCE ont été retirées : le jeu de données doit suivre.

    Un reliquat de trois cents kilooctets qui ne pilote plus rien finirait par
    passer pour une source vivante.
    """
    assert "taux_souverains" not in donnees


# ----------------------------------------------------------------- la monnaie

def test_le_cmpc_est_ramene_en_monnaie_locale(page):
    mode_comparables(page, NIGERIA)
    dollar = nombre_fr(ligne_resultat(page, "CMPC en dollar"))
    assert cmpc(page) != dollar, "le CMPC affiché est resté en dollar"

    infl = page.evaluate("[Number(params.inflation_local), Number(params.inflation_ref)]")
    attendu = ((1 + dollar / 100) * (1 + infl[0]) / (1 + infl[1]) - 1) * 100
    assert cmpc(page) == pytest.approx(attendu, abs=0.011)


def test_la_carte_de_conversion_detaille_le_calcul(page):
    mode_comparables(page, NIGERIA)
    assert "loc" in cartes(page)
    lignes = page.inner_text('#stack .comp[data-comp="loc"] .sub-rows')
    assert "CMPC en dollar" in lignes
    assert "Inflation attendue, monnaie locale" in lignes
    assert "CMPC en monnaie locale" in lignes


def test_pas_de_conversion_la_ou_le_dollar_a_cours_legal(page):
    """Convertir le dollar en dollar ajouterait l'écart des deux curseurs."""
    mode_comparables(page, ETATS_UNIS)
    assert page.evaluate("cmpcComparables().conversion") is False
    assert "loc" not in cartes(page)

    page.click('.tabs button[data-tab="params"]')
    assert cmpc(page) == pytest.approx(
        round(page.evaluate("cmpcComparables().wacc") * 100, 2))


def test_les_curseurs_d_inflation_ne_jouent_que_la_ou_l_on_convertit(page):
    mode_comparables(page, ETATS_UNIS)
    avant = cmpc(page)
    page.evaluate("() => { params.inflation_local = 0.12; apply(); }")
    assert cmpc(page) == avant, "le CMPC a bougé alors qu'aucune conversion ne s'applique"

    choisir(page, "country", NIGERIA)
    bouge = cmpc(page)
    page.evaluate("() => { params.inflation_local = 0.03; apply(); }")
    assert cmpc(page) != bouge


def test_les_curseurs_disent_quand_ils_sont_sans_effet(page):
    """Un réglage qui ne fait rien doit le dire, sinon on le croit pris en compte."""
    mode_comparables(page, ETATS_UNIS)
    aides = page.inner_text("#paramsMain")
    assert "Sans effet ici" in aides

    choisir(page, "country", NIGERIA)
    assert "Sans effet ici" not in page.inner_text("#paramsMain")


# ------------------------------------------------------------- le taux d'IS

def test_un_pays_sans_taux_d_is_publie_donne_quand_meme_un_cmpc(page, donnees):
    """Damodaran n'en publie pas pour les États-Unis, d'où viennent plus de la
    moitié des comparables. Refuser d'y calculer serait absurde."""
    if donnees["pays"][ETATS_UNIS].get("tax") is not None:
        pytest.skip("Damodaran publie désormais un taux d'IS pour les États-Unis")
    mode_comparables(page, ETATS_UNIS)
    assert page.evaluate("cmpcComparables().taxDefaut") is True
    assert page.evaluate("cmpcComparables().tax") == 0.25
    assert "25 % retenu" in page.inner_text("#paramsResult")
