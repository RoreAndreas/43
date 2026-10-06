"""
Univers de comparables, lu depuis les exports S&P Global déposés dans WACC43.

Un export par grande zone — `43 AF.xlsx`, `43 EU.xlsx`, `43 ME.xlsx`,
`43 US.xlsx`. Chacun tient en trois onglets qui partagent la même liste de
sociétés, appariés par `Entity ID` :

    Sheet1  produits, EBITDA, marge, résultat net (FY2022 à FY2025),
            bêta 1 an, bêta 3 ans, taux d'IS effectif
    Sheet2  géographie, pays, industrie, industrie primaire, description
    Sheet3  fonds propres, dette totale, capitalisation boursière

Les colonnes sont repérées par leur code S&P (ligne 4) et leur exercice
(ligne 5), pas par leur position : d'un export à l'autre, S&P ajoute ou retire
des colonnes. `43 US.xlsx` n'a pas de bêta à 3 ans, et la dette, qui ouvrait
Sheet3, y vient désormais après les fonds propres.

Seules les sociétés **complètes** alimentent la plateforme : pays, industrie,
bêtas, dette, fonds propres positifs, capitalisation, chiffre d'affaires sur
quatre exercices et résultat net sur trois. Les autres sont conservées dans
l'univers mais marquées `visible: False`, et n'entrent ni dans les médianes ni
dans les effectifs affichés.

Le bêta de chaque société est désendetté ici, à son propre levier :

    bêta désendetté = bêta / (1 + (1 − t) × dette totale / fonds propres)

`t` est le taux d'IS légal du pays de la société (Damodaran). Le taux effectif
publié par S&P est conservé à côté, dans `is_effectif`, sans entrer dans le
calcul. Le gearing est le même rapport dette totale / fonds propres comptables.
La page ré-endette ensuite la médiane du secteur au gearing retenu.

L'EBITDA est délibérément hors critère. S&P n'en publie pas pour les banques ni
les assureurs — la notion n'a pas de sens pour elles — et l'exiger ferait tomber
le secteur bancaire de 112 sociétés à 1, alors qu'il est le premier des places
africaines. Un critère qui détruit le secteur principal ne mesure plus la
complétude, il mesure le modèle comptable.

L'industrie retenue est la colonne E de Sheet2 (`IQ_INDUSTRY`), soit une
soixantaine de secteurs. La colonne F (`IQ_PRIMARY_INDUSTRY`) est plus fine mais
trop éclatée pour servir de maille de comparables.

Le fichier porte les deux bêtas cotés, à un an et à trois ans. C'est le trois ans
qui alimente le coût des fonds propres : sur des marchés peu liquides, celui à un
an bouge trop pour servir de base à un coût du capital. Un export qui ne publie
pas de bêta à 3 ans — `43 US.xlsx` — fait retenir le bêta à 1 an pour toutes
ses sociétés, et chacune le porte dans `beta_horizon`.

Piège d'unités : S&P exporte les comptes, les fonds propres et la dette en
**milliers** (en-tête `BCEAO000`) mais la capitalisation en **millions**
(`BCEAOM`). Rapporter l'une à l'autre sans conversion donne un rapport mille fois
trop élevé. Tout est donc ramené ici en millions.

Les en-têtes occupent les lignes 3 à 6 ; les données commencent ligne 7.
"""

from __future__ import annotations

import re
import statistics
from pathlib import Path

import openpyxl

# Formes juridiques et abréviations dont le point ne termine pas une phrase.
# Sans cette liste, trente pour cent des résumés s'arrêtaient sur la raison
# sociale — « Lesaka Technologies, Inc. », « Harel Mallac & Co. » — et ne
# disaient plus rien de l'activité.
_ABREVIATIONS = {
    "co", "inc", "ltd", "corp", "plc", "cie", "sa", "nv", "ag", "bhd", "pty",
    "pte", "llc", "lp", "llp", "ab", "oy", "asa", "spa", "srl", "kgaa", "gmbh",
    "jsc", "pjsc", "psc", "sas", "sarl", "bv", "kk", "tbk", "sae", "cv",
    "no", "st", "dr", "jr", "sr", "approx", "est",
}
_POINT = re.compile(r"\.(?=\s|$)")

