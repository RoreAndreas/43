"""R204 - Glissement de recopie."""

from __future__ import annotations

from ..core import blocks as B
from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register

MIN_BLOCK_HEIGHT = 2


@register
class R204CopyDrift(Rule):
    """Plage dont les bornes progressent de +1 par ligne alors que le bloc source est fixe.

    Motif recherche : un groupe de lignes consecutives structurellement identiques
    dont chacune somme un bloc situe ailleurs dans l'onglet. Si les deux bornes de
    la plage avancent d'exactement une ligne a chaque ligne du groupe, la plage
    n'a pas ete ancree a la recopie et elle derive hors de son bloc.

    Deux gardes ecartent les glissements legitimes :
      - une plage qui contient la ligne de la formule est un calcul par ligne
        (somme horizontale, moyenne mobile), pas une derive ;
      - une derive n'est retenue que si elle franchit une frontiere structurelle,
        c'est-a-dire si elle capture une ligne de total ou sort du bloc de donnees
        contigu ou la premiere ligne du groupe pointait.

    Confiance :
      - 0.90 si la derive capture une ligne de sous-total (double comptage certain) ;
      - 0.75 si elle sort du bloc de donnees sans capturer de total ;
      - +0.05 si le chiffrage conclut `actif`, -0.30 s'il conclut `nul`,
        -0.10 s'il reste `indetermine`.
    """

    id = "R204"
    label = "Glissement de recopie"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        graph = ctx.graph
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            if not st.projection_cols:
                continue
            probe_col = st.projection_cols[0]
            for block in B.find_row_blocks(sheet, st, min_height=MIN_BLOCK_HEIGHT):
                out.extend(self._scan_block(ctx, sheet, st, block, probe_col, graph))
        return out

    def _scan_block(self, ctx, sheet, st, block: B.RowBlock, probe_col, graph):
        rows = list(block.rows)
        per_row_refs = []
        for row in rows:
            formula = sheet.formula(row, probe_col)
            if not formula:
                return []
            per_row_refs.append(R.extract_refs(formula, default_sheet=sheet.name))
        n_refs = len(per_row_refs[0])
        if n_refs == 0 or any(len(r) != n_refs for r in per_row_refs):
            return []

        signals = []
        for idx in range(n_refs):
            series = [per_row_refs[i][idx] for i in range(len(rows))]
            if not self._slides_by_one(series, rows):
                continue
            first = series[0]
            last = series[-1]
            run_lo, run_hi = B.contiguous_data_run(sheet, st, first.min_row, first.max_row)

            captured = sorted(
                r for r in range(last.min_row, last.max_row + 1)
                if r in st.total_rows and not (first.min_row <= r <= first.max_row)
            )
            escaped = last.max_row > run_hi or last.min_row < run_lo
            if not captured and not escaped:
                continue

            signals.append(
                self._emit(ctx, sheet, st, block, rows, series, idx,
                           captured, escaped, run_lo, run_hi, graph)
            )
        return [s for s in signals if s is not None]

    @staticmethod
    def _slides_by_one(series: list[R.RangeRef], rows: list[int]) -> bool:
        """Les deux bornes avancent d'exactement une ligne par ligne du groupe."""
        first = series[0]
        if first.whole_col or first.whole_row:
            return False
        if first.height < 2:
            return False
        for i, ref in enumerate(series):
            if ref.height != first.height:
                return False
            if ref.min_row != first.min_row + i or ref.max_row != first.max_row + i:
                return False
            # Une plage qui englobe la ligne de la formule est un calcul par ligne.
            if ref.min_row <= rows[i] <= ref.max_row:
                return False
        return True

    def _emit(self, ctx, sheet, st, block, rows, series, idx,
              captured, escaped, run_lo, run_hi, graph):
        snap = ctx.snapshot
        first = series[0]
        target_lo, target_hi = first.min_row, first.max_row

        # Lignes du bloc de reference qu'une ligne du groupe finit par omettre.
        omitted = sorted(
            {
                r
                for ref in series
                for r in range(target_lo, target_hi + 1)
                if not (ref.min_row <= r <= ref.max_row)
            }
        )

        def rewrite(formula: str, col: int, _i=idx, _lo=target_lo, _hi=target_hi):
            def fn(ref: R.RangeRef, ref_idx: int):
                if ref_idx != _i:
                    return None
                return R.RangeRef(
                    start=R.CellRef(ref.start.col, _lo, ref.start.col_abs, True),
                    end=R.CellRef(ref.end.col, _hi, ref.end.col_abs, True),
                    sheet=ref.sheet,
                ).a1

            return R.map_refs(formula, fn)

        # Le chiffrage porte sur les lignes reellement derivees, pas sur la premiere.
        drifted_rows = [r for r, ref in zip(rows, series) if ref.min_row != target_lo]
        quant = None
        for row in drifted_rows:
            q = Q.quantify(
                snap, sheet.name, row, st.projection_cols, rewrite,
                method="plage figee au bloc de la premiere ligne du groupe",
            )
            if quant is None or q.max_abs_delta > quant.max_abs_delta:
                quant = q
        if quant is None:
            return None

        confidence = 0.90 if captured else 0.75
        if quant.verdict == "actif":
            confidence += 0.05
        elif quant.verdict == "nul":
            confidence -= 0.30
        elif quant.verdict == "indetermine":
            confidence -= 0.10

        label = sheet.row_label(rows[0])
        consumers = []
        if graph:
            for row in rows:
                consumers.extend(graph.consumers_of_row(sheet.name, row, limit=10))
            consumers = sorted(set(consumers))[:40]

        evidence = {
            "lignes_du_groupe": f"{block.first_row}:{block.last_row}",
            "plage_par_ligne": {
                str(row): ref.a1 for row, ref in zip(rows, series)
            },
            "bloc_source_attendu": f"{target_lo}:{target_hi}",
            "bloc_de_donnees_contigu": f"{run_lo}:{run_hi}",
            "sous_totaux_captures": [
                {"ligne": r, "libelle": sheet.row_label(r)} for r in captured
            ],
            "articles_omis": [
                {"ligne": r, "libelle": sheet.row_label(r)} for r in omitted
            ],
            "sort_du_bloc": escaped,
            **quant.to_evidence(),
        }

        note_parts = [
            f"Les bornes de la plage avancent d'une ligne a chaque ligne du groupe "
            f"{block.first_row}:{block.last_row} alors que le bloc source "
            f"{target_lo}:{target_hi} est fixe"
        ]
        if captured:
            note_parts.append(
                "la derive capture le(s) sous-total(aux) "
                + ", ".join(f"ligne {c['ligne']} ({c['libelle']})" for c in evidence["sous_totaux_captures"])
            )
        if omitted:
            note_parts.append(
                "et omet " + ", ".join(f"ligne {o['ligne']} ({o['libelle']})" for o in evidence["articles_omis"][:4])
            )

        return self.signal(
            sheet=sheet.name,
            refs=[f"{block.first_row}:{block.last_row}"],
            label=label,
            observed=sheet.formula(rows[-1], st.projection_cols[0]) or "",
            expected=rewrite(sheet.formula(rows[-1], st.projection_cols[0]) or "", st.projection_cols[0]),
            evidence=evidence,
            consumers=consumers,
            confidence=confidence,
            note=" ; ".join(note_parts) + ".",
        )
