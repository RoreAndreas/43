"""Graphe de dependances cellule / ligne / onglet.

Choix d'echelle : le graphe principal est construit au grain de la **ligne**.
Sur un classeur de 1,26 M de formules, un graphe au grain de la cellule avec
expansion des plages produirait des centaines de millions d'aretes. Or la
question posee par les regles est presque toujours au grain de la ligne
(« qui consomme cette ligne ? », « cette ligne a-t-elle un dependant ? »), et
c'est aussi la granularite du champ `consumers` d'un signal.

Le grain cellule reste disponible a la demande pour `trace`, qui ne porte que sur
quelques cellules : les precedents sont relus dans la formule, les dependants
sont cherches parmi les seules lignes consommatrices connues du graphe de lignes.

Les plages tres hautes (`A:A`, `A1:A100000`) ne sont pas expansees arete par
arete : elles sont enregistrees comme intervalles de consommation, interroges par
`is_consumed`. Sans cela une ligne citee par un `SOMME(A:A)` passerait pour
orpheline.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Callable

import networkx as nx

from . import refs as R
from .loader import Snapshot

ProgressCb = Callable[[str, int, int], None]

# Au-dela, une plage est traitee comme intervalle plutot que comme paquet d'aretes.
BULK_ROW_THRESHOLD = 500


def node_name(sheet: str, row: int) -> str:
    return f"{sheet}!{row}"


@dataclass
class CellNode:
    """Un maillon d'une trace, avec de quoi juger sans rouvrir le classeur."""

    sheet: str
    row: int
    col: int
    formula: str | None
    value: object
    label: str = ""
    depth: int = 0
    children: list["CellNode"] = field(default_factory=list)
    truncated: bool = False
    note: str = ""

    @property
    def ref(self) -> str:
        return f"{R.index_to_col(self.col)}{self.row}"

    @property
    def full_ref(self) -> str:
        return f"{self.sheet}!{self.ref}"

    def to_dict(self) -> dict:
        from ..models import _jsonable

        return {
            "ref": self.full_ref,
            "label": self.label,
            "formula": self.formula,
            "value": _jsonable(self.value),
            "depth": self.depth,
            "truncated": self.truncated,
            "note": self.note,
            "children": [c.to_dict() for c in self.children],
        }


class _IntervalSet:
    """Ensemble d'intervalles de lignes, interroge par appartenance.

    Utilise pour les plages trop hautes pour etre expansees en aretes.
    """

    def __init__(self) -> None:
        self._raw: list[tuple[int, int]] = []
        self._starts: list[int] = []
        self._ends: list[int] = []
        self._dirty = True

    def add(self, lo: int, hi: int) -> None:
        self._raw.append((lo, hi))
        self._dirty = True

    def _compact(self) -> None:
        if not self._dirty:
            return
        merged: list[tuple[int, int]] = []
        for lo, hi in sorted(self._raw):
            if merged and lo <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        self._raw = merged
        self._starts = [a for a, _ in merged]
        self._ends = [b for _, b in merged]
        self._dirty = False

    def contains(self, row: int) -> bool:
        self._compact()
        if not self._starts:
            return False
        i = bisect_right(self._starts, row) - 1
        return i >= 0 and row <= self._ends[i]

    def __bool__(self) -> bool:
        self._compact()
        return bool(self._raw)