# Une « phrase » plus courte que cela est presque sûrement un artefact
# d'abréviation qu'aucune liste ne couvrira jamais entièrement — « EL. D.
# Mouzakis S.A. » en est un. On continue alors de chercher la vraie coupure.
_PHRASE_MIN = 25

PREMIERE_LIGNE = 7
LIGNE_CODES, LIGNE_EXERCICES = 4, 5

# Exports déposés à la racine de WACC43 : « 43 AF.xlsx », « 43 EU.xlsx »…
MOTIF_EXPORTS = "43 *.xlsx"

# Taux d'IS retenu quand Damodaran n'en publie pas pour le pays de la société —
# le même que la page applique au pays valorisé dans ce cas.
TAUX_IS_DEFAUT = 0.25

# Longueur au-delà de laquelle la présentation est coupée. Voir `resume()` : la
# première phrase fait 123 caractères en médiane, et 4 % seulement atteignent ce
# plafond — il ne sert qu'à écarter les énumérations de pays à rallonge.
RESUME_MAX = 220

# Nombre de sociétés retenues pour une médiane sectorielle. Voir
# `statistiques()` : au-delà, ce sont les micro-capitalisations qui décident.
ECHANTILLON_MAX = 20
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


# S&P distingue « Wireless » et « Diversified Telecommunication Services » —
# deux Industry GICS d'un même Industry Group. La frontière n'est pas fiable
# sur les télécoms africains : Orange CI et Sonatel, deux opérateurs du même
# groupe au même modèle d'affaires, se retrouvaient de part et d'autre, tout
# comme MTN Group (Wireless) et MTN Uganda (Diversified). On remonte donc les
# deux au niveau du groupe d'industries, seule maille qui les traite pareil.
_FUSIONS_INDUSTRIE = {
    "Wireless Telecommunication Services": "Telecommunication Services",
    "Diversified Telecommunication Services": "Telecommunication Services",
}


def _industrie_canonique(industrie: str) -> str:
    return _FUSIONS_INDUSTRIE.get(industrie, industrie)


def trouver_exports(racine: Path) -> list:
    """Tous les exports `43 *.xlsx` trouvés autour du dossier fourni.

    Un fichier par grande zone — 43 AF, 43 EU, 43 ME, 43 US, et ceux à venir —
    plutôt qu'un export unique : les actualiser séparément évite de retélécharger
    vingt-cinq mille lignes américaines pour corriger une ligne africaine. Les
    anciens `comps*.xlsx` ne sont plus lus : les fusionner aux nouveaux ferait
    cohabiter deux dates d'arrêté sous un même identifiant.

    Les exports sont déposés à la racine de WACC43, alors que le build travaille
    depuis PFILES. On regarde donc le dossier donné, son parent et son
    grand-parent : un chemin trop étroit fait passer la construction pour
    réussie tout en publiant une page sans univers de comparables, ce qui s'est
    déjà produit et n'a été vu qu'en inspectant la page en ligne.
    """
    for base in (racine, racine.parent, racine.parent.parent):
        if not base.is_dir():
            continue
        trouves = sorted(base.glob(MOTIF_EXPORTS))
        if trouves:
            return trouves
    return []


def _colonnes(feuille, chemin: Path) -> "Colonnes":
    """Les colonnes d'un onglet, repérées par code S&P et exercice."""
    codes = next(feuille.iter_rows(min_row=LIGNE_CODES, max_row=LIGNE_CODES, values_only=True))
    exercices = next(feuille.iter_rows(min_row=LIGNE_EXERCICES, max_row=LIGNE_EXERCICES,
                                       values_only=True))
    index = {}
    for i, code in enumerate(codes):
        if code:
            exercice = exercices[i] if i < len(exercices) else None
            index.setdefault(str(code).strip(), {})[str(exercice or "").strip()] = i
    return Colonnes(index, f"{chemin.name} › {feuille.title}")


