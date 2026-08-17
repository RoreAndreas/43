"""
Univers de comparables, lu depuis l'export S&P Global déposé dans WACC43.

L'export tient en trois onglets qui partagent la même liste de sociétés, dans le
même ordre, appariés par `Entity ID` :

    Sheet1  produits, EBITDA, marge, résultat net (FY2022 à FY2025),
            puis bêta 1 an (colonne S) et bêta 3 ans (colonne T)
    Sheet2  géographie, pays, industrie, industrie primaire, description
    Sheet3  dette totale, capitalisation boursière

Seules les sociétés **complètes** alimentent la plateforme : pays, industrie,
les deux bêtas, dette, capitalisation, chiffre d'affaires sur quatre exercices
et résultat net sur trois. Les autres sont conservées dans l'univers mais
marquées `visible: False`, et n'entrent ni dans les médianes ni dans les
effectifs affichés.

L'EBITDA est délibérément hors critère. S&P n'en publie pas pour les banques ni
les assureurs — la notion n'a pas de sens pour elles — et l'exiger ferait tomber
le secteur bancaire de 112 sociétés à 1, alors qu'il est le premier des places
africaines. Un critère qui détruit le secteur principal ne mesure plus la
complétude, il mesure le modèle comptable.

L'industrie retenue est la colonne E de Sheet2 (`IQ_INDUSTRY`), soit une
soixantaine de secteurs. La colonne F (`IQ_PRIMARY_INDUSTRY`) est plus fine mais
trop éclatée pour servir de maille de comparables.

Ce que le fichier ne contient pas : **aucun bêta**. Le coût des fonds propres ne
peut donc pas en sortir. Il fournit en revanche dette et capitalisation, donc un
gearing sectoriel observé — celui qu'il fallait jusqu'ici saisir à la main.

Piège d'unités : S&P exporte les comptes et la dette en **milliers** (en-tête
`BCEAO000`) mais la capitalisation en **millions** (`BCEAOM`). Rapporter l'une à
l'autre sans conversion donne un gearing mille fois trop élevé — 593 pour les
banques au lieu de 0,59. Tout est donc ramené ici en millions.

Les en-têtes occupent les lignes 3 à 6 ; les données commencent ligne 7.
"""

from __future__ import annotations

import statistics
from pathlib import Path

import openpyxl

PREMIERE_LIGNE = 7
EXERCICES = ["FY2025", "FY2024", "FY2023", "FY2022"]

# S&P écrit « NA » quand la donnée manque, et parfois « NM » (non significatif).
_ABSENT = {"NA", "NM", "NC", "-", ""}


