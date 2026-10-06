"""Le bêta affiché doit être celui qui entre dans le calcul.

Le défaut corrigé ici : l'encadré « Secteur comparable » montrait la moyenne des
bêtas cotés à un an de la seule place d'Abidjan, pendant que le CMPC était bâti
sur la médiane à trois ans de l'univers de comparables. Les deux chiffres
n'avaient ni le même horizon, ni la même population, ni la même statistique — et
rien à l'écran ne le disait.
"""

from conftest import choisir, ligne_resultat, mode_comparables, nombre_fr, secteur, ouvrir


def test_encadre_affiche_la_mediane_trois_ans(page, donnees):
    """La médiane affichée est celle des bêtas à 3 ans, désendettés un à un :
    c'est elle que le calcul ré-endette."""
    mode_comparables(page)
    choisir(page, "secteur", "Banks")

    attendu = secteur(donnees, "Banks")["beta_u"]
    assert nombre_fr(ligne_resultat(page, "Bêta désendetté médian (3 ans)")) == round(attendu, 3)


def test_l_effectif_annonce_est_celui_du_beta(page, donnees):
    """L'effectif annoncé est celui dont sort le bêta, pas celui de la BRVM."""
    mode_comparables(page)
    choisir(page, "secteur", "Banks")

    banques = secteur(donnees, "Banks")
    assert nombre_fr(ligne_resultat(page, "Sociétés du secteur")) == banques["societes"]


def test_le_calcul_du_cout_des_fonds_propres_reprend_ce_beta(page, donnees):
    """Le Ke détaillé dans l'onglet CMPC doit citer la médiane désendettée des
    bêtas 3 ans, pas le 1 an."""
    mode_comparables(page)
    choisir(page, "secteur", "Banks")

    ouvrir(page, "wacc")
    page.click('#stack .comp[data-comp="ke"] .comp-head')
    detail = page.inner_text('#frame .detail[data-detail="ke"]')

    bu = secteur(donnees, "Banks")["beta_u"]
    assert f"{bu:.3f}".replace(".", ",") in detail
    assert "3 ans" in detail


def test_aucun_beta_un_an_ne_se_fait_passer_pour_le_beta_retenu(page, donnees):
    """Le bêta 1 an peut être publié, jamais présenté comme celui du calcul."""
    mode_comparables(page)
    choisir(page, "secteur", "Banks")
    encadre = page.inner_text("#paramsResult")

    assert "Bêta coté moyen" not in encadre
    assert "trois ans" in encadre or "3 ans" in encadre