class Colonnes:
    """Positions d'un onglet. Un code obligatoire absent arrête la lecture en
    le nommant : une colonne manquante ne doit pas passer pour une donnée vide."""

    def __init__(self, index: dict, ou: str):
        self.index, self.ou = index, ou

    def a(self, code: str) -> bool:
        return code in self.index

    def une(self, code: str) -> int:
        if code not in self.index:
            raise ValueError(f"{self.ou} : colonne {code} absente")
        return next(iter(self.index[code].values()))

    def serie(self, code: str, exercices: list) -> dict:
        positions = self.index.get(code, {})
        manquants = [a for a in exercices if a not in positions]
        if manquants:
            raise ValueError(f"{self.ou} : {code} absent pour {', '.join(manquants)}")
        return {a: positions[a] for a in exercices}


def charger(chemin: Path, progress=None) -> dict:
    """Lit l'export et rend l'univers de comparables."""
    def dire(message):
        if progress:
            progress(message)

    dire(f"Comparables : lecture de {chemin.name}...")
    wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    try:
        c2 = _colonnes(wb["Sheet2"], chemin)
        p_nom, p_id, p_pays, p_ind, p_prim, p_desc = (c2.une(code) for code in (
            "SP_ENTITY_NAME", "SP_ENTITY_ID", "SP_COUNTRY_NAME", "IQ_INDUSTRY",
            "IQ_PRIMARY_INDUSTRY", "SP_BUSINESS_DESCRIPTION"))
        signaletique = {}
        for ligne in wb["Sheet2"].iter_rows(min_row=PREMIERE_LIGNE, values_only=True):
            nom, ident = ligne[p_nom], ligne[p_id]
            if not nom or not ident:
                continue
            pays, industrie, primaire, description = (
                ligne[p_pays], ligne[p_ind], ligne[p_prim], ligne[p_desc])
            place, code = _place_et_ticker(nom, ident)
            signaletique[str(ident)] = {
                "nom": _nom_court(nom),
                "ticker": code,
                "place": place,
                "pays": (pays or "").strip() or None,
                "industrie": _industrie_canonique((industrie or "").strip()) or None,
                "industrie_fine": (primaire or "").strip() or None,
                "description": (description or "").strip() or None,
            }

        c1 = _colonnes(wb["Sheet1"], chemin)
        ca, ebitda = c1.serie("IQ_TOTAL_REV", EXERCICES), c1.serie("IQ_EBITDA", EXERCICES)
        rn = c1.serie("IQ_NET_INC_PARENT", EXERCICES[:3])
        beta_1an = c1.une("SP_BETA1YR")
        # Sans bêta à 3 ans dans l'export, c'est le 1 an qui sert, pour toutes
        # ses sociétés : mêler les deux horizons dans un même fichier ferait
        # dépendre le bêta retenu de ce que S&P a su calculer, société par société.
        beta_3ans = c1.une("SP_BETA_3YR") if c1.a("SP_BETA_3YR") else None
        horizon = "3 ans" if beta_3ans is not None else "1 an"
        if beta_3ans is None:
            dire(f"Comparables : {chemin.name} sans bêta à 3 ans — bêta à 1 an retenu.")
        is_effectif = c1.une("IQ_EFFECT_TAX_RATE") if c1.a("IQ_EFFECT_TAX_RATE") else None
        p_id = c1.une("SP_ENTITY_ID")

        comptes = {}
        for ligne in wb["Sheet1"].iter_rows(min_row=PREMIERE_LIGNE, values_only=True):
            ident = ligne[p_id]
            if not ident:
                continue
            taux = None if is_effectif is None else _nombre(ligne[is_effectif])
            comptes[str(ident)] = {
                "ca": {a: _nombre(ligne[i]) for a, i in ca.items()},
                "ebitda": {a: _nombre(ligne[i]) for a, i in ebitda.items()},
                "rn": {a: _nombre(ligne[i]) for a, i in rn.items()},
                "beta_1an": _nombre(ligne[beta_1an]),
                "beta_3ans": None if beta_3ans is None else _nombre(ligne[beta_3ans]),
                "beta_horizon": horizon,
                # Publié en pourcentage, tel quel : S&P le donne au-delà de
                # 100 % quand le résultat avant impôt est presque nul. Conservé
                # pour un usage ultérieur, il n'entre pas dans le désendettement.
                "is_effectif": None if taux is None else taux / 100.0,
            }

        c3 = _colonnes(wb["Sheet3"], chemin)
        p_id, fp, dette, capi = (c3.une(code) for code in
                                 ("SP_ENTITY_ID", "IQ_TOTAL_EQUITY", "IQ_TOTAL_DEBT", "SP_MARKETCAP"))
        marche = {}
        for ligne in wb["Sheet3"].iter_rows(min_row=PREMIERE_LIGNE, values_only=True):
            ident = ligne[p_id]
            if not ident:
                continue
            fonds_propres, montant = _nombre(ligne[fp]), _nombre(ligne[dette])
            marche[str(ident)] = {
                # Fonds propres et dette en milliers, capitalisation en millions :
                # on ramène tout en millions pour que les rapports aient un sens.
                "fonds_propres": None if fonds_propres is None else fonds_propres / 1000.0,
                "dette": None if montant is None else montant / 1000.0,
                "capitalisation": _nombre(ligne[capi]),
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
    }


