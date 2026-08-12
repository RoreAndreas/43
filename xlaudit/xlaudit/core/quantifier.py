"""Chiffreur d'ecart : composant transverse appele par R204 a R208.

Sans chiffrage, ces regles ne produisent que du bruit. Une plage mal bornee n'est
un fait interessant que si l'on sait *de combien* elle fausse le resultat, *sur
quelles colonnes*, et si l'ecart est actif aujourd'hui ou seulement latent.

Methode : on reconstruit la grandeur sur **toutes** les colonnes de projection en
remplacant la plage fautive par la plage attendue, puis on compare au cache.

L'evaluation est volontairement restreinte a la forme dominante des lignes de
total d'un modele financier : une somme algebrique de termes, chaque terme etant
un nombre, une reference, ou un agregat simple sur une plage. Toute formule qui
sort de ce cadre rend un verdict `indetermine` plutot qu'un chiffre faux. C'est
le meme principe que le testeur de faisabilite : mieux vaut refuser de chiffrer
que produire un montant invente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import refs as R
from .loader import Snapshot

ABS_TOL = 1e-6

# Agregats dont la valeur se reconstitue a partir des seules valeurs en cache.
_AGGREGATES = {
    "SUM": lambda xs: sum(xs),
    "AVERAGE": lambda xs: (sum(xs) / len(xs)) if xs else None,
    "MIN": lambda xs: min(xs) if xs else None,
    "MAX": lambda xs: max(xs) if xs else None,
    "COUNT": lambda xs: float(len(xs)),
}


def as_number(value: Any) -> float | None:
    """Convertit une valeur en cache en nombre, ou rend None.

    Les booleens comptent pour 1/0 comme dans Excel ; les textes et les erreurs
    ne sont pas des nombres et interrompent le chiffrage.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def range_numbers(snap: Snapshot, ref: R.RangeRef, default_sheet: str) -> list[float]:
    """Valeurs numeriques en cache d'une plage, dans l'ordre de lecture."""
    sheet = snap.sheet(ref.sheet or default_sheet)
    if sheet is None:
        return []
    out: list[float] = []
    hi_r = min(ref.max_row, sheet.max_row)
    hi_c = min(ref.max_col, sheet.max_col)
    for row in range(ref.min_row, hi_r + 1):
        for col in range(ref.min_col, hi_c + 1):
            num = as_number(sheet.value(row, col))
            if num is not None:
                out.append(num)
    return out


def range_is_populated(snap: Snapshot, ref: R.RangeRef, default_sheet: str) -> bool:
    """Vrai si la plage contient au moins une cellule non vide.

    Distingue le `latent` du `nul` : une plage vide ne pourra jamais rien
    changer, une plage peuplee de zeros le pourra des que le modele bougera.
    """
    sheet = snap.sheet(ref.sheet or default_sheet)
    if sheet is None:
        return False
    hi_r = min(ref.max_row, sheet.max_row)
    hi_c = min(ref.max_col, sheet.max_col)
    for row in range(ref.min_row, hi_r + 1):
        for col in range(ref.min_col, hi_c + 1):
            if sheet.has_content(row, col):
                return True
    return False


class Unevaluable(Exception):
    """La formule sort du cadre reconstituable. On refuse de chiffrer."""


def evaluate(snap: Snapshot, sheet: str, formula: str, _depth: int = 0) -> float:
    """Reconstitue la valeur d'une formule a partir des valeurs en cache.

    Portee volontairement etroite : somme algebrique de termes, chaque terme
    etant un nombre, une reference simple, ou un agregat (SUM, AVERAGE, MIN, MAX,
    COUNT) sur des plages et des nombres. Leve `Unevaluable` sinon.
    """
    if _depth > 6:
        raise Unevaluable("imbrication trop profonde")
    text = formula[1:] if formula.startswith("=") else formula
    terms = R.top_level_terms("=" + text)
    if not terms:
        raise Unevaluable("la formule n'est pas une somme algebrique de termes")
    if len(terms) == 1:
        return _term_value(snap, sheet, terms[0][1], _depth)
    total = 0.0
    for sign, term in terms:
        value = _term_value(snap, sheet, term, _depth)
        total += value if sign == "+" else -value
    return total


