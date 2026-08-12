"""Phase 3 - Bouclages pilotes par mapping.

Les dix invariants. Chacun ne s'execute que sur des localisations **validees
numeriquement** : une ligne mal identifiee produirait un audit faux. Les
controles sautes faute de localisation validee sont declares dans l'evidence du
signal de synthese, pas passes sous silence.

Confiance : un bouclage est une identite comptable, pas une heuristique. Un ecart
constate est un fait ; la confiance sert seulement a distinguer l'ecart
significatif du residu numerique. Elle vaut 0.95 quand l'ecart depasse largement
la tolerance, et decroit a mesure qu'il s'en approche.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register

MAX_DETAIL = 30


@dataclass
class Series:
    """Une grandeur lue sur la chronique de projection."""

    key: str
    sheet: str
    row: int
    label: str
    cols: list[int]
    values: list[float | None]

    def at(self, i: int) -> float | None:
        return self.values[i] if 0 <= i < len(self.values) else None

    @property
    def ref(self) -> str:
        return f"{self.sheet}!{self.row}"


def _confidence(max_gap: float, tol: float) -> float:
    """Ecart franc contre residu numerique.

    Un ecart de plusieurs ordres de grandeur au-dessus de la tolerance ne peut
    pas etre un artefact d'arrondi ; un ecart qui l'effleure, si.
    """
    if tol <= 0:
        return 0.95 if max_gap > 0 else 0.0
    ratio = max_gap / tol
    if ratio >= 100:
        return 0.95
    if ratio >= 10:
        return 0.85
    if ratio >= 2:
        return 0.70
    return 0.55


class TiesEngine:
    """Execute les invariants et collecte les signaux."""

    def __init__(self, ctx: AuditContext, rule: Rule) -> None:
        self.ctx = ctx
        self.rule = rule
        self.snap = ctx.snapshot
        self.mapping = ctx.mapping
        self.cols = self.mapping.periodes.columns()
        self.periods = self._period_labels()
        self.skipped: list[str] = []

    # -- lecture -----------------------------------------------------------
    def _period_labels(self) -> list[str]:
        per = self.mapping.periodes
        out = []
        for i, col in enumerate(self.cols):
            index = self.snap.value(per.sheet, per.ligne_index, col)
            if index is None and per.ligne_date:
                index = self.snap.value(per.sheet, per.ligne_date, col)
            out.append(str(index) if index is not None else R.index_to_col(col))
        return out

    def series(self, key: str, loc) -> Series | None:
        """Lit une grandeur, en refusant toute localisation non validee."""
        if loc is None:
            return None
        if loc.validated is not True:
            self.skipped.append(
                f"{key} ({loc.sheet}!{loc.row}) : localisation non validee"
                + (f" — {loc.validation_note}" if loc.validation_note else "")
            )
            return None
        sheet = self.snap.sheet(loc.sheet)
        if sheet is None:
            self.skipped.append(f"{key} : onglet {loc.sheet} introuvable")
            return None
        return Series(
            key=key,
            sheet=sheet.name,
            row=loc.row,
            label=sheet.row_label(loc.row),
            cols=self.cols,
            values=[Q.as_number(sheet.value(loc.row, c)) for c in self.cols],
        )

    def row_series(self, sheet_name: str, row: int, key: str) -> Series | None:
        sheet = self.snap.sheet(sheet_name)
        if sheet is None:
            return None
        return Series(
            key=key, sheet=sheet.name, row=row, label=sheet.row_label(row),
            cols=self.cols,
            values=[Q.as_number(sheet.value(row, c)) for c in self.cols],
        )

    # -- emission ----------------------------------------------------------
    def breach_signal(
        self,
        check: str,
        title: str,
        left: Series,
        right: Series | None,
        gaps: list[tuple[int, float]],
        tol: float,
        note: str,
        extra: dict | None = None,
    ) -> Signal | None:
        if not gaps:
            return None
        max_gap = max(abs(g) for _i, g in gaps)
        detail = [
            {
                "periode": self.periods[i],
                "colonne": R.index_to_col(self.cols[i]),
                "gauche": left.at(i),
                "droite": right.at(i) if right else None,
                "ecart": gap,
            }
            for i, gap in gaps[:MAX_DETAIL]
        ]
        consumers = (
            self.ctx.graph.consumers_of_row(left.sheet, left.row)
            if self.ctx.graph else []
        )
        evidence = {
            "controle": check,
            "grandeur_gauche": f"{left.ref} ({left.label})",
            "grandeur_droite": f"{right.ref} ({right.label})" if right else None,
            "tolerance": tol,
            "periodes_en_ecart": len(gaps),
            "periodes_analysees": len(self.cols),
            "ecart_maximal": max_gap,
            "premiere_periode_en_ecart": self.periods[gaps[0][0]],
            "detail": detail,
            **(extra or {}),
        }
        return self.rule.signal(
            sheet=left.sheet,
            refs=[f"{left.row}:{left.row}"] + ([f"{right.row}:{right.row}"] if right else []),
            label=title,
            observed=f"{left.label} = {left.at(gaps[0][0])}",
            expected=(f"{right.label} = {right.at(gaps[0][0])}" if right else None),
            evidence=evidence,
            consumers=consumers,
            confidence=_confidence(max_gap, tol),
            note=note,
        )

    # -- les dix invariants -------------------------------------------------
    def check_bilan(self) -> list[Signal]:
        """1. Actif total = passif total, periode par periode."""
        actif = self.series("bilan.actif_total", self.mapping.bilan.actif_total)
        passif = self.series("bilan.passif_total", self.mapping.bilan.passif_total)
        if actif is None or passif is None:
            return []
        tol = self.mapping.tolerances.bilan
        gaps = self._diff(actif, passif, tol)
        signal = self.breach_signal(
            "bilan", "Equilibre du bilan", actif, passif, gaps, tol,
            f"L'actif et le passif different sur {len(gaps)} periode(s) ; "
            f"ecart maximal {max((abs(g) for _i, g in gaps), default=0):.6g} "
            f"pour une tolerance de {tol:g}.",
        )
        return [signal] if signal else []

    def check_cascade_vs_bilan(self) -> list[Signal]:
        """2. Solde de cloture de la cascade = tresorerie du bilan."""
        cloture = self.series("cascade.solde_cloture", self.mapping.cascade.solde_cloture)
        treso = self.series("bilan.tresorerie", self.mapping.bilan.tresorerie)
        if cloture is None or treso is None:
            return []
        tol = self.mapping.tolerances.cascade
        gaps = self._diff(cloture, treso, tol)
        signal = self.breach_signal(
            "cascade_vs_bilan", "Cascade de tresorerie contre bilan",
            cloture, treso, gaps, tol,
            f"Le solde de cloture de la cascade s'ecarte de la tresorerie du bilan "
            f"sur {len(gaps)} periode(s).",
        )
        return [signal] if signal else []

    def check_continuite(self) -> list[Signal]:
        """3. Solde d'ouverture d'une periode = solde de cloture de la precedente."""
        ouverture = self.series("cascade.solde_ouverture", self.mapping.cascade.solde_ouverture)
        cloture = self.series("cascade.solde_cloture", self.mapping.cascade.solde_cloture)
        if ouverture is None or cloture is None:
            return []
        tol = self.mapping.tolerances.continuite
        gaps = []
        for i in range(1, len(self.cols)):
            a, b = ouverture.at(i), cloture.at(i - 1)
            if a is None or b is None:
                continue
            if abs(a - b) > tol:
                gaps.append((i, a - b))
        signal = self.breach_signal(
            "continuite", "Continuite ouverture / cloture",
            ouverture, cloture, gaps, tol,
            f"Le solde d'ouverture ne reprend pas le solde de cloture de la periode "
            f"precedente sur {len(gaps)} periode(s) : la chronique est rompue.",
        )
        return [signal] if signal else []

    def check_dettes(self) -> list[Signal]:
        """4. Amortissement integral et 5. interets = CRD x taux."""
        out: list[Signal] = []
        for dette in self.mapping.dettes:
            if dette.validated is not True:
                self.skipped.append(
                    f"dettes.{dette.nom} : localisation non validee"
                    + (f" — {dette.validation_note}" if dette.validation_note else "")
                )
                continue
            out.extend(self._check_amortissement(dette))
            out.extend(self._check_interets(dette))
        return out

    def _check_amortissement(self, dette) -> list[Signal]:
        if dette.crd_fin is None:
            return []
        crd = self.row_series(dette.sheet, dette.crd_fin, f"dettes.{dette.nom}.crd_fin")
        if crd is None:
            return []
        values = [v for v in crd.values if v is not None]
        if not values:
            return []
        tol = self.mapping.tolerances.amortissement
        final = values[-1]
        if abs(final) <= tol:
            return []
        return [
            self.rule.signal(
                sheet=crd.sheet,
                refs=[f"{crd.row}:{crd.row}"],
                label=f"Amortissement integral — {dette.nom}",
                observed=f"CRD final = {final:.6g}",
                expected="CRD final = 0",
                evidence={
                    "controle": "amortissement_integral",
                    "dette": dette.nom,
                    "ligne_crd_fin": crd.ref,
                    "crd_final": final,
                    "crd_initial": values[0],
                    "tolerance": tol,
                    "part_non_amortie": (final / values[0]) if values[0] else None,
                },
                consumers=(
                    self.ctx.graph.consumers_of_row(crd.sheet, crd.row)
                    if self.ctx.graph else []
                ),
                confidence=_confidence(abs(final), tol),
                note=(
                    f"Le capital restant du de « {dette.nom} » vaut {final:.6g} a la "
                    f"derniere periode : la dette n'est pas integralement amortie sur "
                    f"l'horizon du modele."
                ),
            )
        ]

    def _check_interets(self, dette) -> list[Signal]:
        if dette.interets is None or dette.crd_debut is None or dette.taux_periode is None:
            return []
        interets = self.row_series(dette.sheet, dette.interets, f"dettes.{dette.nom}.interets")
        crd = self.row_series(dette.sheet, dette.crd_debut, f"dettes.{dette.nom}.crd_debut")
        if interets is None or crd is None:
            return []
        tol_rel = self.mapping.tolerances.interets_relatif
        gaps = []
        for i in range(len(self.cols)):
            observed, base = interets.at(i), crd.at(i)
            if observed is None or base is None:
                continue
            expected = base * dette.taux_periode
            if abs(expected) < 1e-12:
                continue
            if abs(observed - expected) / abs(expected) > tol_rel:
                gaps.append((i, observed - expected))
        if not gaps:
            return []
        max_gap = max(abs(g) for _i, g in gaps)
        return [
            self.rule.signal(
                sheet=interets.sheet,
                refs=[f"{interets.row}:{interets.row}", f"{crd.row}:{crd.row}"],
                label=f"Interets = CRD x taux — {dette.nom}",
                observed=f"interets = {interets.at(gaps[0][0])}",
                expected=(
                    f"CRD x taux = "
                    f"{(crd.at(gaps[0][0]) or 0) * dette.taux_periode:.6g}"
                ),
                evidence={
                    "controle": "interets_crd_taux",
                    "dette": dette.nom,
                    "taux_periode": dette.taux_periode,
                    "tolerance_relative": tol_rel,
                    "periodes_en_ecart": len(gaps),
                    "ecart_maximal": max_gap,
                    "detail": [
                        {
                            "periode": self.periods[i],
                            "crd_debut": crd.at(i),
                            "interets_constates": interets.at(i),
                            "interets_attendus": (crd.at(i) or 0) * dette.taux_periode,
                            "ecart": gap,
                        }
                        for i, gap in gaps[:MAX_DETAIL]
                    ],
                },
                consumers=(
                    self.ctx.graph.consumers_of_row(interets.sheet, interets.row)
                    if self.ctx.graph else []
                ),
                confidence=0.85 if len(gaps) > 1 else 0.70,
                note=(
                    f"Les interets de « {dette.nom} » s'ecartent de CRD x taux "
                    f"({dette.taux_periode:g}) sur {len(gaps)} periode(s) ; ecart "
                    f"maximal {max_gap:.6g}."
                ),
            )
        ]

    def check_emplois_ressources(self) -> list[Signal]:
        """6. Total des emplois = total des ressources."""
        if not self.mapping.emplois or not self.mapping.ressources:
            return []
        emplois = [self.series(f"emplois[{i}]", loc) for i, loc in enumerate(self.mapping.emplois)]
        ressources = [
            self.series(f"ressources[{i}]", loc) for i, loc in enumerate(self.mapping.ressources)
        ]
        emplois = [s for s in emplois if s is not None]
        ressources = [s for s in ressources if s is not None]
        if not emplois or not ressources:
            return []
        tol = self.mapping.tolerances.emplois_ressources
        gaps = []
        for i in range(len(self.cols)):
            a = sum(s.at(i) or 0.0 for s in emplois)
            b = sum(s.at(i) or 0.0 for s in ressources)
            if abs(a - b) > tol:
                gaps.append((i, a - b))
        if not gaps:
            return []
        return [
            self.rule.signal(
                sheet=emplois[0].sheet,
                refs=[f"{s.row}:{s.row}" for s in emplois[:4]],
                label="Emplois = ressources",
                observed=f"emplois = {sum(s.at(gaps[0][0]) or 0.0 for s in emplois):.6g}",
                expected=f"ressources = {sum(s.at(gaps[0][0]) or 0.0 for s in ressources):.6g}",
                evidence={
                    "controle": "emplois_ressources",
                    "lignes_emplois": [f"{s.ref} ({s.label})" for s in emplois],
                    "lignes_ressources": [f"{s.ref} ({s.label})" for s in ressources],
                    "tolerance": tol,
                    "periodes_en_ecart": len(gaps),
                    "ecart_maximal": max(abs(g) for _i, g in gaps),
                    "detail": [
                        {"periode": self.periods[i], "ecart": gap} for i, gap in gaps[:MAX_DETAIL]
                    ],
                },
                consumers=[],
                confidence=_confidence(max(abs(g) for _i, g in gaps), tol),
                note=(
                    f"Le total des emplois s'ecarte du total des ressources sur "
                    f"{len(gaps)} periode(s)."
                ),
            )
        ]

    def check_periode_annuel(self) -> list[Signal]:
        """7. Coherence entre la vue par periode et la vue annuelle.

        Un flux annuel doit egaler la somme des flux de ses periodes ; un stock
        annuel doit egaler le stock de la derniere periode de l'annee. Les deux
        regles different, et les confondre est une source classique d'erreur.
        """
        annuel = self.mapping.annuel
        if annuel is None or (not annuel.flux and not annuel.stocks):
            return []
        per = self.mapping.periodes
        index_row = per.ligne_index
        years: dict[int, list[int]] = {}
        for i, col in enumerate(self.cols):
            value = Q.as_number(self.snap.value(per.sheet, index_row, col))
            if value is None:
                continue
            years.setdefault(int(value), []).append(i)
        if not years:
            self.skipped.append("periode/annuel : index de periode illisible")
            return []

        tol = self.mapping.tolerances.periode_annuel
        out: list[Signal] = []
        annual_cols = _annual_columns(annuel)
        for kind, rows in (("flux", annuel.flux), ("stocks", annuel.stocks)):
            for name, period_row in rows.items():
                signal = self._compare_annual(
                    kind, name, period_row, years, annual_cols, tol
                )
                if signal:
                    out.append(signal)
        return out

    def _compare_annual(self, kind, name, period_row, years, annual_cols, tol):
        annuel = self.mapping.annuel
        period_series = self.row_series(self.mapping.periodes.sheet, period_row, name)
        if period_series is None or not annual_cols:
            return None
        annual_sheet = self.snap.sheet(annuel.sheet)
        if annual_sheet is None:
            return None
        annual_row = annuel.flux.get(name) if kind == "flux" else annuel.stocks.get(name)
        if annual_row is None:
            return None

        gaps = []
        for pos, (year, idxs) in enumerate(sorted(years.items())):
            if pos >= len(annual_cols):
                break
            values = [period_series.at(i) for i in idxs]
            values = [v for v in values if v is not None]
            if not values:
                continue
            aggregated = sum(values) if kind == "flux" else values[-1]
            reference = Q.as_number(annual_sheet.value(annual_row, annual_cols[pos]))
            if reference is None:
                continue
            if abs(aggregated - reference) > tol:
                gaps.append((year, aggregated, reference, aggregated - reference))
        if not gaps:
            return None

        rule_text = (
            "la somme des periodes de l'annee" if kind == "flux"
            else "le stock de la derniere periode de l'annee"
        )
        return self.rule.signal(
            sheet=period_series.sheet,
            refs=[f"{period_row}:{period_row}"],
            label=f"Coherence periode / annuel — {name}",
            observed=f"agrege periodes = {gaps[0][1]:.6g}",
            expected=f"vue annuelle = {gaps[0][2]:.6g}",
            evidence={
                "controle": f"periode_annuel_{kind}",
                "grandeur": name,
                "nature": kind,
                "regle_appliquee": rule_text,
                "ligne_periode": f"{period_series.sheet}!{period_row}",
                "ligne_annuelle": f"{annuel.sheet}!{annual_row}",
                "tolerance": tol,
                "annees_en_ecart": len(gaps),
                "detail": [
                    {"annee": y, "agrege_periodes": a, "vue_annuelle": r, "ecart": d}
                    for y, a, r, d in gaps[:MAX_DETAIL]
                ],
            },
            consumers=[],
            confidence=_confidence(max(abs(d) for *_x, d in gaps), tol),
            note=(
                f"La vue annuelle de « {name} » ne correspond pas a {rule_text} sur "
                f"{len(gaps)} annee(s)."
            ),
        )

    def check_flags(self) -> list[Signal]:
        """8. Indicateurs mutuellement exclusifs et contigus.

        Des drapeaux de phase (construction / exploitation / apres dette) doivent
        valoir 1 sur exactement une phase a la fois, et chaque phase doit former
        un intervalle continu. Un drapeau qui s'allume deux fois trahit une
        chronique recollee.
        """
        if len(self.mapping.flags) < 1:
            return []
        series = []
        for name, loc in self.mapping.flags.items():
            s = self.series(f"flags.{name}", loc)
            if s is not None:
                series.append((name, s))
        if not series:
            return []

        out: list[Signal] = []

        # Contiguite, drapeau par drapeau.
        for name, s in series:
            active = [i for i, v in enumerate(s.values) if v is not None and abs(v - 1) < 1e-9]
            if not active:
                continue
            runs = _runs(active)
            if len(runs) > 1:
                out.append(
                    self.rule.signal(
                        sheet=s.sheet,
                        refs=[f"{s.row}:{s.row}"],
                        label=f"Contiguite du drapeau — {name}",
                        observed=f"{len(runs)} plages actives",
                        expected="une seule plage active",
                        evidence={
                            "controle": "flags_contigus",
                            "drapeau": name,
                            "plages_actives": [
                                f"{self.periods[a]}..{self.periods[b]}" for a, b in runs
                            ],
                            "periodes_actives": len(active),
                        },
                        consumers=(
                            self.ctx.graph.consumers_of_row(s.sheet, s.row)
                            if self.ctx.graph else []
                        ),
                        confidence=0.85,
                        note=(
                            f"Le drapeau « {name} » s'active sur {len(runs)} plages "
                            f"disjointes au lieu d'une seule."
                        ),
                    )
                )

        # Exclusivite mutuelle, periode par periode.
        if len(series) >= 2:
            overlaps = []
            for i in range(len(self.cols)):
                active = [name for name, s in series if (s.at(i) or 0) > 0.5]
                if len(active) > 1:
                    overlaps.append((self.periods[i], active))
            if overlaps:
                first = series[0][1]
                out.append(
                    self.rule.signal(
                        sheet=first.sheet,
                        refs=[f"{s.row}:{s.row}" for _n, s in series],
                        label="Exclusivite des drapeaux",
                        observed=f"{len(overlaps)} periode(s) a plusieurs drapeaux actifs",
                        expected="au plus un drapeau actif par periode",
                        evidence={
                            "controle": "flags_exclusifs",
                            "drapeaux": [n for n, _s in series],
                            "periodes_en_chevauchement": [
                                {"periode": p, "drapeaux_actifs": a}
                                for p, a in overlaps[:MAX_DETAIL]
                            ],
                        },
                        consumers=[],
                        confidence=0.85,
                        note=(
                            f"Plusieurs drapeaux sont actifs simultanement sur "
                            f"{len(overlaps)} periode(s)."
                        ),
                    )
                )
        return out

    def check_immobilisations(self) -> list[Signal]:
        """9. Immobilisations bornees : 0 <= amortissements <= brut, net = brut - amort."""
        immo = self.mapping.immobilisations
        brut = self.series("immobilisations.brut", immo.brut)
        amort = self.series("immobilisations.amortissements", immo.amortissements)
        net = self.series("immobilisations.net", immo.net)
        tol = self.mapping.tolerances.immobilisations
        out: list[Signal] = []

        if brut is not None and amort is not None:
            gaps = []
            for i in range(len(self.cols)):
                b, a = brut.at(i), amort.at(i)
                if b is None or a is None:
                    continue
                magnitude = abs(a)
                if magnitude > abs(b) + tol:
                    gaps.append((i, magnitude - abs(b)))
            signal = self.breach_signal(
                "immobilisations_bornees", "Amortissements bornes par le brut",
                amort, brut, gaps, tol,
                f"Les amortissements cumules depassent la valeur brute sur "
                f"{len(gaps)} periode(s) : la valeur nette devient negative.",
            )
            if signal:
                out.append(signal)

        if brut is not None and amort is not None and net is not None:
            gaps = []
            for i in range(len(self.cols)):
                b, a, n = brut.at(i), amort.at(i), net.at(i)
                if None in (b, a, n):
                    continue
                expected = b - abs(a)
                if abs(n - expected) > tol:
                    gaps.append((i, n - expected))
            signal = self.breach_signal(
                "immobilisations_articulation", "Net = brut - amortissements",
                net, brut, gaps, tol,
                f"La valeur nette ne correspond pas a brut moins amortissements sur "
                f"{len(gaps)} periode(s).",
                extra={"ligne_amortissements": amort.ref},
            )
            if signal:
                out.append(signal)
        return out

    def check_non_negativite(self) -> list[Signal]:
        """10. Grandeurs qui ne peuvent pas devenir negatives."""
        out: list[Signal] = []
        tol = self.mapping.tolerances.non_negativite
        for i, loc in enumerate(self.mapping.non_negatif):
            s = self.series(f"non_negatif[{i}]", loc)
            if s is None:
                continue
            gaps = [
                (j, v) for j, v in enumerate(s.values) if v is not None and v < -abs(tol)
            ]
            if not gaps:
                continue
            worst = min(v for _j, v in gaps)
            out.append(
                self.rule.signal(
                    sheet=s.sheet,
                    refs=[f"{s.row}:{s.row}"],
                    label=f"Non-negativite — {s.label or loc}",
                    observed=f"minimum = {worst:.6g}",
                    expected=">= 0",
                    evidence={
                        "controle": "non_negativite",
                        "ligne": s.ref,
                        "periodes_negatives": len(gaps),
                        "minimum": worst,
                        "premiere_periode_negative": self.periods[gaps[0][0]],
                        "detail": [
                            {"periode": self.periods[j], "valeur": v}
                            for j, v in gaps[:MAX_DETAIL]
                        ],
                    },
                    consumers=(
                        self.ctx.graph.consumers_of_row(s.sheet, s.row)
                        if self.ctx.graph else []
                    ),
                    confidence=0.90,
                    note=(
                        f"« {s.label} » devient negative sur {len(gaps)} periode(s), "
                        f"minimum {worst:.6g} en periode {self.periods[gaps[0][0]]}."
                    ),
                )
            )
        return out

    # -- analyseur de tresorerie negative ----------------------------------
    def analyse_negative_cash(self) -> list[Signal]:
        """Decompose la cascade sur les periodes de tresorerie negative.

        Pour chaque periode en ecart : quel etage bascule, dans quel etat sont les
        mecanismes de couverture, et sur quelle grandeur leur signal de
        declenchement est branche. C'est cette derniere question qui distingue un
        modele ou la couverture ne s'active pas d'un modele ou elle est branchee
        sur la mauvaise grandeur.
        """
        cascade = self.mapping.cascade
        cloture = self.series("cascade.solde_cloture", cascade.solde_cloture)
        if cloture is None:
            return []
        negatives = [
            (i, v) for i, v in enumerate(cloture.values) if v is not None and v < 0
        ]
        if not negatives:
            return []

        etages = []
        for key, loc in (
            ("solde_ouverture", cascade.solde_ouverture),
            ("encaissements", cascade.encaissements),
            ("decaissements", cascade.decaissements),
        ):
            s = self.series(f"cascade.{key}", loc)
            if s is not None:
                etages.append((key, s))

        couverture = []
        for key, loc in (
            ("facilite_court_terme", cascade.facilite_court_terme),
            ("reserves", cascade.reserves),
        ):
            s = self.series(f"cascade.{key}", loc)
            if s is not None:
                couverture.append((key, s))

        detail = []
        for i, value in negatives[:MAX_DETAIL]:
            entry = {
                "periode": self.periods[i],
                "colonne": R.index_to_col(self.cols[i]),
                "solde_de_cloture": value,
                "etages": {key: s.at(i) for key, s in etages},
                "mecanismes_de_couverture": {
                    key: {
                        "valeur": s.at(i),
                        "actif": bool(s.at(i)) and abs(s.at(i) or 0) > 1e-12,
                    }
                    for key, s in couverture
                },
            }
            entry["etage_de_bascule"] = self._pivot_stage(etages, i)
            detail.append(entry)

        triggers = {
            key: self._trigger_of(s) for key, s in couverture
        }
        worst = min(v for _i, v in negatives)
        return [
            self.rule.signal(
                sheet=cloture.sheet,
                refs=[f"{cloture.row}:{cloture.row}"],
                label="Tresorerie negative",
                observed=f"solde de cloture minimal = {worst:.6g}",
                expected=">= 0",
                evidence={
                    "controle": "tresorerie_negative",
                    "ligne_solde_cloture": cloture.ref,
                    "periodes_negatives": len(negatives),
                    "solde_minimal": worst,
                    "premiere_periode_negative": self.periods[negatives[0][0]],
                    "mecanismes_de_couverture_declares": [k for k, _s in couverture],
                    "signal_de_declenchement": triggers,
                    "detail": detail,
                },
                consumers=(
                    self.ctx.graph.consumers_of_row(cloture.sheet, cloture.row)
                    if self.ctx.graph else []
                ),
                confidence=0.90,
                note=(
                    f"Le solde de cloture est negatif sur {len(negatives)} periode(s), "
                    f"minimum {worst:.6g} en periode "
                    f"{self.periods[negatives[0][0]]}"
                    + (
                        f" ; mecanismes de couverture declares : "
                        f"{', '.join(k for k, _s in couverture)}."
                        if couverture
                        else " ; aucun mecanisme de couverture n'est declare au mapping."
                    )
                ),
            )
        ]

    @staticmethod
    def _pivot_stage(etages, i: int) -> str:
        """Etage qui fait basculer la periode : le poste negatif le plus lourd."""
        worst_key, worst_value = "", 0.0
        for key, s in etages:
            value = s.at(i)
            if value is None:
                continue
            if value < worst_value:
                worst_key, worst_value = key, value
        return worst_key or "indetermine"

    def _trigger_of(self, s: Series) -> dict:
        """Sur quelle grandeur le declenchement d'un mecanisme est-il branche ?"""
        sheet = self.snap.sheet(s.sheet)
        if sheet is None:
            return {}
        for col in self.cols:
            formula = sheet.formula(s.row, col)
            if not formula:
                continue
            refs = R.extract_refs(formula, default_sheet=s.sheet)
            return {
                "formule": formula,
                "branche_sur": [
                    {
                        "ref": ref.a1,
                        "libelle": self.snap.row_label(ref.sheet or s.sheet, ref.min_row),
                    }
                    for ref in refs[:8]
                ],
            }
        return {"formule": None, "branche_sur": []}

    # -- utilitaires --------------------------------------------------------
    def _diff(self, left: Series, right: Series, tol: float) -> list[tuple[int, float]]:
        gaps = []
        for i in range(len(self.cols)):
            a, b = left.at(i), right.at(i)
            if a is None or b is None:
                continue
            if abs(a - b) > tol:
                gaps.append((i, a - b))
        return gaps