def beta_retenu(s: dict):
    """Le bêta coté qui entre dans le calcul : le 3 ans, ou le 1 an quand
    l'export de la société n'en publie pas d'autre."""
    return s.get("beta_3ans") if s.get("beta_horizon") == "3 ans" else s.get("beta_1an")


def _est_complete(s: dict) -> bool:
    """La société porte-t-elle toutes les valeurs dont la plateforme se sert ?

    Bêtas, dette et fonds propres alimentent le coût du capital ; la
    capitalisation classe l'échantillon ; chiffre d'affaires et résultat net
    alimentent l'affichage. Des fonds propres nuls ou négatifs rendent le gearing
    sans objet : la société ne peut pas être désendettée. Le taux d'IS effectif
    est hors critère — il n'entre pas dans le calcul. L'EBITDA aussi, pour la
    raison exposée en tête de module.
    """
    if not s.get("pays") or not s.get("industrie"):
        return False
    if s.get("beta_1an") is None or beta_retenu(s) is None:
        return False
    if s.get("dette") is None or not s.get("capitalisation"):
        return False
    if not (s.get("fonds_propres") or 0) > 0:
        return False
    ca = s.get("ca") or {}
    rn = s.get("rn") or {}
    if any(ca.get(a) is None for a in EXERCICES):
        return False
    if any(rn.get(a) is None for a in EXERCICES[:3]):
        return False
    return True


def taux_desendettement(societe: dict, taux_pays) -> tuple:
    """Taux d'IS qui désendette le bêta d'une société, et son origine.

    Le taux légal de son pays, pas le taux effectif publié par S&P : celui-ci
    reste dans `is_effectif`. C'est ici, et seulement ici, qu'il faudra le
    brancher le jour où on décidera de s'en servir.
    """
    return taux_pays(societe["pays"])


def desendetter(societes: dict, taux_pays) -> dict:
    """Gearing et bêta désendetté de chaque société complète, à son propre levier.

        gearing          = dette totale / fonds propres
        bêta désendetté  = bêta retenu / (1 + (1 − t) × gearing)

    Désendetter société par société, plutôt que la médiane au gearing médian,
    retire à chaque bêta le levier qui est le sien : une banque à dix fois ses
    fonds propres et une foncière à 0,3 ne portent pas le même risque financier,
    et la médiane des bêtas endettés mêlerait les deux.

    `taux_pays(pays)` rend (taux, origine). Modifie `societes` sur place ; rend
    le décompte des sociétés par origine du taux, pour le journal du build.
    """
    origines = {}
    for s in societes.values():
        if not s.get("visible"):
            continue
        taux, origine = taux_desendettement(s, taux_pays)
        gearing = s["dette"] / s["fonds_propres"]
        # Arrondis ici, une fois : la page refait la médiane des sociétés
        # retenues sur ces valeurs embarquées, et doit retomber sur celle du build.
        s["gearing"] = round(gearing, 6)
        s["is_desendettement"] = taux
        s["beta_u"] = round(beta_retenu(s) / (1 + (1 - taux) * gearing), 6)
        origines[origine] = origines.get(origine, 0) + 1
    return origines


