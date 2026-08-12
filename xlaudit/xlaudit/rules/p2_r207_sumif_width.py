"""R207 - Plage de somme de largeur differente de la plage de criteres."""

from __future__ import annotations

from ..core import blocks as B
from ..core import quantifier as Q
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register

# Position des arguments : (index plage de criteres, index plage de somme).
# SUMIF(criteres, critere, [somme]) ; SUMIFS(somme, criteres1, critere1, ...).
CRITERIA_FIRST = {"SUMIF": (0, 2), "AVERAGEIF": (0, 2)}
SUM_FIRST = {"SUMIFS": (1, 0), "AVERAGEIFS": (1, 0)}


@register
class R207SumRangeWidth(Rule):
    """Plage de somme dont la forme differe de celle de la plage de criteres.

    Excel n'additionne pas la plage citee : il la redimensionne a la forme de la
    plage de criteres, depuis son coin superieur gauche. Une plage de somme de
    deux colonnes face a des criteres d'une colonne ne somme donc que la premiere
    colonne. La formule se lit comme si elle en sommait deux.

    Le signal indique les deux montants : celui qui est effectivement somme et
    celui qu'un lecteur de la formule croirait somme. Le critere est applique
    quand il est litteral ; sinon les deux montants sont donnes sans filtre et
    l'evidence le precise.

    Confiance :
      - 0.95 : la troncature est un comportement d'Excel, pas une hypothese ; la
        seule reserve tient a la possibilite d'une plage citee volontairement plus
        large ;
      - -0.20 si la zone ignoree est vide, auquel cas l'ecriture est trompeuse
        mais sans effet.
    """

    id = "R207"
    label = "Plage de somme multi-colonnes"
    phase = 2

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        graph = ctx.graph
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            for (row, col), formula in sheet.formulas.items():
                for call in R.parse_calls(formula, default_sheet=sheet.name):
                    spec = CRITERIA_FIRST.get(call.name) or SUM_FIRST.get(call.name)
                    if spec is None:
                        continue
                    crit_idx, sum_idx = spec
                    if call.arity <= max(crit_idx, sum_idx):
                        continue
                    crit_ref = call.arg_refs[crit_idx]
                    sum_ref = call.arg_refs[sum_idx]
                    if crit_ref is None or sum_ref is None:
                        continue
                    if crit_ref.width == sum_ref.width and crit_ref.height == sum_ref.height:
                        continue
                    signal = self._emit(
                        ctx, sheet, row, col, formula, call, crit_ref, sum_ref, graph
                    )
                    if signal is not None:
                        out.append(signal)
        return out

    def _emit(self, ctx, sheet, row, col, formula, call, crit_ref, sum_ref, graph):
        snap = ctx.snapshot
        # L'ancrage de la plage citee est conserve : la correction proposee doit
        # rester recopiable comme l'originale.
        effective = R.RangeRef(
            start=R.CellRef(
                sum_ref.min_col, sum_ref.min_row,
                sum_ref.start.col_abs, sum_ref.start.row_abs,
            ),
            end=R.CellRef(
                sum_ref.min_col + crit_ref.width - 1,
                sum_ref.min_row + crit_ref.height - 1,
                sum_ref.end.col_abs, sum_ref.end.row_abs,
            ),
            sheet=sum_ref.sheet,
        )
        criterion = self._criterion(call)
        sums = self._compare(snap, sheet.name, crit_ref, criterion, sum_ref, effective)

        ignored = None
        if sum_ref.max_col > effective.max_col:
            ignored = R.RangeRef(
                start=R.CellRef(effective.max_col + 1, sum_ref.min_row),
                end=R.CellRef(sum_ref.max_col, sum_ref.max_row),
                sheet=sum_ref.sheet,
            )
        confidence = 0.95
        zone_empty = ignored is not None and not Q.range_is_populated(
            snap, ignored, sheet.name
        )
        if zone_empty:
            confidence -= 0.20

        # La comparaison porte sur la zone visee, pas sur le texte : la reference
        # rendue par `map_refs` ne porte pas l'onglet implicite, contrairement a
        # celle qu'a resolue `parse_calls`.
        def substitute(ref: R.RangeRef, _i: int):
            if not R.same_extent(ref, sum_ref, sheet.name):
                return None
            return R.RangeRef(
                start=effective.start, end=effective.end, sheet=ref.sheet
            ).a1

        expected = R.map_refs(formula, substitute)
        evidence = {
            "fonction": call.name,
            "plage_criteres": crit_ref.a1,
            "forme_criteres": f"{crit_ref.height}x{crit_ref.width}",
            "plage_somme_citee": sum_ref.a1,
            "forme_somme_citee": f"{sum_ref.height}x{sum_ref.width}",
            "plage_effectivement_sommee": effective.a1,
            "zone_ignoree": ignored.a1 if ignored else None,
            "zone_ignoree_vide": zone_empty,
            "critere": criterion if criterion is not None else "(non litteral)",
            **sums,
        }
        return self.signal(
            sheet=sheet.name,
            refs=[f"{R.index_to_col(col)}{row}"],
            label=sheet.row_label(row),
            observed=formula,
            expected=expected,
            evidence=evidence,
            consumers=graph.consumers_of_row(sheet.name, row) if graph else [],
            confidence=confidence,
            note=(
                f"{call.name} : la plage de somme citee {sum_ref.a1} "
                f"({sum_ref.height}x{sum_ref.width}) ne correspond pas a la plage de "
                f"criteres {crit_ref.a1} ({crit_ref.height}x{crit_ref.width}) ; Excel "
                f"la redimensionne a {effective.a1} depuis son coin superieur gauche."
            ),
        )

    @staticmethod
    def _criterion(call: R.FunctionCall):
        """Critere litteral de l'appel, ou None s'il est calcule."""
        idx = 1 if call.name in CRITERIA_FIRST else 2
        if call.arity <= idx:
            return None
        raw = call.args[idx].strip()
        if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            return raw[1:-1]
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _compare(snap, sheet: str, crit_ref, criterion, cited, effective) -> dict:
        """Montant effectivement somme et montant que la formule laisse croire.

        Le critere n'est applique que s'il est litteral. Sinon les deux montants
        sont des totaux sans filtre, et l'evidence l'indique explicitement.
        """
        crit_sheet = snap.sheet(crit_ref.sheet or sheet)
        cited_sheet = snap.sheet(cited.sheet or sheet)
        if crit_sheet is None or cited_sheet is None:
            return {"montant_somme": None, "montant_apparent": None}

        def matches(value) -> bool:
            if criterion is None:
                return True
            if isinstance(criterion, float):
                num = Q.as_number(value)
                return num is not None and abs(num - criterion) < 1e-12
            return str(value).strip().lower() == str(criterion).strip().lower()

        effective_total = 0.0
        apparent_total = 0.0
        rows_kept = 0
        for offset in range(crit_ref.height):
            crit_row = crit_ref.min_row + offset
            if not matches(crit_sheet.value(crit_row, crit_ref.min_col)):
                continue
            rows_kept += 1
            target_row = cited.min_row + offset
            for c in range(cited.min_col, cited.max_col + 1):
                num = Q.as_number(cited_sheet.value(target_row, c))
                if num is None:
                    continue
                apparent_total += num
                if c <= effective.max_col:
                    effective_total += num
        return {
            "montant_somme": effective_total,
            "montant_apparent": apparent_total,
            "ecart_de_lecture": apparent_total - effective_total,
            "lignes_retenues_par_le_critere": rows_kept,
            "critere_applique": criterion is not None,
        }
