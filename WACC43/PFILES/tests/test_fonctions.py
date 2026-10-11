"""Les fonctions serveur de l'agent, testées par le lanceur intégré de Node.

Elles sont écrites pour Cloudflare Pages Functions, en JavaScript : leurs
tests vivent donc dans `tests/fonctions/*.test.mjs`. Ce fichier les fait
tourner depuis pytest, pour qu'une seule commande couvre toute la plateforme.

Node n'a pas besoin d'être installé : le paquet Python Playwright, déjà requis
par les tests de la page, en embarque un.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ICI = Path(__file__).parent


def node():
    trouve = shutil.which("node")
    if trouve:
        return trouve
    try:
        import playwright
    except ImportError:
        return None
    for nom in ("node.exe", "node"):
        candidat = Path(playwright.__file__).parent / "driver" / nom
        if candidat.exists():
            return str(candidat)
    return None


def test_les_fonctions_serveur_passent_leurs_tests():
    binaire = node()
    if not binaire:
        pytest.skip("Node introuvable, ni sur le PATH ni dans Playwright")
    fichiers = sorted(str(p) for p in (ICI / "fonctions").glob("*.test.mjs"))
    assert fichiers, "aucun test de fonction trouvé"
    r = subprocess.run([binaire, "--test", *fichiers], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
