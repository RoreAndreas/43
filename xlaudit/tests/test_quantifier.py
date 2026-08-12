"""Tests du chiffreur d'ecart et de son evaluateur restreint.

L'evaluateur doit refuser explicitement ce qu'il ne sait pas reconstituer. Un
chiffre invente serait pire qu'une absence de chiffre : il donnerait a un signal
une autorite qu'il n'a pas.
"""

from __future__ import annotations

import pytest

from xlaudit.core import loader as L
from xlaudit.core import quantifier as Q
from xlaudit.core import refs as R

from .fixtures import FixtureBuilder


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    b = FixtureBuilder()
    for i, value in enumerate([10.0, 20.0, 30.0, 40.0], start=1):
        b.cell("S", i, 1, None, value)
    b.cell("S", 6, 1, "=SUM(A1:A4)", 100.0)
    b.cell("S", 7, 1, "=SUM(A1:A4)+A1", 110.0)
    b.cell("S", 8, 1, "=SUM(A1:A4)-A2", 80.0)
    b.cell("S", 9, 1, "=A1*A2", 200.0)
    b.cell("S", 10, 1, "=XLOOKUP(A1,A1:A4,A1:A4)", 10.0)
    b.cell("S", 11, 1, "=AVERAGE(A1:A4)", 25.0)
    b.cell("S", 12, 1, "=MAX(A1:A4)-MIN(A1:A4)", 30.0)
    b.text("S", 13, 1, "texte")
    b.cell("S", 14, 1, "=SUM(A1:A4)+100", 200.0)
    path = b.save(tmp_path_factory.mktemp("q") / "q.xlsx")
    return L.collect(path)


class TestEvaluate:
    @pytest.mark.parametrize(
        "formula,expected",
        [
            ("=SUM(A1:A4)", 100.0),
            ("=SUM(A1:A4)+A1", 110.0),
            ("=SUM(A1:A4)-A2", 80.0),
            ("=AVERAGE(A1:A4)", 25.0),
            ("=MAX(A1:A4)-MIN(A1:A4)", 30.0),
            ("=SUM(A1:A4)+100", 200.0),
            ("=A1+A2+A3+A4", 100.0),
            ("=-A1+A2", 10.0),
        ],
    )
    def test_reconstitutes_supported_shapes(self, snap, formula, expected):
        assert Q.evaluate(snap, "S", formula) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "formula",
        ["=A1*A2", "=XLOOKUP(A1,A1:A4,A1:A4)", "=A1/A2", "=IF(A1>0,1,2)", "=A1&A2"],
    )
    def test_refuses_what_it_cannot_reconstitute(self, snap, formula):
        with pytest.raises(Q.Unevaluable):
            Q.evaluate(snap, "S", formula)

    def test_empty_cell_counts_as_zero(self, snap):
        assert Q.evaluate(snap, "S", "=A1+A99") == pytest.approx(10.0)

    def test_text_cell_is_refused(self, snap):
        with pytest.raises(Q.Unevaluable):
            Q.evaluate(snap, "S", "=A1+A13")


class TestRangeHelpers:
    def test_sums_only_numbers(self, snap):
        ref = R.parse_ref("A1:A4", "S")
        assert sum(Q.range_numbers(snap, ref, "S")) == pytest.approx(100.0)

    def test_populated_detection(self, snap):
        assert Q.range_is_populated(snap, R.parse_ref("A1:A2", "S"), "S") is True
        assert Q.range_is_populated(snap, R.parse_ref("Z50:Z60", "S"), "S") is False

    def test_booleans_count_as_one_and_zero(self):
        assert Q.as_number(True) == 1.0
        assert Q.as_number(False) == 0.0

    def test_errors_are_not_numbers(self):
        assert Q.as_number("#DIV/0!") is None
        assert Q.as_number(None) is None


class TestQuantify:
    def test_active_gap_is_measured(self, snap):
        """La ligne 6 somme A1:A4 ; la comparer a A1:A2 doit chiffrer l'ecart."""
        q = Q.quantify(snap, "S", 6, [1], lambda f, c: "=SUM(A1:A2)")
        assert q.verdict == "actif"
        assert q.max_abs_delta == pytest.approx(70.0)
        assert q.columns_touched == ["A6"]

    def test_cache_confirmation(self, snap):
        q = Q.quantify(snap, "S", 6, [1], lambda f, c: "=SUM(A1:A2)")
        assert q.cache_confirms_formula is True

    def test_no_gap_is_null(self, snap):
        q = Q.quantify(snap, "S", 6, [1], lambda f, c: "=SUM(A1:A3)+A4")
        assert q.verdict == "nul"
        assert q.max_abs_delta == pytest.approx(0.0)

    def test_unevaluable_yields_indeterminate_not_a_number(self, snap):
        q = Q.quantify(snap, "S", 9, [1], lambda f, c: "=A1*A3")
        assert q.verdict == "indetermine"
        assert q.max_abs_delta == 0.0
        assert q.reason, "le motif de l'indetermination doit etre expose"

    def test_evidence_is_self_contained(self, snap):
        q = Q.quantify(snap, "S", 6, [1], lambda f, c: "=SUM(A1:A2)")
        evidence = q.to_evidence()
        assert evidence["chiffrage"] == "actif"
        assert evidence["detail_colonnes"][0]["cache"] == pytest.approx(100.0)
        assert evidence["detail_colonnes"][0]["recalcul_formule_attendue"] == pytest.approx(30.0)


class TestQuantifyWithZone:
    def test_populated_zone_makes_the_gap_latent(self, tmp_path):
        """Ecart nul mais zone peuplee de zeros : l'erreur mordra plus tard."""
        b = FixtureBuilder()
        b.cell("S", 1, 1, None, 0.0)
        b.cell("S", 2, 1, None, 0.0)
        b.cell("S", 3, 1, None, 5.0)
        b.cell("S", 6, 1, "=SUM(A3:A3)", 5.0)
        snap = L.collect(b.save(tmp_path / "latent.xlsx"))

        q = Q.quantify_with_zone(
            snap, "S", 6, [1],
            rewrite=lambda f, c: "=SUM(A1:A3)",
            zone_for_col=lambda c: R.parse_ref("A1:A2", "S"),
        )
        assert q.max_abs_delta == pytest.approx(0.0)
        assert q.verdict == "latent"

    def test_empty_zone_makes_the_gap_null(self, tmp_path):
        b = FixtureBuilder()
        b.cell("S", 3, 1, None, 5.0)
        b.cell("S", 6, 1, "=SUM(A3:A3)", 5.0)
        snap = L.collect(b.save(tmp_path / "nul.xlsx"))

        q = Q.quantify_with_zone(
            snap, "S", 6, [1],
            rewrite=lambda f, c: "=SUM(A1:A3)",
            zone_for_col=lambda c: R.parse_ref("A1:A2", "S"),
        )
        assert q.verdict == "nul"