def _term_value(snap: Snapshot, sheet: str, text: str, depth: int) -> float:
    text = text.strip()
    if not text:
        raise Unevaluable("terme vide")

    if text.startswith("-"):
        return -_term_value(snap, sheet, text[1:], depth)
    if text.startswith("+"):
        return _term_value(snap, sheet, text[1:], depth)
    if _is_number(text):
        return float(text)
    return _non_number(snap, sheet, text, depth)


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def _non_number(snap: Snapshot, sheet: str, text: str, depth: int) -> float:
    ref = R.parse_ref(text, sheet)
    if ref is not None:
        if ref.is_single:
            num = as_number(snap.value(ref.sheet or sheet, ref.start.row, ref.start.col))
            if num is None:
                # Une cellule vide vaut zero dans une somme Excel.
                target = snap.sheet(ref.sheet or sheet)
                if target is not None and not target.has_content(ref.start.row, ref.start.col):
                    return 0.0
                raise Unevaluable(f"valeur non numerique en {ref.a1}")
            return num
        raise Unevaluable(f"plage nue hors agregat : {ref.a1}")

    calls = R.parse_calls(text, default_sheet=sheet)
    if not calls:
        raise Unevaluable(f"terme non reconstituable : {text}")
    # L'appel enveloppant est celui de profondeur nulle ; il doit couvrir tout le terme.
    outer = [c for c in calls if c.depth == 0]
    if len(outer) != 1 or not text.upper().startswith(outer[0].raw_name.upper() + "("):
        raise Unevaluable(f"terme non reconstituable : {text}")
    call = outer[0]
    fn = _AGGREGATES.get(call.name)
    if fn is None:
        raise Unevaluable(f"fonction hors perimetre du chiffreur : {call.name}")

    values: list[float] = []
    for arg, ref in zip(call.args, call.arg_refs):
        if ref is not None:
            values.extend(range_numbers(snap, ref, sheet))
        elif _is_number(arg):
            values.append(float(arg))
        else:
            values.append(_term_value(snap, sheet, arg, depth + 1))
    result = fn(values)
    if result is None:
        raise Unevaluable(f"{call.name} sans valeur")
    return float(result)


@dataclass
class ColumnDelta:
    """Chiffrage sur une colonne de projection."""

    col: int
    ref: str
    cached: float | None = None
    observed: float | None = None
    intended: float | None = None
    delta: float | None = None
    status: str = "indetermine"  # ok | ecart | indetermine

    def to_dict(self) -> dict:
        return {
            "colonne": R.index_to_col(self.col),
            "ref": self.ref,
            "cache": self.cached,
            "recalcul_formule_ecrite": self.observed,
            "recalcul_formule_attendue": self.intended,
            "ecart": self.delta,
            "statut": self.status,
        }


@dataclass
class Quantification:
    """Verdict chiffre d'un ecart de plage.

    `verdict` vaut :
      - `actif`       : l'ecart est non nul aujourd'hui, le resultat est faux ;
      - `latent`      : l'ecart est nul mais la zone en cause est peuplee, donc
                        l'erreur produira un effet des que ces cellules bougeront ;
      - `nul`         : la zone en cause est vide, aucun effet possible en l'etat ;
      - `indetermine` : la formule sort du cadre reconstituable, aucun chiffre
                        n'est avance.
    """

    verdict: str = "indetermine"
    columns: list[ColumnDelta] = field(default_factory=list)
    max_abs_delta: float = 0.0
    max_rel_delta: float = 0.0
    columns_touched: list[str] = field(default_factory=list)
    cache_confirms_formula: bool = False
    method: str = ""
    reason: str = ""

    @property
    def n_evaluated(self) -> int:
        return sum(1 for c in self.columns if c.delta is not None)

    def to_evidence(self) -> dict:
        return {
            "chiffrage": self.verdict,
            "ecart_max_absolu": self.max_abs_delta,
            "ecart_max_relatif": self.max_rel_delta,
            "colonnes_touchees": self.columns_touched,
            "colonnes_chiffrees": self.n_evaluated,
            "colonnes_analysees": len(self.columns),
            "cache_confirme_la_formule": self.cache_confirms_formula,
            "methode": self.method,
            "detail_colonnes": [c.to_dict() for c in self.columns],
            **({"motif_indetermine": self.reason} if self.reason else {}),
        }


