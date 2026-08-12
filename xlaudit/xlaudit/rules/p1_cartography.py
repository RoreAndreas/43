"""Phase 1 - Cartographie du classeur.

La cartographie ne cherche pas d'anomalie : elle etablit ce qu'il y a dans le
classeur. Ses signaux sont des faits de structure, avec une confiance basse par
construction — ce sont des elements de contexte, pas des suspicions.
"""

from __future__ import annotations

from collections import Counter

from ..core import blocks as B
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register


@register
class R101Inventory(Rule):
    """Inventaire des onglets, des fonctions et des noms definis.

    Confiance : 0.10 sur tous les signaux d'inventaire. Ce ne sont pas des
    anomalies mais des faits de cadrage, et les melanger au tri des suspicions
    n'aurait pas de sens.
    """

    id = "R101"
    label = "Cartographie du classeur"
    phase = 1

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        out: list[Signal] = []

        functions: Counter[str] = Counter()
        volatile: Counter[str] = Counter()
        externals: Counter[str] = Counter()
        for sheet in snap.sheets.values():
            for (_row, _col), formula in sheet.formulas.items():
                for name in R.extract_functions(formula):
                    functions[name] += 1
                    if name in R.VOLATILE_FUNCTIONS:
                        volatile[name] += 1
                for ref in R.extract_refs(formula, default_sheet=sheet.name):
                    if ref.sheet and ref.sheet.startswith("["):
                        externals[ref.sheet] += 1

        out.append(
            self.signal(
                sheet="(classeur)",
                refs=[],
                label="Inventaire",
                observed=f"{len(snap.sheets)} onglet(s), {snap.formula_count} formule(s)",
                evidence={
                    "onglets": [
                        {
                            "nom": s.name,
                            "etat": s.state,
                            "formules": len(s.formulas),
                            "valeurs": len(s.values),
                            "etendue": f"{s.min_row}:{s.max_row} x "
                                       f"{R.index_to_col(s.min_col)}:{R.index_to_col(s.max_col)}",
                        }
                        for s in sorted(snap.sheets.values(), key=lambda x: x.index)
                    ],
                    "total_formules": snap.formula_count,
                    "fonctions_les_plus_frequentes": functions.most_common(25),
                    "fonctions_distinctes": len(functions),
                    "fonctions_volatiles": dict(volatile),
                    "liens_externes": dict(externals),
                },
                consumers=[],
                confidence=0.10,
                note=(
                    f"{len(snap.sheets)} onglet(s), {snap.formula_count} formule(s), "
                    f"{len(functions)} fonction(s) distinctes."
                ),
            )
        )

        out.extend(self._defined_names(ctx))
        out.extend(self._structure(ctx))
        out.extend(self._vba(ctx))
        out.extend(self._cycles(ctx))
        return out

    def _defined_names(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        names = snap.defined_names
        if not names:
            return []
        global_names = [n for n in names if n.scope is None]
        local_names = [n for n in names if n.scope is not None]
        broken = [n for n in names if R.contains_error_literal(n.refers_to)]
        return [
            self.signal(
                sheet="(classeur)",
                refs=[],
                label="Noms definis",
                observed=f"{len(names)} nom(s)",
                evidence={
                    "portee_globale": len(global_names),
                    "portee_feuille": len(local_names),
                    "masques": sum(1 for n in names if n.hidden),
                    "noms_en_erreur": [
                        {"nom": n.name, "portee": n.scope, "cible": n.refers_to}
                        for n in broken
                    ],
                    "detail": [
                        {"nom": n.name, "portee": n.scope, "cible": n.refers_to}
                        for n in names[:200]
                    ],
                },
                consumers=[],
                confidence=0.10,
                note=(
                    f"{len(names)} nom(s) defini(s) : {len(global_names)} a portee "
                    f"globale, {len(local_names)} a portee feuille"
                    + (f", dont {len(broken)} en erreur." if broken else ".")
                ),
            )
        ]

    def _structure(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        out = []
        for sheet in snap.sheets.values():
            if not sheet.formulas:
                continue
            st = B.build_structure(sheet)
            if not st.projection_cols:
                continue
            out.append(
                self.signal(
                    sheet=sheet.name,
                    refs=[],
                    label="Structure de l'onglet",
                    observed=(
                        f"{len(st.projection_cols)} colonne(s) de projection, "
                        f"{len(st.formula_rows)} ligne(s) calculee(s)"
                    ),
                    evidence={
                        "colonnes_de_projection": (
                            f"{R.index_to_col(st.first_col)}:{R.index_to_col(st.last_col)}"
                        ),
                        "nombre_de_colonnes": len(st.projection_cols),
                        "lignes_calculees": len(st.formula_rows),
                        "lignes_de_total": sorted(st.total_rows)[:80],
                        "zone_de_libelles": (
                            f"A:{R.index_to_col(sheet.label_max_col)}"
                        ),
                        "etat": sheet.state,
                    },
                    consumers=[],
                    confidence=0.10,
                    note=(
                        f"Chronique de {len(st.projection_cols)} colonne(s) "
                        f"({R.index_to_col(st.first_col)} a {R.index_to_col(st.last_col)}), "
                        f"{len(st.total_rows)} ligne(s) de total."
                    ),
                )
            )
        return out

    def _vba(self, ctx: AuditContext) -> list[Signal]:
        vba = ctx.snapshot.vba or {}
        if not vba.get("has_vba"):
            return []
        hints = vba.get("circularity_hints") or []
        if hints:
            ctx.add_reserve(
                "VBA_CIRCULARITE",
                "Le classeur comporte des macros manipulant des plages nommees de type "
                f"Copy/Paste ({', '.join(hints[:6])}), motif d'une boucle de resolution "
                "de circularite. Les valeurs en cache dependent de l'execution de ces "
                "macros et ne sont pas reproductibles hors Excel.",
                severity="warning",
            )
        return [
            self.signal(
                sheet="(classeur)",
                refs=[],
                label="Code VBA",
                observed=f"{len(vba.get('modules', []))} module(s)",
                evidence=vba,
                consumers=[],
                confidence=0.10,
                note=(
                    f"{len(vba.get('modules', []))} module(s) VBA, "
                    f"{len(vba.get('macros', []))} procedure(s)"
                    + (
                        f" ; plages evoquant une boucle de circularite : "
                        f"{', '.join(hints[:6])}."
                        if hints else "."
                    )
                ),
            )
        ]

    def _cycles(self, ctx: AuditContext) -> list[Signal]:
        graph = ctx.graph
        if graph is None:
            return []
        cycles = graph.cycles()
        temporal = graph.temporal_recurrences()
        self_refs = graph.self_referencing_rows()
        if not cycles and not self_refs and not temporal:
            return []
        return [
            self.signal(
                sheet="(classeur)",
                refs=[],
                label="Circularites",
                observed=(
                    f"{len(cycles)} composante(s) circulaire(s), "
                    f"{len(self_refs)} auto-reference(s)"
                ),
                evidence={
                    "composantes": [c[:20] for c in cycles[:10]],
                    "auto_references": [f"{s}!{r}" for s, r in self_refs[:40]],
                    "recurrences_temporelles": [c[:20] for c in temporal[:10]],
                    "note_recurrences": (
                        "Les recurrences temporelles enchainent une periode a la "
                        "precedente (ouverture = cloture precedente). Elles ne sont "
                        "pas des circularites et sont listees a part."
                    ),
                    "calcul_iteratif_active": ctx.snapshot.calc.get("iterate") == "1",
                    "iterations_declarees": ctx.snapshot.calc.get("iterateCount"),
                },
                consumers=[],
                confidence=0.10,
                note=(
                    f"{len(cycles)} groupe(s) de lignes en dependance circulaire, "
                    f"{len(self_refs)} ligne(s) auto-referencee(s), et "
                    f"{len(temporal)} recurrence(s) temporelle(s) de periode a periode."
                ),
            )
        ]