def statistiques(membres: list) -> dict:
    """Bêtas et gearing médians d'un secteur, sur ses plus grosses valeurs.

    La médiane, et non la moyenne ni un rapport d'agrégats : une moyenne dit
    surtout ce que fait la plus grosse valeur du secteur, là où la médiane décrit
    la société typique — ce qu'on cherche pour un comparable.

    Mais la médiane de *toute* la population ne vaut pas mieux quand cette
    population est faite de micro-capitalisations qui ne s'échangent pas. Les 508
    banques nord-américaines complètes donnent un bêta médian à trois ans de
    0,32, alors que JPMorgan est à 0,90 et Bank of America à 0,98 : la médiane
    est portée par 374 établissements de moins de 760 millions d'euros, dont le
    bêta mesuré est proche de zéro faute d'être négocié. C'est exactement le
    défaut d'illiquidité qui écrase les bêtas africains, importé sur un marché où
    il est évitable.

    On retient donc les `ECHANTILLON_MAX` premières capitalisations du périmètre,
    ce qui rend 1,04 pour les banques nord-américaines et 0,92 pour les
    européennes. Un plancher de capitalisation absolu aurait le même effet sur
    ces deux marchés mais ne laisserait aucune société africaine : le classement
    par taille, lui, s'adapte à l'échelle de chaque marché et laisse l'Afrique
    inchangée, ses échantillons n'atteignant pas ce nombre.
    """
    def mediane(valeurs):
        valeurs = [v for v in valeurs if v is not None]
        return round(statistics.median(valeurs), 4) if valeurs else None

    retenus = sorted(membres, key=lambda s: -(s["capitalisation"] or 0))[:ECHANTILLON_MAX]
    return {
        # L'effectif du périmètre et l'échantillon qui produit les médianes sont
        # deux nombres différents dès que le secteur compte plus de vingt
        # sociétés. Les confondre ferait décrire une population et en chiffrer
        # une autre.
        "societes": len(membres),
        "retenues": len(retenus),
        # Le bêta qui entre dans le CMPC : désendetté société par société, voir
        # `desendetter()`. Les médianes cotées restent publiées pour la lecture.
        "beta_u": mediane([s["beta_u"] for s in retenus]),
        "beta_1an": mediane([s["beta_1an"] for s in retenus]),
        "beta_3ans": mediane([s["beta_3ans"] for s in retenus]),
        # Sociétés de l'échantillon dont le bêta retenu est le 1 an, faute de
        # 3 ans dans leur export : la page le signale.
        "horizon_1an": sum(1 for s in retenus if s.get("beta_horizon") == "1 an"),
        "gearing": mediane([s["gearing"] for s in retenus]),
        # Conservé pour un usage ultérieur ; n'entre pas dans le calcul.
        "is_effectif": mediane([s.get("is_effectif") for s in retenus]),
        # Somme et non médiane : la capitalisation ne sert pas au calcul, elle
        # dit le poids de l'échantillon. Elle porte donc sur exactement les
        # sociétés qui produisent les médianes ci-dessus.
        "capitalisation": round(sum(s["capitalisation"] for s in retenus), 1),
    }


