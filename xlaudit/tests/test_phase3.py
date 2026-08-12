"""Tests du mapping et des bouclages de la phase 3."""

from __future__ import annotations

import copy

import pytest
import yaml
from pydantic import ValidationError

from xlaudit.mapping.discover import discover, normalise, score_label
from xlaudit.mapping.schema import MappingModel, dump_mapping, load_mapping
from xlaudit.mapping.validate import validate_mapping
from xlaudit.models import AuditContext
from xlaudit.rules.p3_ties import R301Ties

from .conftest import MAPPING_PATH

TIES_SHEET = "Etats fi periode"


@pytest.fixture
def mapping():
    return load_mapping(MAPPING_PATH)


class TestSchema:
    def test_loads_the_fixture_mapping(self, mapping):
        assert mapping.periodes.sheet == TIES_SHEET
        assert mapping.periodes.columns() == list(range(15, 21))  # O..T
        assert mapping.bilan.actif_total.row == 20

    def test_rejects_unknown_keys(self):
        with pytest.raises(ValidationError):
            MappingModel.model_validate(
                {
                    "periodes": {"sheet": "S", "ligne_index": 1, "colonnes": "A:C"},
                    "inconnu": 1,
                }
            )

    def test_rejects_a_mapping_that_allows_no_check(self):
        with pytest.raises(ValidationError, match="aucun controle"):
            MappingModel.model_validate(
                {"periodes": {"sheet": "S", "ligne_index": 1, "colonnes": "A:C"}}
            )

    def test_rejects_malformed_column_range(self):
        with pytest.raises(ValidationError):
            MappingModel.model_validate(
                {
                    "periodes": {"sheet": "S", "ligne_index": 1, "colonnes": "O"},
                    "bilan": {"actif_total": {"sheet": "S", "row": 1}},
                }
            )

    def test_roundtrip_through_yaml(self, mapping, tmp_path):
        out = tmp_path / "m.yaml"
        dump_mapping(mapping, out)
        text = out.read_text(encoding="utf-8")
        assert "validation_note: ''" not in text
        assert load_mapping(out).bilan.actif_total.row == 20


class TestValidation:
    def test_confirms_every_location_of_the_fixture(self, faulty_ctx, mapping):
        results = validate_mapping(faulty_ctx.snapshot, mapping)
        rejected = [r for r in results if not r.ok]
        assert not rejected, [(r.key, r.note) for r in rejected]

    def test_marks_the_mapping_in_place(self, faulty_ctx, mapping):
        validate_mapping(faulty_ctx.snapshot, mapping)
        assert mapping.bilan.actif_total.validated is True

    def test_rejects_a_row_pointing_at_nothing(self, faulty_ctx, mapping):
        mapping.bilan.actif_total.row = 999
        results = {r.key: r for r in validate_mapping(faulty_ctx.snapshot, mapping)}
        assert results["bilan.actif_total"].ok is False
        assert "valeur numerique" in results["bilan.actif_total"].note

    def test_rejects_a_total_that_is_not_computed(self, faulty_ctx, mapping):
        """Un total saisi en dur n'est pas un total : la ligne 21 est constante."""
        mapping.bilan.actif_total.row = 21
        results = {r.key: r for r in validate_mapping(faulty_ctx.snapshot, mapping)}
        assert results["bilan.actif_total"].ok is False
        assert "calcule" in results["bilan.actif_total"].note

    def test_rejects_an_unknown_sheet(self, faulty_ctx, mapping):
        mapping.bilan.actif_total.sheet = "Onglet inexistant"
        results = {r.key: r for r in validate_mapping(faulty_ctx.snapshot, mapping)}
        assert results["bilan.actif_total"].ok is False


