"""Le taux sans risque du référentiel Comparables, pour les 157 pays.

Avant, une seule source l'alimentait — les courbes UMOA-Titres — soit sept
États sur cent cinquante-sept, et trente-deux sociétés de comparables sur six
mille huit cent quatre-vingt-deux. Choisir n'importe quel autre pays laissait le
CMPC vide, alors que l'univers de comparables était mondial depuis trois exports.

Trois socles désormais, une seule formule :

    taux retenu = socle(maturité) + prime de risque pays

et la prime tombe quand le socle est déjà la courbe de l'État lui-même. Ce
fichier vérifie les deux moitiés de cette phrase, puis ce qu'elles entraînent :
un CMPC libellé dans la devise du socle, ramené en monnaie locale par le
différentiel d'inflation — et surtout **pas** ramené quand le socle est déjà
dans la bonne monnaie, où les deux curseurs ajouteraient un écart sans objet.
"""

import pytest

from conftest import choisir, ligne_resultat, mode_comparables, nombre_fr

SOCLES = {"XOF", "EUR", "USD"}

# Un pays par branche de l'échelle, choisi pour ce qu'il exerce.
BENIN = "Benin"                  # sa propre courbe, en FCFA : ni prime ni conversion
FRANCE = "France"                # socle BCE, prime pays, mais déjà en euro
ETATS_UNIS = "United States"     # son propre Treasury, et pas de taux d'IS publié
NIGERIA = "Nigeria"              # socle dollar, prime pays, conversion nécessaire


@pytest.fixture(scope="session")
def affectation(donnees):
    courbes = donnees.get("taux_souverains")
    if not courbes:
        pytest.skip("aucun taux souverain embarqué")
    return courbes["pays"]


@pytest.fixture(scope="session")
def courbe_bce(donnees):
    """Un test dur suffit à signaler une BCE injoignable au moment du build.

    La construction ne s'arrête pas pour autant : les pays de la zone euro
    retombent sur le socle dollar, ce qui est le comportement voulu. Faire
    tomber ici tous les tests qui supposent la courbe transformerait une panne
    tierce en quatre échecs sans rapport avec ce qu'ils vérifient.
    """
    bce = (donnees.get("taux_souverains") or {}).get("bce")
    if not bce:
        pytest.skip("courbe BCE absente de la page : socle euro non affecté")
    return bce


# ------------------------------------------------------------ les données

def test_tous_les_pays_ont_un_socle(donnees, affectation):
    """Le défaut d'origine : 150 pays sur 157 sans taux, donc sans CMPC."""
    orphelins = sorted(set(donnees["pays"]) - set(affectation))
    assert not orphelins, f"{len(orphelins)} pays sans socle, ex. {orphelins[:5]}"


def test_les_socles_sont_ceux_annonces(affectation):
    inconnus = {a["socle"] for a in affectation.values()} - SOCLES
    assert not inconnus, f"socles inattendus : {inconnus}"


def test_un_etat_de_l_umoa_est_sur_sa_propre_courbe(donnees, affectation):
    assert affectation[BENIN] == {"socle": "XOF", "prime": False, "locale": True}
    assert BENIN in donnees["taux_souverains"]["umoa"]["pays"]


def test_la_zone_euro_porte_la_prime_mais_reste_en_monnaie_locale(affectation, courbe_bce):
    """La courbe AAA exclut le risque pays : la prime grecque doit s'y ajouter.

    Mais l'euro est bien la monnaie de la Grèce : aucune conversion d'inflation
    n'a de sens ici, et `locale` est ce qui l'empêche.
    """
    for pays in (FRANCE, "Greece", "Italy"):
        assert affectation[pays] == {"socle": "EUR", "prime": True, "locale": True}


def test_les_etats_unis_sont_sur_leur_propre_treasury(affectation):
    """Damodaran leur attribue 23 points de prime : les ajouter au Treasury
    reviendrait à compter deux fois le risque de l'émetteur de la courbe."""
    assert affectation[ETATS_UNIS] == {"socle": "USD", "prime": False, "locale": True}


def test_le_reste_du_monde_est_construit_et_hors_monnaie_locale(affectation):
    for pays in (NIGERIA, "United Kingdom", "Japan", "Brazil"):
        assert affectation[pays] == {"socle": "USD", "prime": True, "locale": False}


