"""Localisation des grandeurs par libelle, avec score de confiance.

`discover` **propose**, il ne conclut pas. Sa sortie est un mapping candidat que
`validate-mapping` doit confirmer numeriquement avant tout usage. Le score
accompagne chaque proposition pour que l'auditeur sache lesquelles relire.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from pydantic import ValidationError

from ..core import blocks as B
from ..core.loader import Snapshot
from .schema import (
    Bilan, Cascade, Immobilisations, Located, MappingModel, Periodes, Tolerances,
)


def normalise(text: str) -> str:
    """Minuscules, sans accents, ponctuation reduite a l'espace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@dataclass
class Candidate:
    """Une localisation proposee, avec ce qui a motive la proposition."""

    sheet: str
    row: int
    label: str
    score: float
    matched_on: str = ""

    def to_located(self) -> Located:
        return Located(sheet=self.sheet, row=self.row)


@dataclass
class Discovery:
    """Resultat d'une recherche : le meilleur candidat et ses concurrents."""

    key: str
    best: Candidate | None = None
    others: list[Candidate] = field(default_factory=list)

    @property
    def ambiguous(self) -> bool:
        """Vrai si un concurrent talonne le meilleur candidat."""
        if self.best is None or not self.others:
            return False
        return (self.best.score - self.others[0].score) < 0.15


# Motifs de recherche : (cle, expressions attendues, expressions rejetees).
# Les expressions sont normalisees comme les libelles.
PATTERNS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "bilan.actif_total": (("total actif", "total de l actif", "total actifs"), ("passif",)),
    "bilan.passif_total": (("total passif", "total du passif", "total passifs"), ("actif",)),
    "bilan.tresorerie": (
        ("tresorerie", "disponibilites", "cash", "banque"),
        ("variation", "flux", "nette de", "besoin"),
    ),
    "cascade.solde_cloture": (
        ("solde de cloture", "solde cloture", "tresorerie de cloture", "cash de cloture"),
        ("ouverture",),
    ),
    "cascade.solde_ouverture": (
        ("solde d ouverture", "solde ouverture", "tresorerie d ouverture"),
        ("cloture",),
    ),
    "cascade.facilite_court_terme": (
        ("facilite court terme", "facilite de tresorerie", "decouvert", "ligne court terme"),
        (),
    ),
    "cascade.reserves": (("compte de reserve", "reserve dsra", "reserves"), ()),
    "immobilisations.brut": (("immobilisations brutes", "valeur brute", "actif brut"), ()),
    "immobilisations.amortissements": (
        ("amortissements cumules", "amortissement cumule", "cumul amortissements"), ()
    ),
    "immobilisations.net": (
        ("immobilisations nettes", "valeur nette comptable", "vnc", "actif net"), ()
    ),
}

PERIOD_INDEX_PATTERNS = ("periode", "numero de periode", "no periode", "period", "n periode")
PERIOD_DATE_PATTERNS = ("date", "date de fin", "fin de periode", "echeance")


def score_label(label: str, wanted: tuple[str, ...], rejected: tuple[str, ...]) -> tuple[float, str]:
    """Score de correspondance d'un libelle, entre 0 et 1.

    1.00 pour une egalite exacte apres normalisation ; 0.80 quand l'expression
    recherchee est contenue dans le libelle, module par la longueur excedentaire ;
    0 si le libelle contient une expression rejetee. Le calcul est volontairement
    simple et lisible : un score sophistique donnerait une fausse impression de
    certitude sur une heuristique de libelle.
    """
    norm = normalise(label)
    if not norm:
        return 0.0, ""
    for bad in rejected:
        if normalise(bad) in norm:
            return 0.0, ""
    best = 0.0
    matched = ""
    for want in wanted:
        target = normalise(want)
        if not target:
            continue
        if norm == target:
            return 1.0, want
        if target in norm:
            # Plus le libelle deborde, moins la correspondance est franche.
            ratio = len(target) / len(norm)
            value = 0.55 + 0.35 * ratio
            if value > best:
                best, matched = value, want
    return best, matched


def find_rows(snap: Snapshot, key: str, sheets: list[str] | None = None) -> Discovery:
    """Cherche dans tout le classeur les lignes correspondant a une cle."""
    wanted, rejected = PATTERNS[key]
    found: list[Candidate] = []
    for sheet in snap.sheets.values():
        if sheets and sheet.name not in sheets:
            continue
        if sheet.state != "visible":
            continue
        st = B.build_structure(sheet)
        rows = set(st.formula_rows) | {r for (r, _c) in sheet.values}
        for row in sorted(rows):
            label = sheet.row_label(row)
            if not label:
                continue
            score, matched = score_label(label, wanted, rejected)
            if score <= 0:
                continue
            # Une ligne sans aucune valeur sur les colonnes de projection est un
            # titre, pas une grandeur.
            if st.projection_cols and not any(
                sheet.has_content(row, c) for c in st.projection_cols
            ):
                continue
            found.append(Candidate(sheet.name, row, label, round(score, 3), matched))
    found.sort(key=lambda c: -c.score)
    return Discovery(key=key, best=found[0] if found else None, others=found[1:6])


