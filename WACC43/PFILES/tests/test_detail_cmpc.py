"""L'onglet CMPC doit détailler ses paliers sous les deux référentiels.

Les composantes du mode comparable existaient sans tableau de valeurs : les
cartes se dépliaient sur du vide, alors que celles de Damodaran montraient leur
décomposition. Le résultat était donné, jamais vérifiable.
"""

import pytest

from conftest import choisir, mode_comparables

# Ce que l'utilisateur doit pouvoir lire sans rouvrir le classeur.
PALIERS = [
    ("ke", "Taux US Bond"),
    ("ke", "Prime de risque pays"),
    ("ke", "Bêta (3 ans)"),
    ("ke", "Prime de risque marché"),
    ("kd", "Taux d'IS"),
    ("kd", "Coût de la dette après IS"),
    ("poids", "Gearing retenu (D/E)"),
    ("wacc", "CMPC"),
]


@pytest.fixture
def cmpc_comparable(page):
    mode_comparables(page)
    choisir(page, "secteur", "Banks")
    page.click('.tabs button[data-tab="wacc"]')
    return page


@pytest.mark.parametrize("carte, libelle", PALIERS)
def test_chaque_palier_est_visible(cmpc_comparable, carte, libelle):
    lignes = cmpc_comparable.inner_text(f'#stack .comp[data-comp="{carte}"] .sub-rows')
    assert libelle in lignes


def test_chaque_composante_porte_une_formule(cmpc_comparable):
    for carte in ["ke", "kd", "poids", "wacc"]:
        cmpc_comparable.click(f'#stack .comp[data-comp="{carte}"] .comp-head')
        code = cmpc_comparable.inner_text(f'#frame .detail[data-detail="{carte}"] code')
        assert "=" in code, f"la composante {carte} n'affiche aucun calcul"


def test_aucune_carte_ne_se_deplie_sur_du_vide(cmpc_comparable):
    """Le défaut d'origine : des cartes dépliables au contenu inexistant."""
    for bloc in cmpc_comparable.query_selector_all("#stack .comp"):
        lignes = bloc.query_selector_all(".sub-row")
        assert lignes, f"carte {bloc.get_attribute('data-comp')} sans détail"