def test_la_courbe_bce_est_lisible(donnees):
    """Le seul test dur sur la BCE : c'est lui qui doit rougir en cas de panne.

    Mille cent quatre-vingt-dix-neuf sociétés de comparables dépendent de ce
    socle. Une page publiée sans lui n'est pas fausse, mais elle est dégradée,
    et cela doit se voir.
    """
    bce = (donnees.get("taux_souverains") or {}).get("bce")
    assert bce, "courbe BCE absente : la zone euro est retombée sur le socle dollar"
    points = bce["points"]
    assert len(points) >= 5
    assert [p[1] for p in points] == sorted(p[1] for p in points), "maturités désordonnées"
    assert all(-0.05 < taux < 0.5 for _l, _a, taux in points), "taux hors de toute plausibilité"


def test_la_couverture_depasse_largement_l_umoa(donnees, affectation):
    """Le chiffre qui justifiait le chantier : sept pays desservis sur 157."""
    umoa = sum(1 for a in affectation.values() if a["socle"] == "XOF")
    assert umoa == 7
    assert len(affectation) == len(donnees["pays"]) == 157


# ------------------------------------------ le taux affiché, à l'écran

def libelle_resultat(page, debut):
    """Le libellé de la ligne, quand c'est lui qui porte l'information.

    `ligne_resultat` rend la valeur ; la source et la maturité du socle sont
    dans l'intitulé, pas en face.
    """
    for bloc in page.query_selector_all("#paramsResult .result-row"):
        spans = bloc.query_selector_all("span")
        if spans and spans[0].inner_text().strip().startswith(debut):
            return spans[0].inner_text().strip()
    raise AssertionError(f"ligne « {debut} » absente de l'encadré")


def socle_et_prime(page):
    """(socle, prime, taux retenu) tels que l'encadré les affiche, en %."""
    socle = nombre_fr(ligne_resultat(page, "Socle souverain"))
    try:
        prime = nombre_fr(ligne_resultat(page, "Prime de risque pays"))
        taux = nombre_fr(ligne_resultat(page, "Taux sans risque, en"))
    except AssertionError:
        return socle, None, socle
    return socle, prime, taux


def test_le_taux_retenu_est_la_somme_de_ses_deux_moities(page, donnees):
    """Un total affiché sans ses termes ne se vérifie pas, il se croit."""
    mode_comparables(page, NIGERIA)
    socle, prime, taux = socle_et_prime(page)
    assert prime is not None, "la prime devrait être affichée sur un socle construit"
    assert round(prime, 2) == round(donnees["pays"][NIGERIA]["crp"] * 100, 2)
    # Les trois nombres sont arrondis séparément à l'affichage : la somme des
    # parties affichées peut manquer d'un centième le total affiché.
    assert abs(socle + prime - taux) <= 0.011, f"{socle} + {prime} != {taux}"


def test_sur_sa_propre_courbe_la_prime_est_dite_incluse(page):
    mode_comparables(page, BENIN)
    encadre = page.inner_text("#paramsResult")
    assert "Socle souverain" in encadre
    assert "UMOA-Titres" in encadre
    assert "Taux sans risque, en" not in encadre, "un total sans prime serait une ligne de trop"


def exige_socle_euro(donnees, pays):
    """Les cas de la zone euro ne portent que si la courbe BCE a été récupérée.

    Sans elle, ces pays sont sur le socle dollar : le test dirait vrai sur une
    page dégradée, ou faux sans que ce soit la faute de ce qu'il vérifie.
    """
    if pays in (FRANCE, "Greece", "Italy") and not (donnees.get("taux_souverains") or {}).get("bce"):
        pytest.skip(f"courbe BCE absente : {pays} est retombé sur le socle dollar")


@pytest.mark.parametrize("pays, source", [
    (BENIN, "UMOA-Titres"), (FRANCE, "BCE"), (NIGERIA, "US Treasury")])
def test_le_socle_nomme_sa_source(page, donnees, pays, source):
    exige_socle_euro(donnees, pays)
    mode_comparables(page, pays)
    assert source in libelle_resultat(page, "Socle souverain")


def test_les_etats_unis_calculent_malgre_l_is_manquant(page):
    """23 pays sur 157 n'ont pas de taux d'IS publié, dont celui d'où viennent
    plus de la moitié des comparables. Refuser de calculer y serait absurde."""
    mode_comparables(page, ETATS_UNIS)
    assert page.inner_text("#paramsResult .result-hero-value").strip() != "—"
    assert "25 % retenu" in page.inner_text("#paramsResult")