def guess_periods(
    snap: Snapshot, prefer_sheet: str | None = None
) -> tuple[Periodes | None, list[Discovery]]:
    """Repere l'onglet de projection et sa ligne d'index de periode.

    A defaut d'indication, l'onglet retenu est celui qui porte le plus de
    formules : dans un modele, la chronique de projection est l'objet le plus
    dense du classeur. `prefer_sheet` permet de lui substituer l'onglet ou les
    grandeurs recherchees ont effectivement ete trouvees — les colonnes de
    periode doivent etre celles des lignes qu'on va lire, pas celles d'un autre
    onglet.
    """
    if not snap.sheets:
        return None, []
    best_sheet = None
    if prefer_sheet:
        best_sheet = snap.sheet(prefer_sheet)
    if best_sheet is None:
        best_sheet = max(snap.sheets.values(), key=lambda s: len(s.formulas))
    st = B.build_structure(best_sheet)
    if not st.projection_cols:
        return None, []

    index_row = _row_matching(best_sheet, st, PERIOD_INDEX_PATTERNS)
    date_row = _row_matching(best_sheet, st, PERIOD_DATE_PATTERNS)
    if index_row is None:
        # A defaut de libelle, la ligne d'index est celle qui porte 1, 2, 3...
        index_row = _row_of_sequence(best_sheet, st)
    if index_row is None:
        return None, []

    from ..core.refs import index_to_col

    lo, hi = st.projection_cols[0], st.projection_cols[-1]
    return (
        Periodes(
            sheet=best_sheet.name,
            ligne_index=index_row,
            ligne_date=date_row,
            colonnes=f"{index_to_col(lo)}:{index_to_col(hi)}",
        ),
        [],
    )


def _row_matching(sheet, st, patterns: tuple[str, ...]) -> int | None:
    rows = sorted({r for (r, _c) in sheet.values} | set(st.formula_rows))
    best_row, best_score = None, 0.0
    for row in rows[:200]:
        score, _ = score_label(sheet.row_label(row), patterns, ())
        if score > best_score:
            best_row, best_score = row, score
    return best_row if best_score >= 0.55 else None


def _row_of_sequence(sheet, st, min_len: int = 4) -> int | None:
    """Ligne dont les valeurs forment 1, 2, 3... sur les colonnes de projection."""
    cols = st.projection_cols[:20]
    if len(cols) < min_len:
        return None
    rows = sorted({r for (r, _c) in sheet.values})
    for row in rows[:200]:
        values = [sheet.value(row, c) for c in cols]
        numbers = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(numbers) < min_len:
            continue
        if all(
            abs(numbers[i + 1] - numbers[i] - 1) < 1e-9 for i in range(len(numbers) - 1)
        ) and abs(numbers[0] - 1) < 1e-9:
            return row
    return None


def discover(snap: Snapshot) -> tuple[MappingModel | None, list[Discovery]]:
    """Propose un mapping candidat. Rien n'y est confirme.

    Les localisations proposees portent `validated=None` : `validate-mapping` doit
    passer avant que le moindre controle ne s'execute.
    """
    results: dict[str, Discovery] = {}
    for key in PATTERNS:
        results[key] = find_rows(snap, key)

    # Les colonnes de periode doivent etre celles de l'onglet ou les grandeurs
    # ont ete trouvees. Sans cela, une chronique lue sur le mauvais onglet ferait
    # echouer toute la validation numerique pour une raison inutilement obscure.
    hosts = Counter(d.best.sheet for d in results.values() if d.best is not None)
    prefer = hosts.most_common(1)[0][0] if hosts else None

    periods, discoveries = guess_periods(snap, prefer_sheet=prefer)
    if periods is None and prefer is not None:
        periods, discoveries = guess_periods(snap)
    if periods is None:
        return None, discoveries

    def located(key: str) -> Located | None:
        found = results.get(key)
        if found is None or found.best is None:
            return None
        return found.best.to_located()

    try:
        mapping = _assemble(periods, located)
    except ValidationError:
        # Aucune grandeur reconnue : mieux vaut ne rien proposer qu'un mapping
        # squelette que l'utilisateur croirait exploitable.
        return None, [d for d in results.values() if d.best is not None]
    return mapping, [d for d in results.values() if d.best is not None]


def _assemble(periods: Periodes, located) -> MappingModel:
    return MappingModel(
        periodes=periods,
        bilan=Bilan(
            actif_total=located("bilan.actif_total"),
            passif_total=located("bilan.passif_total"),
            tresorerie=located("bilan.tresorerie"),
        ),
        cascade=Cascade(
            solde_cloture=located("cascade.solde_cloture"),
            solde_ouverture=located("cascade.solde_ouverture"),
            facilite_court_terme=located("cascade.facilite_court_terme"),
            reserves=located("cascade.reserves"),
        ),
        immobilisations=Immobilisations(
            brut=located("immobilisations.brut"),
            amortissements=located("immobilisations.amortissements"),
            net=located("immobilisations.net"),
        ),
        tolerances=Tolerances(),
    )
