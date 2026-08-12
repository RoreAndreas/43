"""R205 - Ancrage asymetrique des bornes d'une plage."""

from __future__ import annotations

from ..core import blocks as B
from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register


@register
class R205Anchoring(Rule):
    """Bornes d'une plage ancrees de facon asymetrique.

    Le motif `$O488:S491` — coin initial ancre en colonne, coin final relatif —
    dans une formule recopiee horizontalement neutralise silencieusement le terme
    entier : la plage ne se deplace pas, elle s'elargit depuis le coin superieur
    gauche, et lit toujours la colonne O. Le motif miroir `O488:$S491` produit
    l'effet symetrique. Aucune erreur Excel ne le signale.

    Detection : l'asymetrie d'ancrage est lue sur la reference elle-meme, puis
    **confirmee sur les faits** en observant que la largeur (ou la hauteur) de la
    plage varie d'une colonne a l'autre de la meme ligne. Une asymetrie qui ne
    produit aucune variation de forme n'est pas retenue : c'est une convention
    d'ecriture sans effet.

    Chiffrage systematique : la grandeur attendue est reconstruite en ancrant les
    deux bornes de la meme facon, puis comparee au cache sur toutes les colonnes.

    Confiance :
      - 1.00 si le chiffrage conclut `actif` **et** que la valeur en cache
        correspond exactement a ce que produit la formule telle qu'ecrite : le
        cache confirme alors que l'ecart constate est bien le terme neutralise ;
      - 0.85 si l'ecart est actif sans confirmation exacte par le cache ;
      - 0.55 si l'ecart est latent, 0.30 s'il est nul ;
      - 0.60 si le chiffrage reste indetermine, l'asymetrie de forme etant, elle,
        etablie.
    """

    id = "R205"
    label = "Ancrage asymetrique"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        graph = ctx.graph
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            if len(st.projection_cols) < 2:
                continue
            for row in st.formula_rows:
                out.extend(self._scan_row(ctx, sheet, st, row, graph))
        return out

    def _scan_row(self, ctx, sheet, st, row: int, graph):
        cols = [c for c in st.projection_cols if sheet.formula(row, c)]
        if len(cols) < 2:
            return []

        per_col_refs = {
            col: R.extract_refs(sheet.formula(row, col), default_sheet=sheet.name)
            for col in cols
        }
        n_refs = len(per_col_refs[cols[0]])
        if n_refs == 0 or any(len(v) != n_refs for v in per_col_refs.values()):
            return []

        signals = []
        for idx in range(n_refs):
            series = {col: per_col_refs[col][idx] for col in cols}
            first_ref = series[cols[0]]
            if first_ref.whole_col or first_ref.whole_row:
                continue
            col_asym = first_ref.start.col_abs != first_ref.end.col_abs
            row_asym = first_ref.start.row_abs != first_ref.end.row_abs
            if not (col_asym or row_asym):
                continue

            widths = {col: ref.width for col, ref in series.items()}
            heights = {col: ref.height for col, ref in series.items()}
            shape_varies = len(set(widths.values())) > 1 or len(set(heights.values())) > 1
            if not shape_varies:
                continue  # asymetrie sans effet de forme : pas de signal

            signal = self._emit(
                ctx, sheet, st, row, idx, series, cols, widths, heights,
                col_asym, graph,
            )
            if signal is not None:
                signals.append(signal)
        return signals

    def _emit(self, ctx, sheet, st, row, idx, series, cols, widths, heights,
              col_asym, graph):
        snap = ctx.snapshot
        base_col = cols[0]
        base_ref = series[base_col]

        def corrected_for(col: int, sheet_name=base_ref.sheet) -> R.RangeRef:
            """Plage attendue : les deux bornes ancrees de la meme facon.

            On prend la plage telle qu'elle est en premiere colonne — la ou
            l'asymetrie n'a pas encore produit d'effet — et on la transpose.
            """
            d_col = col - base_col
            return R.RangeRef(
                start=R.CellRef(base_ref.start.col + d_col, base_ref.start.row, False, base_ref.start.row_abs),
                end=R.CellRef(base_ref.end.col + d_col, base_ref.end.row, False, base_ref.end.row_abs),
                sheet=sheet_name,
            )

        def rewrite(formula: str, col: int, _i=idx):
            # `ref.sheet` vient de la formule telle qu'ecrite : le reprendre evite
            # d'ajouter un prefixe d'onglet a une reference qui n'en avait pas.
            def fn(ref: R.RangeRef, ref_idx: int):
                return corrected_for(col, ref.sheet).a1 if ref_idx == _i else None

            return R.map_refs(formula, fn)

        def zone_for_col(col: int):
            """Zone lue en trop par la formule ecrite : ce qui distingue latent de nul."""
            observed = series.get(col)
            wanted = corrected_for(col)
            if observed is None or observed.max_col <= wanted.max_col:
                return None
            return R.RangeRef(
                start=R.CellRef(observed.min_col, observed.min_row),
                end=R.CellRef(wanted.min_col - 1, observed.max_row),
                sheet=observed.sheet,
            )

        quant = Q.quantify_with_zone(
            snap, sheet.name, row, cols, rewrite, zone_for_col,
            method="les deux bornes ancrees comme en premiere colonne",
        )

        if quant.verdict == "actif":
            confidence = 1.0 if quant.cache_confirms_formula else 0.85
        elif quant.verdict == "latent":
            confidence = 0.55
        elif quant.verdict == "nul":
            confidence = 0.30
        else:
            confidence = 0.60

        axis = "colonne" if col_asym else "ligne"
        label = sheet.row_label(row)
        consumers = graph.consumers_of_row(sheet.name, row) if graph else []
        varying = "largeur" if len(set(widths.values())) > 1 else "hauteur"

        evidence = {
            "motif_ancrage": base_ref.anchor_pattern,
            "axe": axis,
            "plage_par_colonne": {
                R.index_to_col(c): series[c].a1 for c in cols[:12]
            },
            f"{varying}_par_colonne": {
                R.index_to_col(c): (widths[c] if varying == "largeur" else heights[c])
                for c in cols[:12]
            },
            "plage_attendue_par_colonne": {
                R.index_to_col(c): corrected_for(c).a1 for c in cols[:12]
            },
            **quant.to_evidence(),
        }

        observed_col = max(cols, key=lambda c: widths[c] * heights[c])
        note = (
            f"Bornes ancrees de facon asymetrique en {axis} (motif "
            f"{base_ref.anchor_pattern}) : la plage passe de "
            f"{series[cols[0]].a1} a {series[cols[-1]].a1} le long de la ligne, "
            f"donc elle s'elargit au lieu de se deplacer"
        )
        if quant.verdict == "actif":
            note += (
                f" ; ecart maximal chiffre {quant.max_abs_delta:.6g} sur "
                f"{len(quant.columns_touched)} colonne(s)"
            )
            if quant.cache_confirms_formula:
                note += ", la valeur en cache confirmant exactement la lecture"
        return self.signal(
            sheet=sheet.name,
            refs=[f"{R.index_to_col(c)}{row}" for c in (cols[0], observed_col)],
            label=label,
            observed=sheet.formula(row, observed_col) or "",
            expected=rewrite(sheet.formula(row, observed_col) or "", observed_col),
            evidence=evidence,
            consumers=consumers,
            confidence=confidence,
            note=note + ".",
        )