def quantify(
    snap: Snapshot,
    sheet: str,
    row: int,
    cols: list[int],
    rewrite,
    method: str = "",
    tol: float = ABS_TOL,
) -> Quantification:
    """Chiffre l'ecart sur toutes les colonnes de projection d'une ligne.

    `rewrite(formula, col)` rend la formule corrigee pour cette colonne, ou None
    si la colonne n'est pas concernee. Pour chaque colonne on reconstitue la
    grandeur avec la formule ecrite et avec la formule attendue, et on compare
    les deux ; le cache sert de controle de la lecture.
    """
    q = Quantification(method=method)
    reasons: set[str] = set()

    for col in cols:
        formula = snap.formula(sheet, row, col)
        if not formula:
            continue
        cd = ColumnDelta(col=col, ref=f"{R.index_to_col(col)}{row}")
        cd.cached = as_number(snap.value(sheet, row, col))
        corrected = rewrite(formula, col)
        if corrected is None or corrected == formula:
            cd.status = "ok"
            q.columns.append(cd)
            continue
        try:
            cd.observed = evaluate(snap, sheet, formula)
            cd.intended = evaluate(snap, sheet, corrected)
        except Unevaluable as exc:
            cd.status = "indetermine"
            reasons.add(str(exc))
            q.columns.append(cd)
            continue
        cd.delta = cd.intended - cd.observed
        cd.status = "ecart" if abs(cd.delta) > tol else "ok"
        q.columns.append(cd)

    deltas = [c for c in q.columns if c.delta is not None]
    if not deltas:
        q.verdict = "indetermine"
        q.reason = "; ".join(sorted(reasons)) or "aucune colonne reconstituable"
        return q

    # Le cache confirme la lecture si, sur les colonnes chiffrees, la valeur
    # enregistree correspond a ce que donne la formule telle qu'ecrite.
    checked = [c for c in deltas if c.cached is not None and c.observed is not None]
    q.cache_confirms_formula = bool(checked) and all(
        abs(c.cached - c.observed) <= max(tol, abs(c.observed) * 1e-9) for c in checked
    )

    q.max_abs_delta = max(abs(c.delta) for c in deltas)
    q.max_rel_delta = max(
        (abs(c.delta) / abs(c.intended)) if c.intended else 0.0 for c in deltas
    )
    q.columns_touched = [c.ref for c in deltas if abs(c.delta) > tol]

    # `nul` par defaut : seul `quantify_with_zone` peut requalifier en `latent`,
    # car lui seul connait la zone qui differe entre formule ecrite et attendue.
    q.verdict = "actif" if q.columns_touched else "nul"
    if reasons:
        q.reason = "; ".join(sorted(reasons))
    return q


def quantify_with_zone(
    snap: Snapshot,
    sheet: str,
    row: int,
    cols: list[int],
    rewrite,
    zone_for_col,
    method: str = "",
    tol: float = ABS_TOL,
) -> Quantification:
    """Comme `quantify`, mais qualifie `latent` / `nul` avec la zone en cause.

    `zone_for_col(col)` rend la plage qui differe entre formule ecrite et formule
    attendue. Si cette zone est peuplee alors que l'ecart est nul, l'erreur est
    latente : elle mordra des que ces cellules cesseront d'etre nulles.
    """
    q = quantify(snap, sheet, row, cols, rewrite, method=method, tol=tol)
    if q.verdict not in ("nul", "latent"):
        return q
    for col in cols:
        zone = zone_for_col(col)
        if zone is not None and range_is_populated(snap, zone, sheet):
            q.verdict = "latent"
            return q
    q.verdict = "nul"
    return q
