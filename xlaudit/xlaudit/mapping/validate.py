"""Confirmation numerique des localisations, avant tout usage.

Regle absolue : aucun controle ne s'execute sur une localisation non validee. Une
ligne mal identifiee produit un audit faux, et un audit faux est pire que pas
d'audit — il fait perdre la confiance dans les constats justes.

La validation confirme **l'identite** d'une ligne, pas l'invariant qu'on lui fera
subir ensuite. Valider « total actif » en verifiant qu'il egale le total passif
serait circulaire : le controle de bilan n'aurait plus rien a prouver. On teste
donc des proprietes de forme — la ligne est renseignee, elle varie, elle est
calculee la ou un total doit l'etre, ses signes sont ceux de sa nature.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core import quantifier as Q
from ..core.loader import Snapshot
from .schema import Dette, Located, MappingModel

MIN_COVERAGE = 0.7

# Grandeurs dont on attend qu'elles soient calculees : un total saisi en dur sur
# toute la chronique n'est pas un total, c'est une reprise.
EXPECTED_TOTALS = {
    "bilan.actif_total",
    "bilan.passif_total",
    "immobilisations.net",
    "cascade.solde_cloture",
}

# Grandeurs qui ne peuvent pas etre negatives par nature.
EXPECTED_NON_NEGATIVE = {
    "bilan.actif_total",
    "bilan.passif_total",
    "immobilisations.brut",
    "immobilisations.net",
}


@dataclass
class ValidationResult:
    key: str
    location: str
    ok: bool
    note: str = ""
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "cle": self.key,
            "localisation": self.location,
            "valide": self.ok,
            "motif": self.note,
            **self.detail,
        }


def _series(snap: Snapshot, sheet: str, row: int, cols: list[int]) -> list[float | None]:
    return [Q.as_number(snap.value(sheet, row, c)) for c in cols]


def _coverage(values: list[float | None]) -> float:
    return (sum(1 for v in values if v is not None) / len(values)) if values else 0.0


def validate_located(
    snap: Snapshot, key: str, loc: Located, cols: list[int]
) -> ValidationResult:
    """Confirme qu'une ligne est bien celle que le mapping annonce."""
    location = f"{loc.sheet}!{loc.row}"
    sheet = snap.sheet(loc.sheet)
    if sheet is None:
        return ValidationResult(key, location, False, f"onglet introuvable : {loc.sheet}")

    values = _series(snap, sheet.name, loc.row, cols)
    coverage = _coverage(values)
    numbers = [v for v in values if v is not None]
    detail = {
        "libelle": sheet.row_label(loc.row),
        "couverture_numerique": round(coverage, 3),
        "colonnes_de_periode": len(cols),
        "premiere_valeur": numbers[0] if numbers else None,
        "derniere_valeur": numbers[-1] if numbers else None,
    }

    if coverage < MIN_COVERAGE:
        return ValidationResult(
            key, location, False,
            f"seulement {coverage:.0%} des colonnes de periode portent une valeur "
            f"numerique (minimum {MIN_COVERAGE:.0%})",
            detail,
        )
    if all(abs(v) < 1e-12 for v in numbers):
        return ValidationResult(
            key, location, False,
            "la ligne est nulle sur toute la chronique : son identification ne peut "
            "pas etre confirmee",
            detail,
        )

    if key in EXPECTED_NON_NEGATIVE and any(v < 0 for v in numbers):
        return ValidationResult(
            key, location, False,
            f"{sum(1 for v in numbers if v < 0)} periode(s) negatives sur une "
            f"grandeur qui ne peut pas l'etre",
            detail,
        )

    if key in EXPECTED_TOTALS:
        formula_cols = sum(1 for c in cols if sheet.formula(loc.row, c))
        detail["colonnes_calculees"] = formula_cols
        if formula_cols < 0.5 * len(cols):
            return ValidationResult(
                key, location, False,
                f"un total doit etre calcule : seulement {formula_cols} colonne(s) "
                f"sur {len(cols)} portent une formule",
                detail,
            )

    return ValidationResult(key, location, True, "confirmee", detail)


