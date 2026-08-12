"""Tests du parsing de references. Toutes les regles en dependent."""

from __future__ import annotations

import pytest

from xlaudit.core import refs as R


class TestColumnConversion:
    @pytest.mark.parametrize(
        "letters,index",
        [("A", 1), ("Z", 26), ("AA", 27), ("AZ", 52), ("BA", 53), ("XFD", 16384)],
    )
    def test_roundtrip(self, letters, index):
        assert R.col_to_index(letters) == index
        assert R.index_to_col(index) == letters

    def test_lowercase(self):
        assert R.col_to_index("ab") == 28

    def test_invalid(self):
        with pytest.raises(ValueError):
            R.col_to_index("A1")


class TestParseRef:
    def test_single_cell(self):
        ref = R.parse_ref("B7")
        assert ref is not None and ref.is_single
        assert (ref.start.col, ref.start.row) == (2, 7)
        assert not ref.start.col_abs and not ref.start.row_abs

    def test_absolute(self):
        ref = R.parse_ref("$B$7")
        assert ref.start.col_abs and ref.start.row_abs
        assert ref.a1 == "$B$7"

    def test_range_dimensions(self):
        ref = R.parse_ref("D6:F9")
        assert (ref.width, ref.height) == (3, 4)
        assert (ref.min_col, ref.max_col, ref.min_row, ref.max_row) == (4, 6, 6, 9)

    def test_sheet_prefix(self):
        ref = R.parse_ref("Financement!A1:B2")
        assert ref.sheet == "Financement"

    def test_quoted_sheet_with_space(self):
        ref = R.parse_ref("'Etats fi periode'!O10:HU10")
        assert ref.sheet == "Etats fi periode"
        assert ref.min_col == R.col_to_index("O")
        assert ref.max_col == R.col_to_index("HU")

    def test_default_sheet_applied(self):
        ref = R.parse_ref("A1", default_sheet="Modele")
        assert ref.sheet == "Modele"

    def test_explicit_sheet_wins_over_default(self):
        ref = R.parse_ref("Autre!A1", default_sheet="Modele")
        assert ref.sheet == "Autre"

    def test_whole_column(self):
        ref = R.parse_ref("C:C")
        assert ref.whole_col and ref.min_col == 3 and ref.max_col == 3

    def test_whole_row(self):
        ref = R.parse_ref("10:12")
        assert ref.whole_row and ref.min_row == 10 and ref.max_row == 12

    def test_defined_name_is_not_a_ref(self):
        assert R.parse_ref("MonNom") is None
        assert R.parse_ref("Taux_actualisation") is None

    def test_out_of_bounds_is_not_a_ref(self):
        # ZZZ9999999 depasse les bornes d'Excel : c'est un nom, pas une plage.
        assert R.parse_ref("ZZZ9999999") is None

    def test_roundtrip_a1(self):
        for text in ["A1", "$A$1", "D6:F9", "$O488:S491", "O488:$S491"]:
            assert R.parse_ref(text).a1 == text


class TestAnchorPattern:
    def test_symmetric_relative(self):
        assert R.parse_ref("D6:F9").anchor_pattern == "RR:RR"

    def test_fully_anchored(self):
        assert R.parse_ref("$D$6:$F$9").anchor_pattern == "AA:AA"

    def test_asymmetric_column_anchor(self):
        # Le motif de R205 : coin initial ancre en colonne, coin final relatif.
        assert R.parse_ref("$O488:S491").anchor_pattern == "AR:RR"

    def test_asymmetric_mirror(self):
        assert R.parse_ref("O488:$S491").anchor_pattern == "RR:AR"