def _nombre(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    texte = str(valeur).strip()
    if texte.upper() in _ABSENT:
        return None
    try:
        return float(texte.replace(",", ""))
    except ValueError:
        return None


def _nom_court(nom: str) -> str:
    """« Absa Bank Kenya PLC (NASE:ABSA) » -> « Absa Bank Kenya PLC »."""
    texte = str(nom).strip()
    if texte.endswith(")") and "(" in texte:
        return texte[: texte.rindex("(")].strip()
    return texte


def _place_et_ticker(nom: str, entity_id):
    """« Absa Group Limited (JSE:ABG) » -> ("JSE", "ABG").

    S&P préfixe le code de la valeur par celui de sa place de cotation. C'est la
    seule mention du marché dans l'export : il n'y a pas de colonne dédiée.
    """
    texte = str(nom).strip()
    if texte.endswith(")") and "(" in texte:
        dedans = texte[texte.rindex("(") + 1: -1].strip()
        if ":" in dedans:
            place, _sep, code = dedans.partition(":")
            return place.strip() or None, code.strip() or str(entity_id)
        return None, dedans or str(entity_id)
    return None, str(entity_id)


def trouver_export(racine: Path) -> Path | None:
    """Le fichier d'export le plus récent déposé dans le dossier du projet."""
    candidats = sorted(
        racine.glob("SPGlobal_Export_*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidats[0] if candidats else None


def charger(chemin: Path, progress=None) -> dict:
    """Lit l'export et rend l'univers de comparables."""
    def dire(message):
        if progress:
            progress(message)

    dire(f"Comparables : lecture de {chemin.name}...")
    wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    try:
        signaletique = {}
        for ligne in wb["Sheet2"].iter_rows(
            min_row=PREMIERE_LIGNE, min_col=1, max_col=7, values_only=True
        ):
            nom, ident, _geo, pays, industrie, primaire, description = ligne[:7]
            if not nom or not ident:
                continue
            place, code = _place_et_ticker(nom, ident)
            signaletique[str(ident)] = {
                "nom": _nom_court(nom),
                "ticker": code,
                "place": place,
                "pays": (pays or "").strip() or None,
                "industrie": (industrie or "").strip() or None,
                "industrie_fine": (primaire or "").strip() or None,
                "description": (description or "").strip() or None,
            }

        comptes = {}
        for ligne in wb["Sheet1"].iter_rows(
            min_row=PREMIERE_LIGNE, min_col=1, max_col=20, values_only=True
        ):
            ident = ligne[1]
            if not ident:
                continue
            comptes[str(ident)] = {
                "ca": {a: _nombre(ligne[2 + i]) for i, a in enumerate(EXERCICES)},
                "ebitda": {a: _nombre(ligne[6 + i]) for i, a in enumerate(EXERCICES)},
                "rn": {a: _nombre(ligne[14 + i]) for i, a in enumerate(EXERCICES[:3])},
                "beta_1an": _nombre(ligne[18]),
                "beta_3ans": _nombre(ligne[19]),
            }

        marche = {}
        for ligne in wb["Sheet3"].iter_rows(
            min_row=PREMIERE_LIGNE, min_col=1, max_col=4, values_only=True
        ):
            ident = ligne[1]
            if not ident:
                continue
            dette = _nombre(ligne[2])
            marche[str(ident)] = {
                # Dette en milliers, capitalisation en millions : on ramène tout
                # en millions pour que le rapport ait un sens.
                "dette": None if dette is None else dette / 1000.0,
                "capitalisation": _nombre(ligne[3]),
            }
    finally:
        wb.close()

    societes = {}
    for ident, base in signaletique.items():
        if not base["industrie"] or not base["pays"]:
            continue
        entree = dict(base)
        entree.update(comptes.get(ident, {}))
        entree.update(marche.get(ident, {}))
        entree["visible"] = _est_complete(entree)
        societes[ident] = entree

    visibles = sum(1 for s in societes.values() if s["visible"])
    dire(f"Comparables : {visibles} sociétés complètes sur {len(societes)}.")
    return {
        "source": chemin.name,
        "societes": societes,
        "industries": _industries(societes),
        # Passerelle vers le volet BRVM, dont les sociétés portent les mêmes
        # codes : elle permet de reclasser les bêtas cotés dans la taxonomie de
        # l'export, et de n'avoir qu'une seule nomenclature d'industries.
        "industrie_par_ticker": {
            s["ticker"]: s["industrie"] for s in societes.values() if s.get("ticker")
        },
    }


def _est_complete(s: dict) -> bool:
    """La société porte-t-elle toutes les valeurs dont la plateforme se sert ?

    Bêtas, dette et capitalisation alimentent le coût du capital ; chiffre
    d'affaires et résultat net alimentent l'affichage. L'EBITDA est hors critère,
    pour la raison exposée en tête de module.
    """
    if not s.get("pays") or not s.get("industrie"):
        return False
    if s.get("beta_1an") is None or s.get("beta_3ans") is None:
        return False
    if s.get("dette") is None or not s.get("capitalisation"):
        return False
    ca = s.get("ca") or {}
    rn = s.get("rn") or {}
    if any(ca.get(a) is None for a in EXERCICES):
        return False
    if any(rn.get(a) is None for a in EXERCICES[:3]):
        return False
    return True


def _industries(societes: dict) -> list:
    """Secteurs de l'univers, avec leurs bêtas et leur gearing médians.

    La médiane, et non la moyenne ni un rapport d'agrégats : sur des marchés
    africains où quelques capitalisations écrasent la distribution, une moyenne
    dit surtout ce que fait la plus grosse valeur du secteur. La médiane décrit
    la société typique, qui est ce qu'on cherche pour un comparable.

    Seules les sociétés complètes entrent dans le calcul.
    """
    paniers = {}
    for ident, s in societes.items():
        if s.get("visible"):
            paniers.setdefault(s["industrie"], []).append((ident, s))

    def mediane(valeurs):
        return round(statistics.median(valeurs), 4) if valeurs else None

    sortie = []
    for nom, membres in sorted(paniers.items()):
        b1 = [s["beta_1an"] for _i, s in membres]
        b3 = [s["beta_3ans"] for _i, s in membres]
        ratios = [s["dette"] / s["capitalisation"] for _i, s in membres]
        sortie.append({
            "nom": nom,
            "tickers": [i for i, _s in membres],
            "societes": len(membres),
            "beta_1an": mediane(b1),
            "beta_3ans": mediane(b3),
            "gearing": mediane(ratios),
        })
    return sortie


def indexer_par_zone(univers: dict, classer) -> tuple[dict, list]:
    """Effectifs par zone, et par industrie au sein d'une zone.

    `classer(pays)` doit rendre (continent, zone). Les sociétés d'un pays
    qu'aucune zone ne réclame sont comptées à part plutôt qu'écartées : le build
    doit pouvoir les nommer.
    """
    index, orphelins = {}, []
    for s in univers["societes"].values():
        if not s.get("visible"):
            continue  # une société incomplète ne se compte pas sur la carte
        _continent, zone = classer(s["pays"])
        if zone is None:
            orphelins.append(s["pays"])
            continue
        place = s.get("place") or "hors cote"
        seau = index.setdefault(zone, {"total": 0, "places": {}, "industries": {}})
        seau["total"] += 1
        seau["places"][place] = seau["places"].get(place, 0) + 1
        detail = seau["industries"].setdefault(s["industrie"], {"n": 0, "places": {}})
        detail["n"] += 1
        detail["places"][place] = detail["places"].get(place, 0) + 1
    return index, sorted(set(orphelins))


def construire(racine: Path, progress=None) -> dict | None:
    """Point d'entrée du build. Rend None si aucun export n'est déposé."""
    chemin = trouver_export(racine)
    if chemin is None:
        return None
    return charger(chemin, progress=progress)
