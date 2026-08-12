"""Tests du graphe de dependances."""

from __future__ import annotations

import pytest

from xlaudit.core import loader as L
from xlaudit.core.graph import build_graph

from .fixtures import build_faulty, build_healthy


@pytest.fixture(scope="module")
def healthy_graph(tmp_path_factory):
    path = build_healthy(tmp_path_factory.mktemp("g") / "sain.xlsx")
    snap = L.collect(path)
    return snap, build_graph(snap)


@pytest.fixture(scope="module")
def faulty_graph(tmp_path_factory):
    path = build_faulty(tmp_path_factory.mktemp("g") / "anomalies.xlsx")
    snap = L.collect(path)
    return snap, build_graph(snap)


class TestRowGraph:
    def test_total_row_consumes_its_block(self, healthy_graph):
        _, g = healthy_graph
        # La ligne 10 (total produits) consomme les lignes 6 a 9.
        precedents = g.precedents_of_row("Modele", 10)
        for row in (6, 7, 8, 9):
            assert f"Modele!{row}" in precedents

    def test_block_rows_are_consumed_by_the_total(self, healthy_graph):
        _, g = healthy_graph
        assert "Modele!10" in g.consumers_of_row("Modele", 6)

    def test_input_row_without_formula_still_has_consumers(self, healthy_graph):
        _, g = healthy_graph
        assert g.consumer_count("Modele", 12) > 0

    def test_orphan_row_in_faulty_workbook(self, faulty_graph):
        _, g = faulty_graph
        # "Impasse de tresorerie" n'est consommee par personne dans le classeur fautif.
        assert g.is_consumed("Modele", 49) is False

    def test_same_row_is_consumed_in_healthy_workbook(self, healthy_graph):
        _, g = healthy_graph
        assert g.is_consumed("Modele", 49) is True

    def test_cross_sheet_edges(self, healthy_graph):
        snap, g = healthy_graph
        # L'onglet d'etats financiers se refere a lui-meme uniquement ici,
        # mais le graphe d'onglets doit exister et contenir les deux onglets.
        assert set(g.sheet_graph.nodes) >= {"Modele", "Etats fi periode"}


class TestBulkRanges:
    def test_rows_inside_a_whole_column_reference_are_not_orphans(self, tmp_path):
        """Une ligne citee par SUM(A:A) ne doit pas passer pour orpheline."""
        from .fixtures import FixtureBuilder

        b = FixtureBuilder()
        b.cell("S", 5, 1, None, 10.0)
        b.cell("S", 900, 3, "=SUM(A:A)", 10.0)
        path = b.save(tmp_path / "bulk.xlsx")
        snap = L.collect(path)
        g = build_graph(snap)
        assert g.is_consumed("S", 5) is True

    def test_tall_range_is_recorded_as_interval(self, tmp_path):
        from .fixtures import FixtureBuilder

        b = FixtureBuilder()
        for r in range(1, 800):
            b.cell("S", r, 1, None, 1.0)
        b.cell("S", 900, 3, "=SUM(A1:A799)", 799.0)
        path = b.save(tmp_path / "tall.xlsx")
        g = build_graph(L.collect(path))
        assert g.is_consumed("S", 400) is True
        assert g.is_consumed("S", 850) is False


class TestTrace:
    def test_upward_trace_reaches_inputs(self, healthy_graph):
        snap, g = healthy_graph
        node = g.trace("Modele", 18, 4, depth=2, direction="up")
        assert node.formula == "=D10-D16"
        assert node.label == "Marge"
        children = {c.ref for c in node.children}
        assert {"D10", "D16"} <= children
        # Au niveau suivant on atteint les produits d'entree.
        total = next(c for c in node.children if c.ref == "D10")
        assert {"D6", "D7", "D8", "D9"} <= {c.ref for c in total.children}

    def test_trace_carries_formula_and_value_at_each_level(self, healthy_graph):
        _, g = healthy_graph
        node = g.trace("Modele", 18, 4, depth=1, direction="up")
        child = next(c for c in node.children if c.ref == "D10")
        assert child.formula == "=SUM(D6:D9)"
        assert child.value == pytest.approx(1000.0)

    def test_downward_trace_finds_consumers(self, healthy_graph):
        _, g = healthy_graph
        node = g.trace("Modele", 10, 4, depth=1, direction="down")
        refs = {c.ref for c in node.children}
        assert "D18" in refs  # la marge consomme le total produits

    def test_depth_is_respected_and_truncation_flagged(self, healthy_graph):
        _, g = healthy_graph
        node = g.trace("Modele", 18, 4, depth=1, direction="up")
        child = next(c for c in node.children if c.ref == "D10")
        assert child.children == []
        assert child.truncated is True

    def test_trace_is_serialisable(self, healthy_graph):
        _, g = healthy_graph
        d = g.trace("Modele", 18, 4, depth=2, direction="up").to_dict()
        assert d["ref"] == "Modele!D18"
        assert isinstance(d["children"], list)


class TestCycles:
    def test_no_cycle_in_healthy_model(self, healthy_graph):
        _, g = healthy_graph
        assert g.cycles() == []

    def test_cycle_is_detected(self, tmp_path):
        from .fixtures import FixtureBuilder

        b = FixtureBuilder()
        b.cell("S", 1, 1, "=B1+1", 1.0)
        b.cell("S", 2, 2, "=A1", 1.0)
        b.cell("S", 1, 2, "=B2", 1.0)
        path = b.save(tmp_path / "cycle.xlsx")
        g = build_graph(L.collect(path))
        cycles = g.cycles()
        assert cycles, "la boucle A1 -> B1 -> B2 -> A1 doit etre vue"