def _runs(indices: list[int]) -> list[tuple[int, int]]:
    """Regroupe des indices en intervalles contigus."""
    if not indices:
        return []
    runs = [(indices[0], indices[0])]
    for i in indices[1:]:
        if i == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], i)
        else:
            runs.append((i, i))
    return runs


def _annual_columns(annuel) -> list[int]:
    if not annuel.colonnes or ":" not in annuel.colonnes:
        return []
    left, right = annuel.colonnes.split(":", 1)
    lo = R.col_to_index(left.strip().lstrip("$"))
    hi = R.col_to_index(right.strip().lstrip("$"))
    return list(range(min(lo, hi), max(lo, hi) + 1))


@register
class R301Ties(Rule):
    """Les dix invariants de bouclage, plus l'analyseur de tresorerie negative.

    Confiance : voir `_confidence`. Un ecart de deux ordres de grandeur au-dessus
    de la tolerance vaut 0.95 ; un ecart qui l'effleure vaut 0.55, parce qu'il
    peut n'etre qu'un residu d'arrondi.
    """

    id = "R301"
    label = "Bouclages"
    phase = 3
    requires_mapping = True

    def run(self, ctx: AuditContext) -> list[Signal]:
        engine = TiesEngine(ctx, self)
        signals: list[Signal] = []
        signals.extend(engine.check_bilan())
        signals.extend(engine.check_cascade_vs_bilan())
        signals.extend(engine.check_continuite())
        signals.extend(engine.check_dettes())
        signals.extend(engine.check_emplois_ressources())
        signals.extend(engine.check_periode_annuel())
        signals.extend(engine.check_flags())
        signals.extend(engine.check_immobilisations())
        signals.extend(engine.check_non_negativite())
        signals.extend(engine.analyse_negative_cash())

        if engine.skipped:
            ctx.add_reserve(
                "P3_LOCALISATIONS_NON_VALIDEES",
                "Controles de phase 3 non executes faute de localisation validee : "
                + " | ".join(engine.skipped),
                severity="warning",
            )
        return signals
