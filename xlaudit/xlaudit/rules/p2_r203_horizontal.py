"""R203 - Coherence horizontale des formules d'une ligne."""

from __future__ import annotations

from ..core import blocks as B
from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register


@register
class R203Horizontal(Rule):
    """Variantes minoritaires de formule sur une meme ligne.

    Les formules de la ligne sont normalisees en R1C1 puis groupees : deux
    colonnes portant la meme formule recopiee tombent dans le meme groupe. Les
    groupes minoritaires sont signales, avec la formule majoritaire transposee a
    la colonne concernee comme correction proposee.

    Confiance, ponderee par la position comme le veut la specification :
      - 0.85 si la variante occupe au plus 20 % des colonnes de la ligne,
        0.60 jusqu'a 40 %, 0.35 au-dela (a parts egales, « majoritaire » ne veut
        plus dire grand-chose) ;
      - -0.35 si toutes les colonnes de la variante sont des colonnes de bord :
        premiere colonne d'initialisation et derniere colonne de synthese
        different legitimement ;
      - +0.10 si la variante est isolee au milieu de la chronique, entouree des
        deux cotes par la formule majoritaire : c'est le motif de la retouche
        ponctuelle oubliee.
    """

    id = "R203"
    label = "Coherence horizontale"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        graph = ctx.graph
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            if len(st.projection_cols) < 3:
                continue
            for row in st.formula_rows:
                groups = B.row_variants(sheet, row, st.projection_cols)
                if len(groups) < 2:
                    continue
                total_cols = sum(len(v) for v in groups.values())
                majority_key, majority_cols = max(groups.items(), key=lambda kv: len(kv[1]))
                majority_col = majority_cols[0]
                majority_formula = sheet.formula(row, majority_col)
                label = sheet.row_label(row)
                consumers = graph.consumers_of_row(sheet.name, row) if graph else []

                for key, cols in groups.items():
                    if key == majority_key:
                        continue
                    share = len(cols) / total_cols
                    confidence = 0.85 if share <= 0.2 else (0.60 if share <= 0.4 else 0.35)
                    all_edge = all(st.is_edge_column(c) for c in cols)
                    if all_edge:
                        confidence -= 0.35
                    elif self._is_surrounded(cols, majority_cols):
                        confidence += 0.10

                    observed = sheet.formula(row, cols[0])
                    expected = R.translate_formula(
                        majority_formula, row, majority_col, row, cols[0]
                    )
                    deltas = self._value_gap(snap, sheet.name, row, cols)

                    out.append(
                        self.signal(
                            sheet=sheet.name,
                            refs=[f"{R.index_to_col(c)}{row}" for c in cols],
                            label=label,
                            observed=observed,
                            expected=expected,
                            evidence={
                                "colonnes_variante": [R.index_to_col(c) for c in cols],
                                "colonnes_majoritaires": [
                                    R.index_to_col(c) for c in majority_cols
                                ],
                                "part_variante": round(share, 3),
                                "r1c1_variante": key,
                                "r1c1_majoritaire": majority_key,
                                "formule_majoritaire": majority_formula,
                                "colonnes_de_bord": all_edge,
                                "valeurs_en_cache": deltas,
                            },
                            consumers=consumers,
                            confidence=confidence,
                            note=(
                                f"{len(cols)} colonne(s) sur {total_cols} portent une "
                                f"structure de formule differente du reste de la ligne"
                                + (" (colonnes de bord)." if all_edge else ".")
                            ),
                        )
                    )
        return out

    @staticmethod
    def _is_surrounded(cols: list[int], majority_cols: list[int]) -> bool:
        """Variante encadree des deux cotes par la formule majoritaire."""
        if not majority_cols:
            return False
        lo, hi = min(cols), max(cols)
        return any(c < lo for c in majority_cols) and any(c > hi for c in majority_cols)

    @staticmethod
    def _value_gap(snap, sheet: str, row: int, cols: list[int]) -> dict:
        """Valeurs en cache des colonnes en variante : de quoi juger l'effet."""
        out = {}
        for col in cols[:8]:
            value = Q.as_number(snap.value(sheet, row, col))
            out[f"{R.index_to_col(col)}{row}"] = value
        return out
