"""R201 - Erreurs en cache."""

from __future__ import annotations

from ..core import blocks as B
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register

# #N/A est frequemment un resultat de recherche assume ; les autres erreurs ne le
# sont jamais. Cette distinction pilote la confiance, pas le filtrage.
TOLERATED = {"#N/A"}


@register
class R201CachedErrors(Rule):
    """Erreurs presentes dans les valeurs en cache.

    Pour chaque cellule en erreur, le signal porte : les consommateurs de la ligne
    (donc la propagation), les cellules amont elles-memes en erreur ou nulles
    (donc la cause probable), et la formule d'une cellule jumelle quand la formule
    fautive s'ecarte de celle de ses voisines.

    Confiance : une erreur en cache est un fait, pas une heuristique ; la
    confiance mesure donc surtout la possibilite que l'erreur soit assumee.
      - 0.95 pour toute erreur autre que #N/A, 0.75 pour #N/A ;
      - +0.05 si la ligne est consommee (l'erreur se propage) ;
      - -0.20 si la cellule est isolee et sans consommateur (brouillon probable).
    """

    id = "R201"
    label = "Erreurs en cache"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        graph = ctx.graph
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            for (row, col), value in sheet.values.items():
                if not isinstance(value, str):
                    continue
                error = R.contains_error_literal(value)
                if error is None or value.strip().upper() != error:
                    continue

                formula = sheet.formula(row, col)
                ref = f"{R.index_to_col(col)}{row}"
                label = sheet.row_label(row)
                consumers = graph.consumers_of_row(sheet.name, row) if graph else []

                twin_ref, twin_formula = self._find_twin(sheet, st, row, col)
                expected = None
                if twin_formula and formula:
                    twin_row, twin_col = twin_ref
                    proposed = R.translate_formula(
                        twin_formula, twin_row, twin_col, row, col
                    )
                    if proposed != formula:
                        expected = proposed

                upstream = self._upstream_causes(snap, sheet.name, row, col, formula)

                confidence = 0.75 if error in TOLERATED else 0.95
                if consumers:
                    confidence += 0.05
                elif not upstream:
                    confidence -= 0.20

                evidence = {
                    "erreur": error,
                    "cellule": f"{sheet.name}!{ref}",
                    "formule_conforme_a_la_ligne": expected is None and bool(formula),
                    "cellules_amont_en_cause": upstream,
                    "nb_consommateurs_ligne": len(consumers),
                }
                if twin_formula:
                    evidence["cellule_jumelle"] = (
                        f"{R.index_to_col(twin_ref[1])}{twin_ref[0]}"
                    )
                    evidence["formule_jumelle"] = twin_formula

                if expected is not None:
                    note = (
                        f"{error} en cache ; la formule s'ecarte de celle de ses "
                        f"voisines de ligne, dont la transposition est proposee."
                    )
                elif upstream:
                    note = (
                        f"{error} en cache ; la formule est conforme a celle de la "
                        f"ligne, la cause est en amont ({', '.join(upstream[:3])})."
                    )
                else:
                    note = f"{error} en cache."

                out.append(
                    self.signal(
                        sheet=sheet.name,
                        refs=[ref],
                        label=label,
                        observed=formula or str(value),
                        expected=expected,
                        evidence=evidence,
                        consumers=consumers,
                        confidence=confidence,
                        note=note,
                    )
                )
        return out

    @staticmethod
    def _find_twin(sheet, st: B.SheetStructure, row: int, col: int):
        """Cellule de meme position relative dont la formule sert de reference.

        On cherche d'abord dans la ligne : les colonnes de projection d'une meme
        ligne sont des blocs paralleles par construction. La jumelle retenue est
        celle de la variante majoritaire dont la valeur n'est pas en erreur.
        """
        groups = B.row_variants(sheet, row, st.projection_cols)
        if not groups:
            return (row, col), None
        majority_cols = max(groups.values(), key=len)
        for cand_col in majority_cols:
            if cand_col == col:
                continue
            value = sheet.value(row, cand_col)
            if isinstance(value, str) and R.contains_error_literal(value):
                continue
            return (row, cand_col), sheet.formula(row, cand_col)
        return (row, col), None

    @staticmethod
    def _upstream_causes(snap, sheet_name: str, row: int, col: int, formula: str | None):
        """Cellules amont en erreur, ou nulles quand la formule divise."""
        if not formula:
            return []
        causes: list[str] = []
        divides = "/" in formula
        for ref in R.extract_refs(formula, default_sheet=sheet_name):
            target = snap.sheet(ref.sheet or sheet_name)
            if target is None:
                continue
            hi_r = min(ref.max_row, target.max_row)
            hi_c = min(ref.max_col, target.max_col)
            for r in range(ref.min_row, hi_r + 1):
                for c in range(ref.min_col, hi_c + 1):
                    value = target.value(r, c)
                    name = f"{target.name}!{R.index_to_col(c)}{r}"
                    if isinstance(value, str) and R.contains_error_literal(value):
                        causes.append(f"{name} = {value}")
                    elif divides and isinstance(value, (int, float)) and value == 0:
                        causes.append(f"{name} = 0")
                    if len(causes) >= 6:
                        return causes
        return causes