class TestR1C1:
    def test_relative_same_row(self):
        assert R.parse_ref("C5").to_r1c1(anchor_row=5, anchor_col=4) == "RC[-1]"

    def test_self_reference(self):
        assert R.parse_ref("D5").to_r1c1(anchor_row=5, anchor_col=4) == "RC"

    def test_absolute_column(self):
        assert R.parse_ref("$B5").to_r1c1(anchor_row=5, anchor_col=4) == "RC2"

    def test_formula_normalization_makes_copies_identical(self):
        """Deux colonnes portant la meme formule recopiee donnent la meme chaine."""
        a = R.to_r1c1("=D18*0.7", row=20, col=4)
        b = R.to_r1c1("=E18*0.7", row=20, col=5)
        assert a == b == "=R[-2]C*0.7"

    def test_formula_normalization_separates_variants(self):
        base = R.to_r1c1("=E18/$D$18", row=22, col=5)
        variant = R.to_r1c1("=E18/D18", row=22, col=5)
        assert base != variant

    def test_defined_names_are_left_alone(self):
        out = R.to_r1c1("=SUM(A1:A5)*Taux_actualisation", row=1, col=1)
        assert "Taux_actualisation" in out

    def test_string_literal_containing_colon_is_untouched(self):
        out = R.to_r1c1('=IF(A1>0,"a:b","c")', row=1, col=1)
        assert '"a:b"' in out


class TestExtraction:
    def test_extract_refs_skips_string_literals(self):
        refs = R.extract_refs('=SUMIF($A$1:A10,"tot(al",B1:C10)', default_sheet="S")
        assert [r.a1 for r in refs] == ["S!$A$1:A10", "S!B1:C10"]

    def test_extract_functions_normalizes(self):
        assert R.extract_functions("=_xlfn.XLOOKUP(A1,B:B,C:C)") == ["XLOOKUP"]
        assert R.extract_functions("=SOMME.SI(A1:A5,B1:B5)") == ["SUMIF"]

    def test_nested_functions(self):
        assert R.extract_functions("=IF(SUM(A1:A2)>0,MAX(B1:B2),0)") == ["IF", "SUM", "MAX"]

    def test_extract_names(self):
        assert R.extract_names("=SUM(A1:A5)+Taux") == ["Taux"]

    def test_array_formula_text_is_parseable(self):
        refs = R.extract_refs("=SUM(B2:B5*2)", default_sheet="S")
        assert [r.a1 for r in refs] == ["S!B2:B5"]


class TestParseCalls:
    def test_arguments_of_sumif(self):
        calls = R.parse_calls('=SUMIF($D$44:$D$47,"A",$E$44:$F$47)')
        assert len(calls) == 1
        call = calls[0]
        assert call.name == "SUMIF"
        assert call.arity == 3
        assert call.arg_refs[0].width == 1
        assert call.arg_refs[2].width == 2
        assert call.arg_refs[1] is None  # le critere n'est pas une plage

    def test_semicolon_separator(self):
        call = R.parse_calls("=SUMIF(A1:A5;B1:B5)")[0]
        assert call.arity == 2

    def test_comma_inside_string_does_not_split(self):
        call = R.parse_calls('=SUMIF(A1:A5,"x,y",B1:B5)')[0]
        assert call.arity == 3

    def test_nested_call_arguments_are_not_confused(self):
        calls = {c.name: c for c in R.parse_calls("=IF(SUM(A1:A2)>0,MAX(B1:B2),0)")}
        assert calls["IF"].arity == 3
        assert calls["SUM"].arity == 1
        assert calls["MAX"].arity == 1

    def test_parenthesised_subexpression(self):
        call = R.parse_calls("=ROUND((A1+A2)*B1,2)")[0]
        assert call.name == "ROUND"
        assert call.arity == 2


class TestTopLevelTerms:
    def test_simple_sum_of_terms(self):
        terms = R.top_level_terms("=D10+D16")
        assert terms == [("+", "D10"), ("+", "D16")]

    def test_three_terms_with_subtraction(self):
        terms = R.top_level_terms("=A1+SUM(B1:B5)-C1")
        assert terms == [("+", "A1"), ("+", "SUM(B1:B5)"), ("-", "C1")]

    def test_separator_inside_function_is_not_a_term(self):
        terms = R.top_level_terms("=SUM(A1,B1)")
        assert len(terms) == 1

    def test_product_is_not_additive(self):
        assert R.top_level_terms("=A1*B1") == []

    def test_single_term(self):
        assert R.top_level_terms("=D18") == [("+", "D18")]


class TestErrorLiterals:
    def test_detects_error(self):
        assert R.contains_error_literal("#DIV/0!") == "#DIV/0!"
        assert R.contains_error_literal("=#REF!*2") == "#REF!"

    def test_no_false_positive(self):
        assert R.contains_error_literal("=A1+B1") is None
        assert R.contains_error_literal("Chiffre d'affaires") is None