def secteurs_par_perimetre(societes: dict, classer) -> dict:
    """Statistiques de chaque secteur, à quatre échelles emboîtées.

    Le CMPC se calcule sur la zone retenue. Mais l'univers est mince : sur les
    cent vingt-six couples zone x secteur, quarante pour cent ne comptent aucune
    société et un tiers n'en compte qu'une. Une médiane sur une seule société
    n'est pas une médiane, c'est cette société.

    On publie donc quatre échelles — place, zone, continent, univers — et la
    page prend la plus étroite qui atteigne le seuil, en écrivant laquelle a
    servi. Choisir à la construction figerait ce repli sans que l'utilisateur
    le voie. La place est la plus étroite des quatre : c'est celle que
    l'utilisateur vise explicitement en verrouillant le cadrage sur une bourse
    précise, plutôt que la laisser à la médiane de toute la zone.
    """
    paniers = {"univers": {}, "continents": {}, "zones": {}, "places": {}}
    for s in societes.values():
        if not s.get("visible"):
            continue
        nom = s["industrie"]
        continent, zone = classer(s["pays"])
        paniers["univers"].setdefault(nom, []).append(s)
        if continent:
            paniers["continents"].setdefault(nom, {}).setdefault(continent, []).append(s)
        if zone:
            paniers["zones"].setdefault(nom, {}).setdefault(zone, []).append(s)
        if s.get("place"):
            paniers["places"].setdefault(nom, {}).setdefault(s["place"], []).append(s)

    sortie = {}
    for nom, membres in sorted(paniers["univers"].items()):
        sortie[nom] = {
            "univers": statistiques(membres),
            "continents": {c: statistiques(m)
                           for c, m in sorted(paniers["continents"].get(nom, {}).items())},
            "zones": {z: statistiques(m)
                      for z, m in sorted(paniers["zones"].get(nom, {}).items())},
            "places": {p: statistiques(m)
                       for p, m in sorted(paniers["places"].get(nom, {}).items())},
        }
    return sortie


def payload_page(univers: dict, classer) -> dict:
    """Les sociétés visibles, allégées pour être embarquées dans la page.

    C'est la seule source de comparables de la page : décomptes du cadrage,
    médianes du CMPC et cartes de l'onglet Sociétés en sortent toutes.

    Deux précautions qui ne se voient pas dans le résultat :

    - **Unités.** Produits, EBITDA et résultat net sont exportés en milliers
      (`BCEAO000`), la capitalisation en millions (`BCEAOM`). Tout est ramené
      ici en millions, faute de quoi la même page afficherait deux échelles
      sans le dire.

    Les descriptions ne sont embarquées que sous forme de première phrase : voir
    `resume()`. Intégrales, elles pesaient sept mégaoctets sur dix, et la page
    doit rester un fichier unique que le navigateur analyse d'un bloc.

    - **Zone.** Elle est calculée ici, par le `classer` qui produit aussi les
      effectifs du cadrage. La déduire côté navigateur à partir du pays
      supposerait que tout pays coté soit connu de Damodaran : le Malawi et la
      Gambie ne le sont pas, et leurs quatorze sociétés auraient été comptées
      sans jamais pouvoir être listées.
    """
    def millions(valeur):
        return None if valeur is None else round(valeur / 1000.0, 1)

    def resume(texte, nom=None):
        """La première phrase de la description S&P, coupée si besoin.

        Les descriptions font mille caractères en moyenne et montent à cinq
        mille : embarquées telles quelles pour près de sept mille sociétés, elles
        pesaient à elles seules les deux tiers du jeu de données. Leur première
        phrase dit pourtant l'essentiel — ce que fait la société et où — pour un
        sixième du poids.

        Encore faut-il trouver la fin de cette phrase. Prise naïvement au premier
        point suivi d'un espace, elle tombait sur la forme juridique pour trente
        pour cent des sociétés : « Lesaka Technologies, Inc. » et rien d'autre.

        On ne retire pas le nom de la société bien qu'il figure déjà sur la
        carte : l'ôter laisse une phrase sans sujet, qui se lit plus mal qu'une
        redite de trois mots.

        Aucune liste d'abréviations ne couvrira toutes les raisons sociales —
        « Drugs Mfg. Co. », « Holdings PTV. Ltd. », « Communications. (K.S.C.P) »
        sont arrivées avec l'export Moyen-Orient. Quand la description s'ouvre
        sur le nom de la société, les points qu'il contient sont donc ignorés.
        """
        if not texte:
            return None
        propre = " ".join(texte.split())
        nom_propre = " ".join(str(nom or "").split())
        tete = len(nom_propre) if nom_propre and propre.startswith(nom_propre) else 0
        for point in _POINT.finditer(propre):
            if point.end() <= tete:
                continue
            debut = propre.rfind(" ", 0, point.start()) + 1
            mot = propre[debut:point.start()].lower().strip("(),;:\"'")
            # Une initiale, un sigle pointé, une forme juridique : on passe.
            if len(mot) <= 1 or "." in mot or mot in _ABREVIATIONS:
                continue
            if point.end() < _PHRASE_MIN:
                continue
            propre = propre[: point.end()]
            break
        if len(propre) <= RESUME_MAX:
            return propre
        return propre[:RESUME_MAX].rsplit(" ", 1)[0].rstrip(" ,;:.") + "…"


    sortie = {}
    for ident, s in univers["societes"].items():
        if not s.get("visible"):
            continue
        continent, zone = classer(s["pays"])
        ca, ebitda, rn = s.get("ca") or {}, s.get("ebitda") or {}, s.get("rn") or {}
        sortie[ident] = {
            "nom": s["nom"],
            "ticker": s["ticker"],
            "place": s["place"],
            "pays": s["pays"],
            "continent": continent,
            "zone": zone,
            "industrie": s["industrie"],
            "activite": s.get("industrie_fine"),
            "presentation": resume(s.get("description"), s["nom"]),
            "beta_1an": s.get("beta_1an"),
            "beta_3ans": s.get("beta_3ans"),
            "beta_horizon": s.get("beta_horizon"),
            "beta_u": s.get("beta_u"),
            "capitalisation": round(s["capitalisation"], 1),
            "dette": round(s["dette"], 1),
            "fonds_propres": round(s["fonds_propres"], 1),
            "gearing": s.get("gearing"),
            "is_desendettement": s.get("is_desendettement"),
            "is_effectif": None if s.get("is_effectif") is None else round(s["is_effectif"], 5),
            # Exercices en clair : le gabarit indexe les séries par année.
            "annees": [int(a[2:]) for a in reversed(EXERCICES)],
            "ca": {a[2:]: millions(ca.get(a)) for a in EXERCICES},
            "ebitda": {a[2:]: millions(ebitda.get(a)) for a in EXERCICES},
            "rn": {a[2:]: millions(rn.get(a)) for a in EXERCICES[:3]},
        }
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


