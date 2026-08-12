"""Phase 5 - Faisabilite du recalcul, chocs, propagation statique."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register


@dataclass
class FeasibilityVerdict:
    """Verdict rendu *avant* toute tentative de recalcul hors Excel.

    Si le verdict est negatif, le recalcul doit etre refuse avec un message
    explicite plutot que de produire des chiffres faux. C'est la seule reponse
    honnete : LibreOffice headless accepte le fichier, produit des nombres, et ne
    previent pas qu'il a mal evalue une fonction ou saute une macro.
    """

    feasible: bool = True
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported: dict[str, int] = field(default_factory=dict)
    volatile: dict[str, int] = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "recalcul_hors_excel_possible": self.feasible,
            "obstacles": self.blockers,
            "reserves": self.warnings,
            "fonctions_non_supportees": self.unsupported,
            "fonctions_volatiles": self.volatile,
            **self.details,
        }

    @property
    def message(self) -> str:
        if self.feasible:
            base = "Recalcul hors Excel envisageable."
            if self.warnings:
                base += " Sous reserve de : " + " ; ".join(self.warnings) + "."
            return base
        return (
            "Recalcul hors Excel refuse. "
            + " ; ".join(self.blockers)
            + ". Un recalcul mene malgre cela produirait des chiffres faux sans le "
            "signaler."
        )


def assess_feasibility(ctx: AuditContext) -> FeasibilityVerdict:
    """Compte les obstacles et rend un verdict, sans rien recalculer."""
    snap = ctx.snapshot
    verdict = FeasibilityVerdict()

    functions: Counter[str] = Counter()
    for sheet in snap.sheets.values():
        for formula in sheet.formulas.values():
            for name in R.extract_functions(formula):
                functions[name] += 1

    unsupported = {
        name: count for name, count in functions.items()
        if name in R.UNSUPPORTED_BY_LIBREOFFICE
    }
    volatile = {
        name: count for name, count in functions.items() if name in R.VOLATILE_FUNCTIONS
    }
    verdict.unsupported = dict(sorted(unsupported.items(), key=lambda kv: -kv[1]))
    verdict.volatile = dict(sorted(volatile.items(), key=lambda kv: -kv[1]))

    if unsupported:
        total = sum(unsupported.values())
        verdict.feasible = False
        verdict.blockers.append(
            f"{total} appel(s) a {len(unsupported)} fonction(s) que LibreOffice "
            f"headless n'evalue pas de maniere fiable "
            f"({', '.join(list(unsupported)[:6])})"
        )

    vba = snap.vba or {}
    if vba.get("has_vba"):
        verdict.feasible = False
        verdict.blockers.append(
            f"le classeur porte {len(vba.get('macros', []))} procedure(s) VBA, que "
            f"LibreOffice headless ne rejoue pas"
        )
        if vba.get("circularity_hints"):
            verdict.blockers.append(
                "des plages nommees de type Copy/Paste suggerent une boucle de "
                "resolution de circularite pilotee par macro, dont le resultat ne "
                "peut pas etre reproduit hors Excel"
            )

    if snap.calc.get("iterate") == "1":
        verdict.warnings.append(
            f"le calcul iteratif est active "
            f"(iterateCount={snap.calc.get('iterateCount', '?')}), la convergence "
            f"depend du moteur"
        )
    if volatile:
        verdict.warnings.append(
            f"{sum(volatile.values())} appel(s) a des fonctions volatiles "
            f"({', '.join(list(volatile)[:4])}) : le resultat depend de la date ou "
            f"de l'ordre de calcul"
        )
    if not snap.stats.get("has_cached_values", True):
        verdict.warnings.append(
            "aucune valeur en cache : le classeur n'a jamais ete calcule par Excel"
        )

    verdict.details = {
        "formules_totales": snap.formula_count,
        "fonctions_distinctes": len(functions),
        "macros": len((snap.vba or {}).get("macros", [])),
    }
    return verdict


@register
class R501Feasibility(Rule):
    """Testeur de faisabilite du recalcul hors Excel.

    Confiance : 0.20. Le verdict est un fait de cadrage methodologique, pas une
    anomalie du modele.
    """

    id = "R501"
    label = "Faisabilite du recalcul"
    phase = 5

    def run(self, ctx: AuditContext) -> list[Signal]:
        verdict = assess_feasibility(ctx)
        if not verdict.feasible:
            ctx.add_reserve(
                "RECALCUL_IMPOSSIBLE",
                verdict.message,
                severity="warning",
            )
        return [
            self.signal(
                sheet="(classeur)",
                refs=[],
                label="Faisabilite du recalcul hors Excel",
                observed="possible" if verdict.feasible else "refuse",
                expected=None,
                evidence=verdict.to_dict(),
                consumers=[],
                confidence=0.20,
                note=verdict.message,
            )
        ]


@register
class R502CalcProperties(Rule):
    """Etat de `calcPr` et fiabilite des valeurs en cache.

    `calcOnSave="0"` signifie que les valeurs enregistrees sont celles du dernier
    calcul volontaire de l'utilisateur, pas l'etat converge du modele. Toute
    conclusion chiffree adossee au cache en herite, d'ou une reserve automatique
    propagee dans tous les rapports.

    Confiance : 0.30 quand une reserve est emise, 0.10 sinon. Il s'agit d'un fait
    de cadrage, jamais d'une anomalie a corriger dans le modele.
    """

    id = "R502"
    label = "Proprietes de calcul"
    phase = 5

    def run(self, ctx: AuditContext) -> list[Signal]:
        calc = ctx.snapshot.calc or {}
        reserves: list[str] = []

        if calc.get("calcOnSave") == "0":
            reserves.append(
                "calcOnSave=\"0\" : les valeurs en cache sont celles du dernier calcul "
                "de l'utilisateur, pas l'etat converge du modele"
            )
        if calc.get("fullCalcOnLoad") == "1":
            reserves.append(
                "fullCalcOnLoad=\"1\" : Excel recalcule tout a l'ouverture, donc les "
                "valeurs enregistrees peuvent differer de celles qu'un lecteur verra"
            )
        if calc.get("calcMode") == "manual":
            reserves.append(
                "calcMode=\"manual\" : le classeur n'est recalcule que sur demande"
            )
        if calc.get("iterate") == "1":
            reserves.append(
                f"iterate=\"1\" : circularites resolues par iteration "
                f"(iterateCount={calc.get('iterateCount', '?')}, "
                f"iterateDelta={calc.get('iterateDelta', '?')})"
            )
        if not ctx.snapshot.stats.get("has_cached_values", True):
            reserves.append(
                "aucune valeur en cache n'accompagne les formules : tout chiffrage "
                "adosse au cache est impossible"
            )

        for i, message in enumerate(reserves):
            ctx.add_reserve(f"CALCPR_{i}", message, severity="warning")

        note = (
            "Les valeurs en cache ne peuvent pas etre tenues pour l'etat converge du "
            "modele : " + " ; ".join(reserves) + "."
            if reserves
            else "Aucune reserve tiree de calcPr : les valeurs en cache peuvent etre "
                 "tenues pour le dernier etat calcule."
        )
        return [
            self.signal(
                sheet="(classeur)",
                refs=[],
                label="Proprietes de calcul (calcPr)",
                observed=str(calc) if calc else "(calcPr absent)",
                expected=None,
                evidence={"calcPr": calc, "reserves": reserves},
                consumers=[],
                confidence=0.30 if reserves else 0.10,
                note=note,
            )
        ]


@register
class R503StaticPropagation(Rule):
    """Propagation statique d'un choc, sans recalcul.

    Le choc n'est pas evalue : on ne dispose pas d'un moteur de calcul fiable, et
    en simuler un produirait des chiffres inventes. Ce qui est calcule, c'est
    l'**etendue** de la propagation — quelles lignes, quels onglets, quelles
    sorties dependent de la grandeur choquee — pour dire ce que le choc atteint.
    Le chiffrage, lui, exige Excel.

    Confiance : 0.20, comme tout signal de cadrage.
    """

    id = "R503"
    label = "Propagation statique"
    phase = 5
    requires_graph = True

    def run(self, ctx: AuditContext) -> list[Signal]:
        shocks = ctx.options.get("shocks") or {}
        graph = ctx.graph
        if not shocks or graph is None:
            return []

        out: list[Signal] = []
        for target, amount in shocks.items():
            located = self._locate(ctx, target)
            if located is None:
                out.append(
                    self.signal(
                        sheet="(classeur)",
                        refs=[],
                        label=f"Choc « {target} »",
                        observed="cible introuvable",
                        evidence={"choc": target, "amplitude": amount},
                        consumers=[],
                        confidence=0.20,
                        note=(
                            f"La grandeur « {target} » n'a pas ete localisee : ni "
                            f"reference explicite, ni ligne portant ce libelle."
                        ),
                    )
                )
                continue
            sheet_name, row = located
            reach, sheets_hit, depth = self._reach(graph, sheet_name, row)
            out.append(
                self.signal(
                    sheet=sheet_name,
                    refs=[f"{row}:{row}"],
                    label=f"Choc « {target} » ({amount})",
                    observed=f"{len(reach)} ligne(s) atteinte(s)",
                    expected=None,
                    evidence={
                        "choc": target,
                        "amplitude": amount,
                        "ligne_choquee": f"{sheet_name}!{row}",
                        "libelle": ctx.snapshot.row_label(sheet_name, row),
                        "lignes_atteintes": len(reach),
                        "onglets_atteints": sorted(sheets_hit),
                        "profondeur_de_propagation": depth,
                        "echantillon": sorted(reach)[:60],
                        "chiffrage": (
                            "non effectue : le chiffrage d'un choc exige un recalcul, "
                            "que l'outil refuse de simuler"
                        ),
                    },
                    consumers=graph.consumers_of_row(sheet_name, row),
                    confidence=0.20,
                    note=(
                        f"Un choc sur « {target} » se propage a {len(reach)} ligne(s) "
                        f"reparties sur {len(sheets_hit)} onglet(s), sur "
                        f"{depth} niveau(x) de dependance. L'amplitude n'est pas "
                        f"chiffree : elle exige un recalcul par Excel."
                    ),
                )
            )
        return out

    @staticmethod
    def _locate(ctx: AuditContext, target: str) -> tuple[str, int] | None:
        """Resout une cible de choc : 'Onglet!A12', 'Onglet!12', ou un libelle."""
        snap = ctx.snapshot
        if "!" in target:
            sheet_name, _sep, rest = target.rpartition("!")
            sheet = snap.sheet(sheet_name)
            if sheet is None:
                return None
            ref = R.parse_ref(rest, sheet.name)
            if ref is not None:
                return sheet.name, ref.min_row
            if rest.isdigit():
                return sheet.name, int(rest)
            return None

        from ..mapping.discover import normalise

        wanted = normalise(target)
        if not wanted:
            return None
        for sheet in snap.sheets.values():
            rows = {r for (r, _c) in sheet.values} | {r for (r, _c) in sheet.formulas}
            for row in sorted(rows):
                if normalise(sheet.row_label(row)) == wanted:
                    return sheet.name, row
        return None

    @staticmethod
    def _reach(graph, sheet: str, row: int, max_depth: int = 20):
        seen = {(sheet, row)}
        frontier = [(sheet, row)]
        sheets_hit = {sheet}
        depth = 0
        while frontier and depth < max_depth:
            following = []
            for s, r in frontier:
                for name in graph.consumers_of_row(s, r, limit=500):
                    csheet, _sep, crow = name.rpartition("!")
                    key = (csheet, int(crow))
                    if key in seen:
                        continue
                    seen.add(key)
                    sheets_hit.add(csheet)
                    following.append(key)
            if not following:
                break
            frontier = following
            depth += 1
        reach = {f"{s}!{r}" for s, r in seen} - {f"{sheet}!{row}"}
        return reach, sheets_hit, depth
