"""R206 - Somme tronquee."""

from __future__ import annotations

from ..core import blocks as B
from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register

SUMMING = {"SUM", "SUBTOTAL", "AVERAGE", "COUNT", "COUNTA", "MIN", "MAX"}


@register
class R206TruncatedSum(Rule):
    """Plage de somme qui n'epouse pas l'etendue du bloc.

    Deux controles independants sur les lignes de total :

    1. Coherence entre colonnes : le nombre de lignes sommees doit etre le meme
       d'une colonne a l'autre d'une meme ligne de total. Une colonne qui en
       somme moins que les autres est signalee.

    2. Coherence avec le bloc : la plage sommee est comparee a l'etendue reelle du
       bloc situe au-dessus, delimitee par l'en-tete et le sous-total. L'omission
       de la premiere ou de la derniere ligne du bloc est le cas typique — c'est
       aussi le plus difficile a voir a l'oeil.

    Confiance :
      - 0.85 pour une colonne isolee divergente (controle 1), 0.65 si la
        divergence touche plus d'une colonne sur trois ;
      - 0.80 pour l'omission d'une ligne de bord du bloc (controle 2) ;
      - +0.05 si le chiffrage conclut `actif`, -0.30 s'il conclut `nul`,
        -0.10 s'il reste `indetermine`.
    """

    id = "R206"
    label = "Somme tronquee"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        out: list[Signal] = []
        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            if not st.projection_cols:
                continue
            for row in sorted(st.total_rows):
                out.extend(self._cross_column(ctx, sheet, st, row))
                out.extend(self._against_block(ctx, sheet, st, row))
        return out

    # -- controle 1 : entre colonnes ---------------------------------------
    def _cross_column(self, ctx, sheet, st, row: int):
        snap = ctx.snapshot
        graph = ctx.graph
        cols = [c for c in st.projection_cols if sheet.formula(row, c)]
        if len(cols) < 3:
            return []

        heights: dict[int, int] = {}
        refs: dict[int, R.RangeRef] = {}
        for col in cols:
            ref = self._vertical_sum_ref(sheet, row, col)
            if ref is None:
                return []
            refs[col] = ref
            heights[col] = ref.height
        if len(set(heights.values())) < 2:
            return []

        counts: dict[int, list[int]] = {}
        for col, h in heights.items():
            counts.setdefault(h, []).append(col)
        majority_h, majority_cols = max(counts.items(), key=lambda kv: len(kv[1]))
        model_col = majority_cols[0]
        model_ref = refs[model_col]

        signals = []
        for h, variant_cols in counts.items():
            if h == majority_h:
                continue

            def rewrite(formula: str, col: int, _mc=model_col, _mr=model_ref):
                # L'onglet est repris de la reference telle qu'ecrite, pour ne pas
                # ajouter un prefixe a une formule qui n'en portait pas.
                def fn(ref: R.RangeRef, i: int):
                    if i != 0:
                        return None
                    return R.RangeRef(
                        start=R.CellRef(
                            _mr.start.col if _mr.start.col_abs else _mr.start.col + (col - _mc),
                            _mr.start.row, _mr.start.col_abs, _mr.start.row_abs,
                        ),
                        end=R.CellRef(
                            _mr.end.col if _mr.end.col_abs else _mr.end.col + (col - _mc),
                            _mr.end.row, _mr.end.col_abs, _mr.end.row_abs,
                        ),
                        sheet=ref.sheet,
                    ).a1

                return R.map_refs(formula, fn)

            quant = Q.quantify(
                snap, sheet.name, row, variant_cols, rewrite,
                method="plage alignee sur celle des colonnes majoritaires",
            )
            confidence = 0.85 if len(variant_cols) <= max(1, len(cols) // 3) else 0.65
            confidence += {"actif": 0.05, "nul": -0.30, "indetermine": -0.10}.get(
                quant.verdict, 0.0
            )

            missing = self._missing_rows(model_ref, refs[variant_cols[0]])
            signals.append(
                self.signal(
                    sheet=sheet.name,
                    refs=[f"{R.index_to_col(c)}{row}" for c in variant_cols],
                    label=sheet.row_label(row),
                    observed=sheet.formula(row, variant_cols[0]) or "",
                    expected=rewrite(sheet.formula(row, variant_cols[0]) or "", variant_cols[0]),
                    evidence={
                        "controle": "coherence entre colonnes",
                        "lignes_sommees_par_colonne": {
                            R.index_to_col(c): heights[c] for c in cols[:12]
                        },
                        "plage_par_colonne": {
                            R.index_to_col(c): refs[c].a1 for c in cols[:12]
                        },
                        "hauteur_majoritaire": majority_h,
                        "lignes_omises": [
                            {"ligne": r, "libelle": sheet.row_label(r)} for r in missing
                        ],
                        **quant.to_evidence(),
                    },
                    consumers=graph.consumers_of_row(sheet.name, row) if graph else [],
                    confidence=confidence,
                    note=(
                        f"La ligne de total somme {h} ligne(s) en "
                        f"{', '.join(R.index_to_col(c) for c in variant_cols)} contre "
                        f"{majority_h} sur les autres colonnes"
                        + (
                            " ; omet " + ", ".join(
                                f"ligne {m['ligne']} ({m['libelle']})" for m in
                                [{"ligne": r, "libelle": sheet.row_label(r)} for r in missing][:3]
                            )
                            if missing else ""
                        )
                        + "."
                    ),
                )
            )
        return signals

    # -- controle 2 : contre le bloc ---------------------------------------
    def _against_block(self, ctx, sheet, st, row: int):
        snap = ctx.snapshot
        graph = ctx.graph
        extent = B.data_block_above(sheet, row, st)
        if extent is None:
            return []
        block_lo, block_hi = extent
        if block_hi < block_lo:
            return []

        cols = [c for c in st.projection_cols if sheet.formula(row, c)]
        if not cols:
            return []
        probe = cols[0]
        ref = self._vertical_sum_ref(sheet, row, probe)
        if ref is None:
            return []
        if ref.min_row == block_lo and ref.max_row == block_hi:
            return []
        # On ne signale que l'omission d'une ligne de bord du bloc, cas vise par la
        # specification ; une plage plus large releve d'autres regles.
        if ref.min_row < block_lo or ref.max_row > block_hi:
            return []

        omitted = [
            r for r in range(block_lo, block_hi + 1)
            if not (ref.min_row <= r <= ref.max_row)
        ]
        if not omitted:
            return []

        def rewrite(formula: str, col: int, _lo=block_lo, _hi=block_hi):
            def fn(target: R.RangeRef, i: int):
                if i != 0:
                    return None
                return R.RangeRef(
                    start=R.CellRef(target.start.col, _lo, target.start.col_abs, target.start.row_abs),
                    end=R.CellRef(target.end.col, _hi, target.end.col_abs, target.end.row_abs),
                    sheet=target.sheet,
                ).a1

            return R.map_refs(formula, fn)

        quant = Q.quantify(
            snap, sheet.name, row, cols, rewrite,
            method="plage etendue a tout le bloc delimite par l'en-tete et le sous-total",
        )
        confidence = 0.80
        confidence += {"actif": 0.05, "nul": -0.30, "indetermine": -0.10}.get(
            quant.verdict, 0.0
        )
        edge = "premiere" if block_lo not in range(ref.min_row, ref.max_row + 1) else "derniere"

        return [
            self.signal(
                sheet=sheet.name,
                refs=[f"{R.index_to_col(c)}{row}" for c in cols[:4]],
                label=sheet.row_label(row),
                observed=sheet.formula(row, probe) or "",
                expected=rewrite(sheet.formula(row, probe) or "", probe),
                evidence={
                    "controle": "coherence avec l'etendue du bloc",
                    "plage_sommee": ref.a1,
                    "etendue_du_bloc": f"{block_lo}:{block_hi}",
                    "bord_omis": edge,
                    "lignes_omises": [
                        {"ligne": r, "libelle": sheet.row_label(r)} for r in omitted
                    ],
                    **quant.to_evidence(),
                },
                consumers=graph.consumers_of_row(sheet.name, row) if graph else [],
                confidence=confidence,
                note=(
                    f"La plage sommee {ref.a1} couvre {ref.height} ligne(s) alors que "
                    f"le bloc s'etend de {block_lo} a {block_hi} "
                    f"({block_hi - block_lo + 1} lignes) ; la {edge} ligne du bloc "
                    f"est omise."
                ),
            )
        ]

    @staticmethod
    def _vertical_sum_ref(sheet, row: int, col: int) -> R.RangeRef | None:
        """Unique plage verticale d'un agregat, si la formule en contient une seule."""
        formula = sheet.formula(row, col)
        if not formula:
            return None
        found = None
        for call in R.parse_calls(formula, default_sheet=sheet.name):
            if call.name not in SUMMING:
                continue
            for ref in call.arg_refs:
                if ref is None or ref.whole_col or ref.whole_row:
                    continue
                if ref.height > 1 and ref.width == 1:
                    if found is not None:
                        return None  # plusieurs plages : hors du cadre de la regle
                    found = ref
        if found is None:
            return None
        # La formule ne doit contenir aucune autre reference, sinon la
        # substitution d'indice 0 ne viserait pas la bonne plage.
        all_refs = R.extract_refs(formula, default_sheet=sheet.name)
        if len(all_refs) != 1 or all_refs[0].a1 != found.a1:
            return None
        return found

    @staticmethod
    def _missing_rows(model: R.RangeRef, variant: R.RangeRef) -> list[int]:
        return [
            r for r in range(model.min_row, model.max_row + 1)
            if not (variant.min_row <= r <= variant.max_row)
        ]