def validate_dette(snap: Snapshot, dette: Dette, cols: list[int]) -> ValidationResult:
    """Confirme qu'un echeancier de dette est bien un echeancier de dette.

    Proprietes de forme attendues : le capital restant du est renseigne et jamais
    negatif, les remboursements et tirages ne sont jamais negatifs, et l'encours
    final n'excede pas l'encours initial (une dette s'amortit). Ces tests
    n'anticipent pas les invariants de la phase 3, qui verifieront l'amortissement
    integral et le calcul des interets.
    """
    location = f"{dette.sheet}!{dette.nom}"
    sheet = snap.sheet(dette.sheet)
    if sheet is None:
        return ValidationResult(
            f"dettes.{dette.nom}", location, False, f"onglet introuvable : {dette.sheet}"
        )

    detail: dict = {}
    for field_name in ("crd_debut", "tirage", "remb", "interets", "crd_fin"):
        row = getattr(dette, field_name)
        if row is None:
            continue
        values = [v for v in _series(snap, sheet.name, row, cols) if v is not None]
        detail[field_name] = {
            "ligne": row,
            "libelle": sheet.row_label(row),
            "couverture": round(_coverage(_series(snap, sheet.name, row, cols)), 3),
        }
        if _coverage(_series(snap, sheet.name, row, cols)) < MIN_COVERAGE:
            return ValidationResult(
                f"dettes.{dette.nom}", location, False,
                f"{field_name} (ligne {row}) : couverture numerique insuffisante",
                detail,
            )
        if field_name in ("crd_debut", "crd_fin", "remb", "tirage") and any(
            v < -1e-9 for v in values
        ):
            return ValidationResult(
                f"dettes.{dette.nom}", location, False,
                f"{field_name} (ligne {row}) comporte des valeurs negatives",
                detail,
            )

    if dette.crd_fin is not None:
        crd = [v for v in _series(snap, sheet.name, dette.crd_fin, cols) if v is not None]
        if crd and crd[-1] > crd[0] + 1e-9:
            return ValidationResult(
                f"dettes.{dette.nom}", location, False,
                f"l'encours final ({crd[-1]:.2f}) depasse l'encours initial "
                f"({crd[0]:.2f}) : la ligne designee ne se comporte pas comme un "
                f"capital restant du",
                detail,
            )

    return ValidationResult(f"dettes.{dette.nom}", location, True, "confirmee", detail)


def validate_mapping(snap: Snapshot, mapping: MappingModel) -> list[ValidationResult]:
    """Valide toutes les localisations et **inscrit le verdict dans le mapping**.

    Les localisations rejetees portent `validated=False` ; la phase 3 les ignore
    et le journal indique quels controles ont ete sautes de ce fait.
    """
    cols = mapping.periodes.columns()
    results: list[ValidationResult] = []

    periods_sheet = snap.sheet(mapping.periodes.sheet)
    if periods_sheet is None:
        results.append(
            ValidationResult(
                "periodes", mapping.periodes.sheet, False,
                f"onglet de periodes introuvable : {mapping.periodes.sheet}",
            )
        )
        return results
    results.append(
        ValidationResult(
            "periodes",
            f"{mapping.periodes.sheet}!{mapping.periodes.ligne_index}",
            True,
            f"{len(cols)} colonnes de periode",
            {"colonnes": len(cols)},
        )
    )

    for key, loc in mapping.located_items():
        result = validate_located(snap, key, loc, cols)
        loc.validated = result.ok
        loc.validation_note = result.note
        results.append(result)

    for dette in mapping.dettes:
        result = validate_dette(snap, dette, cols)
        dette.validated = result.ok
        dette.validation_note = result.note
        results.append(result)

    return results
