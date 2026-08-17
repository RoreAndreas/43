"""Le bêta affiché doit être celui qui entre dans le calcul.

Le défaut corrigé ici : l'encadré « Secteur comparable » montrait la moyenne des
bêtas cotés à un an de la seule place d'Abidjan, pendant que le CMPC était bâti
sur la médiane à trois ans de l'univers de comparables. Les deux chiffres
n'avaient ni le même horizon, ni la même population, ni la même statistique — et
rien à l'écran ne le disait.
"""

from conftest import choisir, ligne_resultat, mode_comparables, nombre_fr, secteur


def test_encadre_affiche_la_mediane_trois_ans(page, donnees):
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")

    attendu = secteur(donnees, "Banks")["beta_3ans"]
    assert nombre_fr(ligne_resultat(page, "Bêta médian (3 ans)")) == round(attendu, 3)


def test_effectif_et_capitalisation_decrivent_la_meme_population(page, donnees):
    """L'effectif annoncé est celui dont sort le bêta, pas celui de la BRVM."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")

    banques = secteur(donnees, "Banks")
    assert nombre_fr(ligne_resultat(page, "Sociétés du secteur")) == banques["societes"]
    assert nombre_fr(ligne_resultat(page, "Capitalisation cumulée")) == round(banques["capitalisation"])


def test_le_calcul_du_cout_des_fonds_propres_reprend_ce_beta(page, donnees):
    """Le Ke détaillé dans l'onglet CMPC doit citer le bêta 3 ans, pas le 1 an."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")

    page.click('.tabs button[data-tab="wacc"]')
    page.click('#stack .comp[data-comp="ke"] .comp-head')
    detail = page.inner_text('#frame .detail[data-detail="ke"]')

    b3 = secteur(donnees, "Banks")["beta_3ans"]
    assert f"{b3:.3f}".replace(".", ",") in detail
    assert "3 ans" in detail


def test_aucun_beta_un_an_ne_se_fait_passer_pour_le_beta_retenu(page, donnees):
    """Le bêta 1 an peut être publié, jamais présenté comme celui du calcul."""
    mode_comparables(page)
    choisir(page, "industrie_brvm", "Banks")
    encadre = page.inner_text("#paramsResult")

    assert "Bêta coté moyen" not in encadre
    assert "trois ans" in encadre or "3 ans" in encadre
