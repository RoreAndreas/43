"""R208 - Somme heterogene : nombre de termes variable selon la colonne."""

from __future__ import annotations

from ..core import blocks as B
from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register


@register
class R208HeterogeneousSum(Rule):
    """Nombre de termes additionnes variable d'une colonne a l'autre.

    Une ligne de synthese doit agreger les memes composantes sur toute la
    chronique. Une colonne qui additionne un terme de plus ou de moins que ses
    voisines revele un ajout ponctuel jamais recopie.

    Le signal identifie les blocs sources des termes en trop et interroge le
    graphe pour dire si l'un d'eux est **deja agrege** par un autre terme de la
    meme formule : c'est la signature du double comptage.

    Confiance :
      - 0.80 pour une colonne isolee divergente, 0.60 si la divergence porte sur
        plus d'un tiers des colonnes ;
      - +0.15 si un terme en trop est deja compris dans un autre terme
        (double comptage etabli par le graphe) ;
      - +0.05 si le chiffrage conclut `actif`, -0.25 s'il conclut `nul`.
    """

    id = "R208"
    label = "Somme heterogene"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        out: list[Signal] = []
        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            if len(st.projection_cols) < 3:
                continue
            for row in st.formula_rows:
                out.extend(self._scan_row(ctx, sheet, st, row))
        return out

    def _scan_row(self, ctx, sheet, st, row: int):
        snap = ctx.snapshot
        graph = ctx.graph
        cols = [c for c in st.projection_cols if sheet.formula(row, c)]
        if len(cols) < 3:
            return []

        term_counts: dict[int, int] = {}
        term_map: dict[int, list[tuple[str, str]]] = {}
        for col in cols:
            terms = R.top_level_terms(sheet.formula(row, col))
            if len(terms) < 2:
                return []  # pas une somme de termes : hors du cadre de la regle
            term_counts[col] = len(terms)
            term_map[col] = terms
        if len(set(term_counts.values())) < 2:
            return []

        by_count: dict[int, list[int]] = {}
        for col, n in term_counts.items():
            by_count.setdefault(n, []).append(col)
        majority_n, majority_cols = max(by_count.items(), key=lambda kv: len(kv[1]))
        model_col = majority_cols[0]

        signals = []
        for n, variant_cols in by_count.items():
            if n == majority_n:
                continue
            probe = variant_cols[0]
            extra, missing = self._term_diff(
                term_map[probe], term_map[model_col], row, probe, model_col
            )
            double = self._double_counted(ctx, sheet, row, probe, term_map[probe])

            def rewrite(formula: str, col: int, _mc=model_col, _row=row):
                model_formula = sheet.formula(_row, _mc)
                if not model_formula:
                    return None
                return R.translate_formula(model_formula, _row, _mc, _row, col)

            quant = Q.quantify(
                snap, sheet.name, row, variant_cols, rewrite,
                method="formule alignee sur celle des colonnes majoritaires",
            )
            confidence = 0.80 if len(variant_cols) <= max(1, len(cols) // 3) else 0.60
            if double:
                confidence += 0.15
            confidence += {"actif": 0.05, "nul": -0.25}.get(quant.verdict, 0.0)

            signals.append(
                self.signal(
                    sheet=sheet.name,
                    refs=[f"{R.index_to_col(c)}{row}" for c in variant_cols],
                    label=sheet.row_label(row),
                    observed=sheet.formula(row, probe) or "",
                    expected=rewrite(sheet.formula(row, probe) or "", probe),
                    evidence={
                        "termes_par_colonne": {
                            R.index_to_col(c): term_counts[c] for c in cols[:12]
                        },
                        "nombre_majoritaire_de_termes": majority_n,
                        "termes_en_trop": extra,
                        "termes_manquants": missing,
                        "blocs_sources": self._sources(sheet, term_map[probe]),
                        "double_comptage": double,
                        **quant.to_evidence(),
                    },
                    consumers=graph.consumers_of_row(sheet.name, row) if graph else [],
                    confidence=confidence,
                    note=(
                        f"{n} termes additionnes en "
                        f"{', '.join(R.index_to_col(c) for c in variant_cols)} contre "
                        f"{majority_n} sur les autres colonnes"
                        + (
                            f" ; {double[0]['explication']}"
                            if double else ""
                        )
                        + "."
                    ),
                )
            )
        return signals

    @staticmethod
    def _term_diff(variant, model, row, variant_col, model_col):
        """Termes en trop et manquants, compares apres transposition de colonne."""
        def normalise(terms, col):
            out = []
            for sign, text in terms:
                ref = R.parse_ref(text)
                out.append(f"{sign}{ref.min_row if ref else text}")
            return out

        v = normalise(variant, variant_col)
        m = normalise(model, model_col)
        extra = [t for t in v if t not in m]
        missing = [t for t in m if t not in v]
        return extra, missing

    @staticmethod
    def _sources(sheet, terms) -> list[dict]:
        """Lignes citees par les termes, avec leur libelle."""
        out = []
        for sign, text in terms:
            ref = R.parse_ref(text, sheet.name)
            if ref is None:
                out.append({"terme": text, "ligne": None, "libelle": ""})
                continue
            out.append(
                {
                    "terme": text,
                    "ligne": ref.min_row,
                    "libelle": sheet.row_label(ref.min_row),
                    "signe": sign,
                }
            )
        return out

    @staticmethod
    def _double_counted(ctx, sheet, row: int, col: int, terms) -> list[dict]:
        """Termes dont la ligne est deja agregee par un autre terme de la formule.

        Le graphe de lignes repond directement a la question : si la ligne du
        terme A figure parmi les precedents de la ligne du terme B, alors B
        contient deja A et les additionner compte deux fois la meme grandeur.
        """
        graph = ctx.graph
        if graph is None:
            return []
        rows = []
        for sign, text in terms:
            ref = R.parse_ref(text, sheet.name)
            if ref is not None and ref.is_single:
                rows.append((ref.min_row, text))
        out = []
        for target_row, target_text in rows:
            precedents = set(graph.precedents_of_row(sheet.name, target_row, limit=200))
            for other_row, other_text in rows:
                if other_row == target_row:
                    continue
                if f"{sheet.name}!{other_row}" in precedents:
                    out.append(
                        {
                            "terme_agregeant": target_text,
                            "terme_deja_compris": other_text,
                            "explication": (
                                f"la ligne {target_row} "
                                f"({sheet.row_label(target_row)}) agrege deja la ligne "
                                f"{other_row} ({sheet.row_label(other_row)}), "
                                f"les additionner compte deux fois la meme grandeur"
                            ),
                        }
                    )
        return out