class TestTies:
    def _run(self, ctx, mapping):
        validate_mapping(ctx.snapshot, mapping)
        scoped = AuditContext(snapshot=ctx.snapshot, graph=ctx.graph, mapping=mapping)
        return R301Ties().run(scoped), scoped

    def test_detects_the_one_cent_imbalance(self, faulty_ctx, mapping):
        signals, _ctx = self._run(faulty_ctx, mapping)
        bilan = [s for s in signals if s.evidence.get("controle") == "bilan"]
        assert len(bilan) == 1
        assert bilan[0].evidence["ecart_maximal"] == pytest.approx(0.01, abs=1e-9)
        assert bilan[0].evidence["periodes_en_ecart"] == 1

    def test_reports_which_period_broke(self, faulty_ctx, mapping):
        signals, _ctx = self._run(faulty_ctx, mapping)
        bilan = next(s for s in signals if s.evidence.get("controle") == "bilan")
        assert bilan.evidence["premiere_periode_en_ecart"] == "4"
        assert bilan.evidence["detail"][0]["ecart"] == pytest.approx(-0.01, abs=1e-9)

    def test_confidence_reflects_size_against_tolerance(self, faulty_ctx, mapping):
        signals, _ctx = self._run(faulty_ctx, mapping)
        bilan = next(s for s in signals if s.evidence.get("controle") == "bilan")
        # 0.01 contre une tolerance de 1e-6 : quatre ordres de grandeur au-dessus.
        assert bilan.confidence == pytest.approx(0.95)

    def test_healthy_workbook_ties_out(self, healthy_ctx, mapping):
        signals, _ctx = self._run(healthy_ctx, mapping)
        assert signals == [], [(s.label, s.note) for s in signals]

    def test_cascade_matches_balance_sheet_treasury(self, healthy_ctx, mapping):
        signals, _ctx = self._run(healthy_ctx, mapping)
        assert not [s for s in signals if s.evidence.get("controle") == "cascade_vs_bilan"]

    def test_continuity_breach_is_detected(self, faulty_ctx, mapping):
        """Debrancher l'ouverture de la cloture doit casser la continuite."""
        broken = copy.deepcopy(mapping)
        broken.cascade.solde_ouverture.row = 42  # variation, pas le solde d'ouverture
        signals, _ctx = self._run(faulty_ctx, broken)
        assert [s for s in signals if s.evidence.get("controle") == "continuite"]

    def test_unvalidated_location_is_skipped_not_guessed(self, faulty_ctx, mapping):
        """Un controle ne s'execute jamais sur une localisation rejetee."""
        mapping.bilan.passif_total.row = 999
        signals, ctx = self._run(faulty_ctx, mapping)
        assert not [s for s in signals if s.evidence.get("controle") == "bilan"]
        codes = {r.code for r in ctx.reserves}
        assert "P3_LOCALISATIONS_NON_VALIDEES" in codes

    def test_negative_treasury_is_analysed(self, faulty_ctx, mapping):
        """Une cascade negative doit produire une decomposition, pas juste un flag."""
        negative = copy.deepcopy(mapping)
        # La ligne 42 (variation) descend sous zero : on la designe comme cloture
        # pour eprouver l'analyseur sans reconstruire un classeur.
        sheet = faulty_ctx.snapshot.sheet(TIES_SHEET)
        original = dict(sheet.values)
        try:
            for col in negative.periodes.columns()[2:4]:
                sheet.values[(40, col)] = -500.0
            signals, _ctx = self._run(faulty_ctx, negative)
            treso = [
                s for s in signals
                if s.evidence.get("controle") == "tresorerie_negative"
            ]
            assert len(treso) == 1
            evidence = treso[0].evidence
            assert evidence["periodes_negatives"] == 2
            assert evidence["solde_minimal"] == pytest.approx(-500.0)
            assert evidence["detail"][0]["etage_de_bascule"]
        finally:
            sheet.values.clear()
            sheet.values.update(original)

    def test_non_negativity_breach(self, faulty_ctx, mapping):
        sheet = faulty_ctx.snapshot.sheet(TIES_SHEET)
        original = sheet.values.get((15, 17))
        try:
            sheet.values[(15, 17)] = -12.5
            signals, _ctx = self._run(faulty_ctx, mapping)
            breaches = [
                s for s in signals if s.evidence.get("controle") == "non_negativite"
            ]
            assert len(breaches) == 1
            assert breaches[0].evidence["minimum"] == pytest.approx(-12.5)
        finally:
            if original is None:
                sheet.values.pop((15, 17), None)
            else:
                sheet.values[(15, 17)] = original


class TestDiscover:
    def test_normalisation_strips_accents_and_case(self):
        assert normalise("Trésorerie  d'OUVERTURE") == "tresorerie d ouverture"

    def test_exact_match_scores_one(self):
        score, matched = score_label("Total actif", ("total actif",), ("passif",))
        assert score == 1.0 and matched == "total actif"

    def test_rejected_term_zeroes_the_score(self):
        score, _ = score_label("Total actif et passif", ("total actif",), ("passif",))
        assert score == 0.0

    def test_finds_the_balance_sheet_rows(self, faulty_ctx):
        mapping, found = discover(faulty_ctx.snapshot)
        assert mapping is not None
        assert mapping.bilan.actif_total.row == 20
        assert mapping.bilan.passif_total.row == 30
        assert {d.key for d in found} >= {"bilan.actif_total", "bilan.passif_total"}

    def test_periods_are_taken_from_the_hosting_sheet(self, faulty_ctx):
        """Les colonnes de periode doivent etre celles des lignes trouvees."""
        mapping, _found = discover(faulty_ctx.snapshot)
        assert mapping.periodes.sheet == TIES_SHEET
        assert mapping.periodes.columns()[0] == 15  # colonne O

    def test_proposals_are_never_pre_validated(self, faulty_ctx):
        mapping, _found = discover(faulty_ctx.snapshot)
        assert mapping.bilan.actif_total.validated is None

    def test_discovered_mapping_passes_validation(self, faulty_ctx):
        mapping, _found = discover(faulty_ctx.snapshot)
        results = validate_mapping(faulty_ctx.snapshot, mapping)
        assert not [r for r in results if not r.ok], [
            (r.key, r.note) for r in results if not r.ok
        ]