class DependencyGraph:
    """Graphe de lignes, plus les services de trace au grain cellule."""

    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        self.row_graph = nx.DiGraph()
        self.sheet_graph = nx.DiGraph()
        # Lignes citees par une plage trop haute pour etre expansee.
        self.bulk_consumed: dict[str, _IntervalSet] = {}
        # Les memes plages, avec leur consommateur : sans cela, retrouver les
        # dependants d'une cellule prise dans un `SOMME(A:A)` imposerait de
        # relire toutes les formules du classeur.
        self.bulk_edges: dict[str, list[tuple[int, int, tuple[str, int]]]] = {}
        # Lignes citees par une reference dont l'onglet est introuvable.
        self.unresolved_refs: list[tuple[str, int, int, str]] = []
        self.external_refs: set[str] = set()
        # Collectees pendant la construction : les reperer apres coup imposerait
        # un second parcours complet des formules.
        self._self_refs: set[tuple[str, int]] = set()
        self._built = False

    # -- construction ------------------------------------------------------
    def build(self, progress: ProgressCb | None = None) -> "DependencyGraph":
        snap = self.snapshot
        sheets = list(snap.sheets.values())
        total = sum(len(s.formulas) for s in sheets) or 1
        done = 0

        for sheet in sheets:
            self.sheet_graph.add_node(sheet.name)
            for (row, col), formula in sheet.formulas.items():
                done += 1
                if progress and done % 5000 == 0:
                    progress("graphe", done, total)
                consumer = (sheet.name, row)
                self.row_graph.add_node(consumer)
                for ref in R.extract_refs(formula, default_sheet=sheet.name):
                    self._add_edge(sheet.name, row, col, ref)

        if progress:
            progress("graphe", total, total)
        self._built = True
        return self

    def _add_edge(self, sheet_name: str, row: int, col: int, ref: R.RangeRef) -> None:
        target_sheet = ref.sheet or sheet_name
        if target_sheet.startswith("["):
            self.external_refs.add(target_sheet)
            return
        src = self.snapshot.sheet(target_sheet)
        if src is None:
            self.unresolved_refs.append((sheet_name, row, col, ref.a1))
            return
        canonical = src.name
        consumer = (sheet_name, row)

        lo = ref.min_row
        hi = min(ref.max_row, max(src.max_row, 1))
        if hi < lo:
            return

        if (hi - lo + 1) > BULK_ROW_THRESHOLD:
            self.bulk_consumed.setdefault(canonical, _IntervalSet()).add(lo, hi)
            self.bulk_edges.setdefault(canonical, []).append((lo, hi, consumer))
            self.sheet_graph.add_edge(canonical, sheet_name)
            return

        # Une arete est « decalee » quand la formule ne lit que des colonnes
        # strictement a sa gauche : c'est le motif « solde d'ouverture = solde de
        # cloture de la periode precedente ». Au grain de la ligne, une telle
        # recurrence temporelle ressemble a un cycle alors qu'elle n'en est pas
        # un. L'attribut permet de les distinguer sans perdre l'information.
        lagged = ref.max_col < col
        if canonical == sheet_name and lo <= row <= hi and ref.min_col <= col <= ref.max_col:
            self._self_refs.add((canonical, row))

        for r in range(lo, hi + 1):
            producer = (canonical, r)
            if producer == consumer:
                continue  # auto-reference : comptabilisee juste au-dessus
            existing = self.row_graph.get_edge_data(producer, consumer)
            if existing is None:
                self.row_graph.add_edge(producer, consumer, lagged=lagged)
            elif not lagged:
                # Une seule reference en meme colonne suffit a rendre l'arete
                # instantanee : le decalage doit valoir pour toutes.
                existing["lagged"] = False
        if canonical != sheet_name:
            self.sheet_graph.add_edge(canonical, sheet_name)

    # -- interrogation -----------------------------------------------------
    def consumers_of_row(self, sheet: str, row: int, limit: int = 40) -> list[str]:
        """Lignes qui consomment (sheet, row), en 'Onglet!ligne'."""
        node = (sheet, row)
        if node not in self.row_graph:
            return []
        out = [node_name(s, r) for s, r in self.row_graph.successors(node)]
        out.sort()
        return out[:limit]

    def precedents_of_row(self, sheet: str, row: int, limit: int = 40) -> list[str]:
        node = (sheet, row)
        if node not in self.row_graph:
            return []
        out = [node_name(s, r) for s, r in self.row_graph.predecessors(node)]
        out.sort()
        return out[:limit]

    def consumer_count(self, sheet: str, row: int) -> int:
        node = (sheet, row)
        if node not in self.row_graph:
            return 0
        return self.row_graph.out_degree(node)

    def is_consumed(self, sheet: str, row: int) -> bool:
        """Vrai si la ligne est lue par au moins une formule.

        Prend en compte les plages trop hautes pour avoir ete expansees : sans
        cela, une ligne citee par `SOMME(A:A)` serait declaree orpheline a tort.
        """
        if self.consumer_count(sheet, row) > 0:
            return True
        iv = self.bulk_consumed.get(sheet)
        return bool(iv and iv.contains(row))

    def self_referencing_rows(self) -> list[tuple[str, int]]:
        """Lignes qui se citent elles-memes : circularite assumee ou accident.

        Collectees pendant la construction du graphe ; sans graphe construit, on
        retombe sur un parcours complet des formules.
        """
        if self._built:
            return sorted(self._self_refs)
        out = []
        for sheet in self.snapshot.sheets.values():
            for (row, col), formula in sheet.formulas.items():
                for ref in R.extract_refs(formula, default_sheet=sheet.name):
                    tgt = ref.sheet or sheet.name
                    s = self.snapshot.sheet(tgt)
                    if s and s.name == sheet.name and ref.min_row <= row <= ref.max_row:
                        if ref.min_col <= col <= ref.max_col:
                            out.append((sheet.name, row))
                            break
        return sorted(set(out))

    def _components(self, max_components: int) -> tuple[list[list[str]], list[list[str]]]:
        """Separe les vraies circularites des recurrences temporelles.

        Une composante fortement connexe du graphe de lignes qui se dissout des
        qu'on retire les aretes decalees d'une periode n'est pas une circularite :
        c'est une chronique, ou chaque periode lit la precedente. Les signaler
        comme des cycles noierait les vraies boucles sous le bruit, puisque tout
        modele financier enchaine ainsi ses soldes.
        """
        instantaneous = nx.DiGraph()
        instantaneous.add_nodes_from(self.row_graph.nodes)
        instantaneous.add_edges_from(
            (u, v) for u, v, data in self.row_graph.edges(data=True)
            if not data.get("lagged", False)
        )

        real: list[list[str]] = []
        temporal: list[list[str]] = []
        for comp in nx.strongly_connected_components(self.row_graph):
            if len(comp) <= 1:
                continue
            names = sorted(node_name(s, r) for s, r in comp)
            sub = instantaneous.subgraph(comp)
            if any(len(c) > 1 for c in nx.strongly_connected_components(sub)):
                real.append(names)
            else:
                temporal.append(names)
            if len(real) + len(temporal) >= max_components:
                break
        return real, temporal

    def cycles(self, max_cycles: int = 50) -> list[list[str]]:
        """Circularites reelles : composantes qui subsistent sans les aretes decalees.

        On ne cherche pas les cycles elementaires (`simple_cycles` est
        exponentiel sur un modele reel) : une composante fortement connexe suffit
        a localiser une boucle de calcul.
        """
        return self._components(max_cycles)[0]

    def temporal_recurrences(self, max_components: int = 50) -> list[list[str]]:
        """Chaines periode a periode, du type « ouverture = cloture precedente ».

        Ce ne sont pas des anomalies : c'est ainsi qu'un modele enchaine ses
        soldes. Elles sont exposees a part pour ne pas etre confondues avec des
        circularites.
        """
        return self._components(max_components)[1]

    def sheet_cycles(self) -> list[list[str]]:
        out = []
        for comp in nx.strongly_connected_components(self.sheet_graph):
            if len(comp) > 1:
                out.append(sorted(comp))
        return out

    # -- grain cellule (a la demande) --------------------------------------
    def _cell_precedents(self, sheet: str, row: int, col: int) -> list[tuple[str, int, int]]:
        snap = self.snapshot
        formula = snap.formula(sheet, row, col)
        if not formula:
            return []
        out: list[tuple[str, int, int]] = []
        seen: set[tuple[str, int, int]] = set()
        for ref in R.extract_refs(formula, default_sheet=sheet):
            tgt = snap.sheet(ref.sheet or sheet)
            if tgt is None:
                continue
            hi_r = min(ref.max_row, tgt.max_row)
            hi_c = min(ref.max_col, tgt.max_col)
            for r in range(ref.min_row, hi_r + 1):
                for c in range(ref.min_col, hi_c + 1):
                    if not tgt.has_content(r, c):
                        continue
                    key = (tgt.name, r, c)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(key)
                    if len(out) > 400:
                        return out
        return out

    def _cell_dependents(self, sheet: str, row: int, col: int) -> list[tuple[str, int, int]]:
        """Cellules dont la formule cite reellement (sheet, row, col).

        Les candidats sont restreints aux lignes consommatrices connues du graphe
        de lignes, puis verifies par relecture de la formule : le graphe de lignes
        est volontairement grossier, la verification retablit la precision.
        """
        snap = self.snapshot
        out: list[tuple[str, int, int]] = []
        candidates = set(self.row_graph.successors((sheet, row))) if (sheet, row) in self.row_graph else set()
        # Les plages en masse ne figurent pas dans le graphe : on rappelle leurs
        # consommateurs enregistres plutot que de rebalayer tout le classeur.
        for lo, hi, consumer in self.bulk_edges.get(sheet, ()):
            if lo <= row <= hi:
                candidates.add(consumer)

        # Tri explicite : les candidats viennent d'ensembles, et une sortie de
        # trace doit etre reproductible d'une execution a l'autre.
        for csheet, crow in sorted(candidates):
            s = snap.sheet(csheet)
            if s is None:
                continue
            for (r, c) in sorted(k for k in s.formulas if k[0] == crow):
                if self._formula_hits(s.formulas[(r, c)], csheet, sheet, row, col):
                    out.append((s.name, r, c))
                    if len(out) > 400:
                        return out
        return out

    @staticmethod
    def _formula_hits(formula: str, host_sheet: str, sheet: str, row: int, col: int) -> bool:
        for ref in R.extract_refs(formula, default_sheet=host_sheet):
            if (ref.sheet or host_sheet).lower() != sheet.lower():
                continue
            if ref.min_row <= row <= ref.max_row and ref.min_col <= col <= ref.max_col:
                return True
        return False

    def trace(
        self,
        sheet: str,
        row: int,
        col: int,
        depth: int = 3,
        direction: str = "up",
        _seen: set | None = None,
        _level: int = 0,
    ) -> CellNode:
        """Remontee (`up`) ou descente (`down`) recursive des dependances.

        Chaque maillon porte sa formule et sa valeur : la trace se lit sans
        rouvrir le classeur.
        """
        snap = self.snapshot
        s = snap.sheet(sheet)
        canonical = s.name if s else sheet
        node = CellNode(
            sheet=canonical,
            row=row,
            col=col,
            formula=snap.formula(canonical, row, col),
            value=snap.value(canonical, row, col),
            label=snap.row_label(canonical, row),
            depth=_level,
        )
        if _seen is None:
            _seen = set()
        key = (canonical, row, col)
        if key in _seen:
            node.note = "deja visite (boucle)"
            node.truncated = True
            return node
        _seen.add(key)
        if _level >= depth:
            has_more = bool(
                self._cell_precedents(canonical, row, col)
                if direction == "up"
                else self._cell_dependents(canonical, row, col)
            )
            node.truncated = has_more
            if has_more:
                node.note = "profondeur maximale atteinte"
            return node

        children = (
            self._cell_precedents(canonical, row, col)
            if direction == "up"
            else self._cell_dependents(canonical, row, col)
        )
        for csheet, crow, ccol in children[:60]:
            node.children.append(
                self.trace(csheet, crow, ccol, depth, direction, _seen, _level + 1)
            )
        if len(children) > 60:
            node.truncated = True
            node.note = f"{len(children)} dependances, 60 affichees"
        return node


def build_graph(snapshot: Snapshot, progress: ProgressCb | None = None) -> DependencyGraph:
    return DependencyGraph(snapshot).build(progress=progress)