# ------------------------------------------- la conversion en monnaie locale

def cmpc_affiche(page):
    return nombre_fr(page.inner_text("#paramsResult .result-hero-value"))


def inflations(page, ref, locale):
    page.evaluate("a => { params.inflation_ref = a[0]; params.inflation_local = a[1]; apply(); }",
                  [ref, locale])


def test_hors_monnaie_locale_le_cmpc_est_converti(page):
    mode_comparables(page, NIGERIA)
    choisir(page, "secteur", "Banks")
    inflations(page, 0.02, 0.10)

    devise = nombre_fr(ligne_resultat(page, "CMPC en dollar"))
    local = cmpc_affiche(page)
    attendu = ((1 + devise / 100) * 1.10 / 1.02 - 1) * 100
    assert round(local, 1) == round(attendu, 1), f"{local} affiché contre {attendu} attendu"
    assert local > devise, "une inflation locale plus forte doit renchérir le taux"


def test_la_conversion_est_neutre_a_inflations_egales(page):
    mode_comparables(page, NIGERIA)
    choisir(page, "secteur", "Banks")
    inflations(page, 0.04, 0.04)
    assert cmpc_affiche(page) == nombre_fr(ligne_resultat(page, "CMPC en dollar"))


@pytest.mark.parametrize("pays", [BENIN, FRANCE, ETATS_UNIS])
def test_en_monnaie_locale_aucune_conversion_n_est_appliquee(page, donnees, pays):
    """Le piège : deux curseurs laissés à leurs valeurs par défaut ajouteraient
    un demi-point à un taux déjà libellé dans la monnaie du pays."""
    exige_socle_euro(donnees, pays)
    mode_comparables(page, pays)
    choisir(page, "secteur", "Banks")
    avant = cmpc_affiche(page)
    inflations(page, 0.01, 0.20)
    assert cmpc_affiche(page) == avant, "la conversion s'applique là où elle n'a pas lieu d'être"
    assert "CMPC en" not in page.inner_text("#paramsResult .result-rows")


def test_la_carte_de_conversion_n_apparait_que_si_elle_sert(page):
    mode_comparables(page, NIGERIA)
    page.click('.tabs button[data-tab="wacc"]')
    assert page.query_selector('#stack .comp[data-comp="loc"]') is not None

    # Retour aux paramètres : leurs menus ne sont pas manipulables tant que
    # l'onglet CMPC est affiché.
    page.click('.tabs button[data-tab="params"]')
    choisir(page, "country", BENIN)
    page.click('.tabs button[data-tab="wacc"]')
    assert page.query_selector('#stack .comp[data-comp="loc"]') is None


def test_la_carte_de_conversion_montre_son_calcul(page):
    mode_comparables(page, NIGERIA)
    page.click('.tabs button[data-tab="wacc"]')
    page.click('#stack .comp[data-comp="loc"] .comp-head')
    page.wait_for_timeout(300)
    detail = page.inner_text("#frame .detail.is-shown")
    assert "parité des pouvoirs d'achat" in detail
    assert "CMPC loc. = (1 + CMPC)" in detail


# --------------------------------------------------- le menu des maturités

def maturites(page):
    return page.eval_on_selector_all(
        '#paramsMain select[data-param="maturite_souveraine"] option', "e => e.map(o => o.value)")


def test_le_menu_suit_le_socle(page, courbe_bce):
    mode_comparables(page, FRANCE)
    assert "30 ans" in maturites(page) and "3 mois" in maturites(page)
    mode_comparables(page, NIGERIA)
    assert maturites(page) == ["10 ans", "30 ans"], "le Treasury n'offre que deux points"


def test_une_maturite_indisponible_est_recalee_sur_la_plus_proche(page, courbe_bce):
    """Sinon le menu afficherait un point et le calcul en prendrait un autre."""
    mode_comparables(page, FRANCE)
    choisir(page, "maturite_souveraine", "3 mois")
    mode_comparables(page, NIGERIA)

    retenue = page.evaluate("params.maturite_souveraine")
    assert retenue in maturites(page)
    assert page.eval_on_selector(
        '#paramsMain select[data-param="maturite_souveraine"]', "e => e.value") == retenue
    assert retenue in libelle_resultat(page, "Socle souverain")