def construire(racine: Path, taux_pays, progress=None) -> dict | None:
    """Point d'entrée du build : fusionne tous les exports déposés, puis
    désendette le bêta de chaque société complète.

    Rend None si aucun n'est trouvé. Les sociétés sont appariées par `Entity ID`,
    identifiant S&P global : un même titre présent dans deux exports n'est donc
    compté qu'une fois, et la fusion reste sûre quand les périmètres se
    recouvrent — ce que fait l'export « Moyen-Orient » face à l'export
    « Afrique » sur l'Égypte.

    `taux_pays(pays)` rend le taux d'IS légal du pays et son origine : voir
    `desendetter()`.
    """
    chemins = trouver_exports(racine)
    if not chemins:
        return None

    societes, sources, doublons = {}, [], 0
    for chemin in chemins:
        bloc = charger(chemin, progress=progress)
        doublons += len(set(bloc["societes"]) & set(societes))
        societes.update(bloc["societes"])
        sources.append(chemin.name)

    origines = desendetter(societes, taux_pays)

    if progress:
        visibles = sum(1 for s in societes.values() if s["visible"])
        recouvrement = f", {doublons} en double" if doublons else ""
        progress(f"Comparables : {len(sources)} export(s) fusionné(s) — "
                 f"{visibles} sociétés complètes sur {len(societes)}{recouvrement}.")
        if origines.get("défaut"):
            progress(f"Comparables : {origines['défaut']} société(s) sans taux d'IS "
                     f"Damodaran pour leur pays — désendettées à {TAUX_IS_DEFAUT:.0%}.")
    return {"source": ", ".join(sources), "societes": societes}


def taux_pays_damodaran(pays_damodaran: dict, nom_damodaran):
    """Fonction `taux_pays` adossée au jeu de données Damodaran.

    `pays_damodaran` : l'entrée `pays` du jeu de données, où chaque pays porte
    son taux d'IS sous `tax` quand Damodaran en publie un. `nom_damodaran`
    ramène l'orthographe S&P (« USA », « Türkiye ») à celle de Damodaran.
    """
    def taux(pays):
        entree = pays_damodaran.get(nom_damodaran(pays)) or {}
        if entree.get("tax") is not None:
            return entree["tax"], "pays"
        return TAUX_IS_DEFAUT, "défaut"
    return taux
