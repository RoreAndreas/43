"""Harnais de test de la page statique.

La page est un fichier autonome : aucun serveur, aucun appel réseau une fois
construite. On l'ouvre donc telle quelle dans un Chromium piloté, et on la
manipule par ses vrais contrôles plutôt qu'en appelant ses fonctions internes —
un test qui contourne l'interface ne dit rien de ce que l'utilisateur voit.

    python -m pytest PFILES/tests

Prérequis : `playwright install chromium` une fois, et une page déjà construite
dans `PFILES/site/index.html`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).parents[1]
PAGE = RACINE / "site" / "index.html"

# Le jeu de données est collé dans la page entre `const DATA = ` et la ligne
# suivante. On le relit pour que les tests comparent l'affichage aux chiffres
# sources plutôt qu'à des valeurs recopiées, qui vieilliraient à chaque build.
_DATA = re.compile(r"const DATA = (\{.*?\});\n\s*const STEPS", re.DOTALL)


@pytest.fixture(scope="session")
def donnees() -> dict:
    if not PAGE.exists():
        pytest.skip(f"page non construite : {PAGE}")
    trouve = _DATA.search(PAGE.read_text(encoding="utf-8"))
    assert trouve, "bloc DATA introuvable dans la page"
    return json.loads(trouve.group(1).replace("<\\/", "</"))


@pytest.fixture(scope="session")
def navigateur():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as err:                      # pragma: no cover
            pytest.skip(f"Chromium indisponible : {err}")
        yield nav
        nav.close()


@pytest.fixture
def page(navigateur):
    if not PAGE.exists():
        pytest.skip(f"page non construite : {PAGE}")
    onglet = navigateur.new_page(viewport={"width": 1280, "height": 900})
    erreurs = []
    onglet.on("pageerror", lambda e: erreurs.append(str(e)))
    onglet.goto(PAGE.resolve().as_uri())
    onglet.wait_for_selector("#paramsMain .card-block")
    yield onglet
    # Une exception JS laisse la page à moitié dessinée : le test suivant
    # constaterait un état incohérent sans qu'on sache d'où il vient.
    assert not erreurs, "erreurs JS pendant le test : " + " | ".join(erreurs)
    onglet.close()


# ---------------------------------------------------------------- utilitaires

def choisir(page, champ: str, valeur: str) -> None:
    """Sélectionne une valeur dans un menu de l'onglet Paramètres."""
    page.select_option(f'#paramsMain select[data-param="{champ}"]', valeur)


def mode_comparables(page, pays: str = "Benin") -> None:
    """Passe en référentiel Comparables sur un pays qui a une courbe souveraine.

    Le pays par défaut du jeu Damodaran (Abu Dhabi) n'en a pas : sans ce
    recalage le CMPC ne serait calculable dans aucun test, et l'absence de
    résultat viendrait du pays, pas de ce qu'on cherche à vérifier.
    """
    choisir(page, "referentiel", "brvm")
    choisir(page, "country", pays)


def ligne_resultat(page, libelle: str) -> str:
    """Valeur affichée en regard d'un libellé de l'encadré de droite."""
    for bloc in page.query_selector_all("#paramsResult .result-row"):
        spans = bloc.query_selector_all("span")
        if spans and spans[0].inner_text().strip().startswith(libelle):
            return spans[-1].inner_text().strip()
    raise AssertionError(f"ligne « {libelle} » absente de l'encadré")


def nombre_fr(texte: str) -> float:
    """« 9,18 % » -> 9.18 ; « 214 687 M » -> 214687.0"""
    net = texte.replace("%", "").replace("M", "")
    net = net.replace(" ", "").replace(" ", "").replace(" ", "")
    return float(net.replace(",", "."))


def secteur(donnees: dict, nom: str) -> dict:
    for i in (donnees.get("comparables") or {}).get("industries", []):
        if i["nom"] == nom:
            return i
    raise AssertionError(f"secteur « {nom} » absent de l'univers de comparables")
