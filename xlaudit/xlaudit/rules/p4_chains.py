"""Phase 4 - Extraction de chaines de calcul et comparateur de reconstitution.

Une chaine est le chemin qui mene d'une grandeur de sortie a ses entrees. Le
comparateur de reconstitution confronte la valeur en cache de chaque maillon a
celle que sa formule redonne a partir des valeurs en cache de ses precedents. Un
maillon dont les deux ne coincident pas signale un cache perime, une macro non
rejouee, ou une formule que l'outil lit mal — dans les trois cas, l'auditeur doit
le savoir avant de s'appuyer sur les chiffres.
"""

from __future__ import annotations

from ..core import blocks as B
from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register


@register
class R401Reconstitution(Rule):
    """Comparateur de reconstitution : cache contre recalcul local.

    Chaque cellule reconstituable est recalculee a partir des valeurs en cache de
    ses precedents, puis comparee a sa propre valeur en cache. Les cellules hors
    du perimetre du chiffreur sont comptees mais ne produisent pas de signal :
    elles ne prouvent rien.

    Confiance :
      - 0.80 quand des ecarts apparaissent sur plus de 1 % des cellules
        reconstituables : le cache n'est pas l'etat converge du modele ;
      - 0.55 en deca, ou quelques ecarts isoles peuvent tenir a des fonctions
        volatiles ou a des arrondis d'affichage.
    """

    id = "R401"
    label = "Reconstitution du cache"
    phase = 4

    #: Au-dela, on echantillonne : la reconstitution complete d'un classeur de
    #: 1,26 M de formules n'apporte rien de plus que sa mesure sur un echantillon.
    MAX_CELLS_PER_SHEET = 4000

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            if not sheet.formulas:
                continue
            checked = 0
            unevaluable = 0
            mismatches: list[dict] = []
            for (row, col), formula in sorted(sheet.formulas.items()):
                if checked >= self.MAX_CELLS_PER_SHEET:
                    break
                cached = Q.as_number(sheet.value(row, col))
                if cached is None:
                    continue
                try:
                    recomputed = Q.evaluate(snap, sheet.name, formula)
                except Q.Unevaluable:
                    unevaluable += 1
                    continue
                checked += 1
                tol = max(1e-6, abs(cached) * 1e-9)
                if abs(recomputed - cached) > tol:
                    mismatches.append(
                        {
                            "ref": f"{R.index_to_col(col)}{row}",
                            "libelle": sheet.row_label(row),
                            "formule": formula,
                            "valeur_en_cache": cached,
                            "valeur_reconstituee": recomputed,
                            "ecart": recomputed - cached,
                        }
                    )
            if not mismatches or checked == 0:
                continue

            share = len(mismatches) / checked
            confidence = 0.80 if share > 0.01 else 0.55
            worst = max(mismatches, key=lambda m: abs(m["ecart"]))
            out.append(
                self.signal(
                    sheet=sheet.name,
                    refs=[m["ref"] for m in mismatches[:10]],
                    label="Reconstitution",
                    observed=f"{len(mismatches)} ecart(s) sur {checked} cellule(s) reconstituables",
                    expected="valeur en cache = valeur reconstituee",
                    evidence={
                        "cellules_reconstituees": checked,
                        "cellules_hors_perimetre": unevaluable,
                        "cellules_en_ecart": len(mismatches),
                        "part_en_ecart": round(share, 4),
                        "ecart_maximal": worst["ecart"],
                        "detail": mismatches[:30],
                    },
                    consumers=[],
                    confidence=confidence,
                    note=(
                        f"{len(mismatches)} cellule(s) sur {checked} reconstituables "
                        f"ne redonnent pas leur valeur en cache ; ecart maximal "
                        f"{worst['ecart']:.6g} en {worst['ref']}."
                    ),
                )
            )
        return out


@register
class R402Chains(Rule):
    """Extraction des chaines de calcul menant aux lignes terminales.

    Une chaine part d'une ligne consommee par personne — donc une sortie du
    modele — et remonte ses precedents. Elle donne la profondeur du calcul, les
    onglets traverses et les entrees atteintes.

    Confiance : 0.15. Une chaine est une description, pas une suspicion.
    """

    id = "R402"
    label = "Chaines de calcul"
    phase = 4
    requires_graph = True

    MAX_CHAINS = 40
    MAX_DEPTH = 12

    def run(self, ctx: AuditContext) -> list[Signal]:
        graph = ctx.graph
        snap = ctx.snapshot
        if graph is None:
            return []
        out: list[Signal] = []
        emitted = 0

        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            for row in st.formula_rows:
                if emitted >= self.MAX_CHAINS:
                    return out
                if graph.is_consumed(sheet.name, row):
                    continue
                label = sheet.row_label(row)
                if not label:
                    continue
                depth, sheets_seen, inputs = self._walk(graph, sheet.name, row)
                if depth == 0:
                    continue
                emitted += 1
                out.append(
                    self.signal(
                        sheet=sheet.name,
                        refs=[f"{row}:{row}"],
                        label=label,
                        observed=f"profondeur {depth}, {len(sheets_seen)} onglet(s) traverses",
                        evidence={
                            "profondeur": depth,
                            "onglets_traverses": sorted(sheets_seen),
                            "lignes_d_entree": inputs[:40],
                            "nombre_d_entrees": len(inputs),
                        },
                        consumers=[],
                        confidence=0.15,
                        note=(
                            f"Chaine de calcul de « {label} » : {depth} niveau(x), "
                            f"{len(sheets_seen)} onglet(s), {len(inputs)} ligne(s) "
                            f"d'entree."
                        ),
                    )
                )
        return out

    def _walk(self, graph, sheet: str, row: int):
        """Remonte les precedents au grain de la ligne, sans reboucler."""
        seen = {(sheet, row)}
        frontier = [(sheet, row)]
        depth = 0
        sheets_seen = {sheet}
        inputs: list[str] = []
        while frontier and depth < self.MAX_DEPTH:
            following = []
            for s, r in frontier:
                precedents = graph.precedents_of_row(s, r, limit=60)
                if not precedents:
                    if (s, r) != (sheet, row):
                        inputs.append(f"{s}!{r}")
                    continue
                for name in precedents:
                    psheet, _sep, prow = name.rpartition("!")
                    key = (psheet, int(prow))
                    if key in seen:
                        continue
                    seen.add(key)
                    sheets_seen.add(psheet)
                    following.append(key)
            if not following:
                break
            frontier = following
            depth += 1
        return depth, sheets_seen, sorted(set(inputs))
