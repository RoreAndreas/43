"""
Courbes de taux souverains UEMOA, publiées par UMOA-Titres.

L'agence met en ligne chaque semaine un classeur `COURBES-DE-TAUX-au-JJ.MM.AAAA.xlsx`
avec une feuille par État et deux colonnes : taux zéro-coupon et taux après
lissage. On retient le taux lissé — c'est la courbe ajustée par l'agence, plus
stable d'une semaine à l'autre que les points bruts.

C'est l'un des trois socles du taux sans risque du référentiel Comparables, et
le seul qui soit la courbe propre des États qu'il dessert : un souverain UEMOA
emprunte en FCFA et porte déjà son risque pays. Aucune prime ne s'y ajoute, et
le coût du capital qui en découle est directement en monnaie locale — voir
`taux_sans_risque.py` pour les deux autres socles et leur affectation.
"""

import datetime
import re
from functools import lru_cache
from io import BytesIO

import pandas as pd
import requests

PAGE_COURBES = "https://www.umoatitres.org/fr/ressources-2/courbe-des-taux/"
ENTETES = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Les feuilles du classeur ne nomment pas les États comme les tickers BRVM.
ALIAS_PAYS = {
    "burkina": "Burkina Faso",
    "guinee-bissau": "Guinée-Bissau",
}

# "3 mois" -> 0.25, "10 ans" -> 10.0 : sert à ordonner et à choisir une maturité.
_MOIS = re.compile(r"(\d+)\s*mois", re.IGNORECASE)
_ANS = re.compile(r"(\d+)\s*ans?", re.IGNORECASE)


def _annees(libelle: str):
    m = _ANS.search(libelle)
    if m:
        return float(m.group(1))
    m = _MOIS.search(libelle)
    if m:
        return int(m.group(1)) / 12
    return None


def _date_du_lien(url: str):
    m = re.search(r"au[-_.]?(\d{2})[-.](\d{2})[-.](\d{4})", url, re.IGNORECASE)
    if not m:
        return None
    jour, mois, annee = (int(x) for x in m.groups())
    try:
        return datetime.date(annee, mois, jour)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def dernier_classeur():
    """(date, url) du classeur de courbes le plus récent publié."""
    reponse = requests.get(PAGE_COURBES, headers=ENTETES, timeout=60, verify=False)
    reponse.raise_for_status()
    liens = set(re.findall(r"((?:https?:)?//[^\"' )]*COURBE[^\"' )]*\.xlsx)", reponse.text, re.IGNORECASE))
    dates = [(_date_du_lien(u), u) for u in liens]
    dates = sorted([(d, u) for d, u in dates if d], reverse=True)
    if not dates:
        raise RuntimeError("Aucun classeur de courbes trouvé sur UMOA-Titres.")
    date, url = dates[0]
    return date, ("https:" + url if url.startswith("//") else url)


@lru_cache(maxsize=1)
def charger_courbes() -> dict:
    """
    Courbes souveraines du dernier classeur publié.

    Retourne {"date": "AAAA-MM-JJ", "source": url, "pays": {État: [[libellé, années, taux], ...]}}
    Les taux sont en décimal (0.0713 pour 7,13 %), triés par maturité croissante.
    """
    date, url = dernier_classeur()
    reponse = requests.get(url, headers=ENTETES, timeout=90, verify=False)
    reponse.raise_for_status()
    classeur = pd.ExcelFile(BytesIO(reponse.content))

    pays = {}
    for feuille in classeur.sheet_names:
        nom = ALIAS_PAYS.get(feuille.strip().lower(), feuille.strip())
        brut = pd.read_excel(classeur, sheet_name=feuille, header=None)
        if brut.shape[1] < 14:
            continue  # feuille technique (« Feuil1 »)

        # Colonne 11 : maturité, colonne 13 : taux après lissage. L'en-tête est
        # en ligne 12, les données commencent juste en dessous.
        points = []
        for libelle, taux in brut.iloc[13:, [11, 13]].dropna().values:
            annees = _annees(str(libelle))
            try:
                valeur = float(taux)
            except (TypeError, ValueError):
                continue
            if annees is None or not (0 < valeur < 0.5):
                continue
            points.append([str(libelle).strip(), annees, valeur])

        if points:
            pays[nom] = sorted(points, key=lambda p: p[1])

    if not pays:
        raise RuntimeError(f"Classeur {url} illisible : aucune courbe extraite.")

    return {"date": date.isoformat(), "source": url, "pays": pays}


def taux(pays: str, annees_cibles: float = 10.0):
    """
    Taux souverain d'un État à la maturité demandée, ou à la plus longue
    disponible si la courbe s'arrête avant (le Niger ne va pas au-delà de 7 ans).

    Retourne (taux, libellé de la maturité retenue) ou (None, None).
    """
    courbes = charger_courbes()["pays"]
    points = courbes.get(pays)
    if not points:
        return None, None
    exact = [p for p in points if abs(p[1] - annees_cibles) < 1e-9]
    retenu = exact[0] if exact else min(points, key=lambda p: abs(p[1] - annees_cibles))
    return retenu[2], retenu[0]
