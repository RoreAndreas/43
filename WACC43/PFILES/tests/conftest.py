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
    """Passe en référentiel Comparables sur un pays donné.

    Tous les pays du référentiel donnent désormais un CMPC — le taux sans
    risque est celui des US Bonds augmenté de la prime de risque pays, publiée
    pour les cent cinquante-sept. Le recalage ne sert donc plus qu'à rendre les
    tests déterministes : un défaut d'affichage ne doit pas dépendre du pays
    que Damodaran classe en tête de sa liste.
    """
    choisir(page, "referentiel", "comparables")
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


def continent_vide(donnees: dict) -> str:
    """Un continent que l'univers de comparables ne couvre pas.

    Codé en dur, ce nom vieillit mal : l'Europe et les Amériques étaient vides
    tant que l'univers se limitait à l'Afrique, et sept tests l'ont supposé
    jusqu'à ce que trois exports arrivent. On le cherche donc dans les données.
    """
    peuples = {s["continent"]
               for s in (donnees.get("comparables") or {}).get("societes", {}).values()}
    for continent, _pays in donnees["options"]["countries_grouped"]:
        if continent not in peuples:
            return continent
    pytest.skip("aucun continent vide : l'univers les couvre tous")


def zone_vide(donnees: dict, continent: str) -> str:
    """Une zone de ce continent qu'aucune société ne peuple."""
    peuplees = {s["zone"]
                for s in (donnees.get("comparables") or {}).get("societes", {}).values()}
    for zone, _pays in donnees["options"]["zones_par_continent"].get(continent, []):
        if zone not in peuplees:
            return zone
    pytest.skip(f"aucune zone vide sur {continent}")


def secteur(donnees: dict, nom: str, perimetre: str = "univers") -> dict:
    """Statistiques d'un secteur à l'échelle demandée.

    Les médianes sont publiées à trois échelles emboîtées — univers, continent,
    zone — et la page retient la plus étroite qui atteigne le seuil. Les tests
    doivent donc dire laquelle ils attendent plutôt que de supposer.
    """
    bloc = ((donnees.get("comparables") or {}).get("secteurs") or {}).get(nom)
    if bloc is None:
        raise AssertionError(f"secteur « {nom} » absent de l'univers de comparables")
    if perimetre == "univers":
        return bloc["univers"]
    for echelle in ("zones", "continents"):
        if perimetre in bloc.get(echelle, {}):
            return bloc[echelle][perimetre]
    raise AssertionError(f"secteur « {nom} » absent du périmètre « {perimetre} »")
