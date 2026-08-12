"""R202 - Valeurs en dur dans une ligne de formules."""

from __future__ import annotations

import datetime as _dt

from ..core import blocks as B
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register

# Une ligne n'est une « ligne de projection » que si elle est majoritairement
# calculee. En deca, c'est une ligne d'entree : ses constantes sont normales.
MIN_FORMULA_SHARE = 0.6
MIN_FORMULA_CELLS = 3


@register
class R202Hardcoded(Rule):
    """Constante numerique isolee dans une plage de formules homogene.

    Sont exclus : les lignes d'entree (majoritairement constantes), les colonnes
    hors chronique de projection (unites, commentaires), les colonnes de bord
    (initialisation, synthese), les dates et les textes.

    Confiance :
      - 0.60 de base ;
      - +0.25 si le libelle de la ligne contient « controle », « ctrl », « check »
        ou equivalent : une valeur en dur y neutralise le controle lui-meme ;
      - +0.10 si la constante est isolee au milieu de la chronique ;
      - -0.25 si elle se trouve sur une colonne de bord ;
      - -0.15 si plusieurs constantes coexistent (convention de saisie plausible).
    """

    id = "R202"
    label = "Valeurs en dur"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        graph = ctx.graph
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            if not st.projection_cols:
                continue
            for row in st.formula_rows:
                cols = [c for c in st.projection_cols if sheet.has_content(row, c)]
                if len(cols) < MIN_FORMULA_CELLS:
                    continue
                formula_cols = [c for c in cols if sheet.formula(row, c)]
                const_cols = [
                    c for c in cols
                    if not sheet.formula(row, c) and _is_hard_number(sheet.value(row, c))
                ]
                if not const_cols:
                    continue
                if len(formula_cols) / len(cols) < MIN_FORMULA_SHARE:
                    continue  # ligne d'entree : ses constantes ne sont pas des anomalies

                groups = B.row_variants(sheet, row, formula_cols)
                majority_cols = max(groups.values(), key=len)
                majority_col = majority_cols[0]
                majority_formula = sheet.formula(row, majority_col)
                label = sheet.row_label(row)
                control_word = B.label_matches(label, B.CONTROL_WORDS)
                consumers = graph.consumers_of_row(sheet.name, row) if graph else []

                for col in const_cols:
                    confidence = 0.60
                    if control_word:
                        confidence += 0.25
                    if st.is_edge_column(col):
                        confidence -= 0.25
                    else:
                        confidence += 0.10
                    if len(const_cols) > 1:
                        confidence -= 0.15

                    value = sheet.value(row, col)
                    expected = R.translate_formula(
                        majority_formula, row, majority_col, row, col
                    )
                    out.append(
                        self.signal(
                            sheet=sheet.name,
                            refs=[f"{R.index_to_col(col)}{row}"],
                            label=label,
                            observed=repr(value),
                            expected=expected,
                            evidence={
                                "valeur_en_dur": value,
                                "colonnes_de_la_ligne": len(cols),
                                "colonnes_calculees": len(formula_cols),
                                "colonnes_en_dur": [
                                    R.index_to_col(c) for c in const_cols
                                ],
                                "formule_majoritaire": majority_formula,
                                "colonne_de_bord": st.is_edge_column(col),
                                "libelle_de_controle": control_word,
                            },
                            consumers=consumers,
                            confidence=confidence,
                            note=(
                                f"Constante {value!r} en {R.index_to_col(col)}{row} dans "
                                f"une ligne calculee sur {len(formula_cols)} des "
                                f"{len(cols)} colonnes renseignees"
                                + (
                                    f" ; le libelle porte « {control_word} »."
                                    if control_word
                                    else "."
                                )
                            ),
                        )
                    )
        return out


def _is_hard_number(value) -> bool:
    """Une valeur en dur est un nombre saisi, pas un texte ni une date."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return False
    return isinstance(value, (int, float))
