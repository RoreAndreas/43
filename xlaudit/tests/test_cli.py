"""Tests de bout en bout de la ligne de commande."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from xlaudit.cli import app

from .conftest import MAPPING_PATH

runner = CliRunner()


def run(*args):
    return runner.invoke(app, [str(a) for a in args])


@pytest.fixture(scope="module")
def scanned(tmp_path_factory, faulty_path):
    """Un scan complet, reutilise par plusieurs tests."""
    out = tmp_path_factory.mktemp("cli") / "signaux.json"
    result = run("scan", faulty_path, "--phases", "1,2", "--out", out,
                 "--cache-dir", out.parent / "cache")
    assert result.exit_code == 0, result.output
    return json.loads(out.read_text(encoding="utf-8")), out


class TestScan:
    def test_writes_a_versioned_document(self, scanned):
        document, _path = scanned
        assert document["schema_version"] == "1.0"
        assert document["signal_count"] > 0

    def test_every_planted_anomaly_is_reported(self, scanned):
        document, _path = scanned
        rules = {s["rule_id"] for s in document["signals"]}
        assert {"R201", "R202", "R203", "R204", "R205", "R206", "R207", "R208", "R215"} <= rules

    def test_run_log_records_the_fingerprint(self, scanned):
        document, _path = scanned
        assert len(document["run"]["sha256"]) == 64
        assert document["run"]["started_at"]
        assert document["run"]["rules"]

    def test_rule_selection(self, faulty_path, tmp_path):
        out = tmp_path / "r205.json"
        result = run("scan", faulty_path, "--rules", "R205", "--out", out,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        document = json.loads(out.read_text(encoding="utf-8"))
        assert {s["rule_id"] for s in document["signals"]} == {"R205"}

    def test_phase_3_is_skipped_without_mapping(self, faulty_path, tmp_path):
        out = tmp_path / "p3.json"
        result = run("scan", faulty_path, "--phases", "3", "--out", out,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        document = json.loads(out.read_text(encoding="utf-8"))
        skipped = [r for r in document["run"]["rules"] if r["status"] == "skipped"]
        assert skipped and "mapping" in skipped[0]["reason"]

    def test_missing_workbook_is_reported(self, tmp_path):
        result = run("scan", tmp_path / "absent.xlsx")
        assert result.exit_code == 2
        assert "introuvable" in result.output

    def test_cache_is_reused_on_second_run(self, faulty_path, tmp_path):
        cache = tmp_path / "cache"
        first = run("scan", faulty_path, "--rules", "R205", "--cache-dir", cache,
                    "--out", tmp_path / "a.json")
        second = run("scan", faulty_path, "--rules", "R205", "--cache-dir", cache,
                     "--out", tmp_path / "b.json")
        assert first.exit_code == second.exit_code == 0
        assert "collecte" in first.output
        assert "cache" in second.output


class TestTrace:
    def test_upward_trace_shows_formulas_and_values(self, faulty_path, tmp_path):
        result = run("trace", faulty_path, "--cell", "Modele!D18", "--depth", "2",
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        assert "Modele!D18" in result.output
        assert "=D10-D16" in result.output
        assert "Total produits" in result.output

    def test_downward_trace(self, faulty_path, tmp_path):
        result = run("trace", faulty_path, "--cell", "Modele!D10", "--direction", "down",
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        assert "Modele!D18" in result.output

    def test_json_output(self, faulty_path, tmp_path):
        out = tmp_path / "trace.json"
        result = run("trace", faulty_path, "--cell", "Modele!D18", "--out", out,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        document = json.loads(out.read_text(encoding="utf-8"))
        assert document["cellule"] == "Modele!D18"
        assert document["trace"]["children"]

    def test_malformed_reference_is_rejected(self, faulty_path, tmp_path):
        result = run("trace", faulty_path, "--cell", "D18", "--cache-dir", tmp_path / "c")
        assert result.exit_code == 2
        assert "invalide" in result.output

    def test_unknown_sheet_lists_the_available_ones(self, faulty_path, tmp_path):
        result = run("trace", faulty_path, "--cell", "Absent!D18",
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 2
        assert "Modele" in result.output


class TestMappingCommands:
    def test_validate_accepts_the_fixture_mapping(self, faulty_path, tmp_path):
        result = run("validate-mapping", faulty_path, "--mapping", MAPPING_PATH,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        assert "confirmees" in result.output

    def test_validate_fails_on_a_wrong_row(self, faulty_path, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            MAPPING_PATH.read_text(encoding="utf-8").replace("row: 20", "row: 999"),
            encoding="utf-8",
        )
        result = run("validate-mapping", faulty_path, "--mapping", bad,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 1
        assert "rejete" in result.output

    def test_ties_finds_the_imbalance(self, faulty_path, tmp_path):
        out = tmp_path / "ties.json"
        result = run("ties", faulty_path, "--mapping", MAPPING_PATH, "--out", out,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        document = json.loads(out.read_text(encoding="utf-8"))
        controls = {s["evidence"]["controle"] for s in document["signals"]}
        assert "bilan" in controls

    def test_ties_is_silent_on_a_healthy_model(self, healthy_path, tmp_path):
        out = tmp_path / "ties.json"
        result = run("ties", healthy_path, "--mapping", MAPPING_PATH, "--out", out,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        assert json.loads(out.read_text(encoding="utf-8"))["signal_count"] == 0

    def test_discover_then_validate(self, faulty_path, tmp_path):
        mapping = tmp_path / "auto.yaml"
        first = run("discover", faulty_path, "--out", mapping, "--cache-dir", tmp_path / "c")
        assert first.exit_code == 0
        assert mapping.exists()
        assert "Aucune localisation n'est confirmee" in first.output
        second = run("validate-mapping", faulty_path, "--mapping", mapping,
                     "--cache-dir", tmp_path / "c")
        assert second.exit_code == 0, second.output

    def test_invalid_mapping_file_is_rejected(self, faulty_path, tmp_path):
        bad = tmp_path / "invalide.yaml"
        bad.write_text("periodes: {sheet: S}\n", encoding="utf-8")
        result = run("ties", faulty_path, "--mapping", bad, "--cache-dir", tmp_path / "c")
        assert result.exit_code == 2
        assert "invalide" in result.output


class TestOtherCommands:
    def test_map_writes_mermaid(self, faulty_path, tmp_path):
        out = tmp_path / "carte.mmd"
        result = run("map", faulty_path, "--out", out, "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        assert "graph LR" in out.read_text(encoding="utf-8")

    def test_feasibility_passes_on_a_plain_workbook(self, faulty_path, tmp_path):
        result = run("feasibility", faulty_path, "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        assert "envisageable" in result.output

    def test_feasibility_refuses_when_functions_are_unsupported(self, tmp_path):
        from .fixtures import FixtureBuilder

        b = FixtureBuilder()
        b.cell("S", 1, 1, None, 1.0)
        b.cell("S", 2, 1, "=XLOOKUP(A1,A1:A1,A1:A1)", 1.0)
        b.cell("S", 3, 1, "=LET(x,A1,x*2)", 2.0)
        path = b.save(tmp_path / "moderne.xlsx")
        result = run("feasibility", path, "--cache-dir", tmp_path / "c")
        assert result.exit_code == 1
        assert "refuse" in result.output
        assert "XLOOKUP" in result.output

    def test_report_produces_both_deliverables(self, scanned, tmp_path):
        _document, signals_path = scanned
        xlsx = tmp_path / "constats.xlsx"
        md = tmp_path / "rapport.md"
        result = run("report", signals_path, "--xlsx", xlsx, "--md", md)
        assert result.exit_code == 0
        assert xlsx.exists() and md.exists()
        assert "ne contient aucun constat d'audit" in md.read_text(encoding="utf-8")

    def test_report_requires_an_output(self, scanned):
        _document, signals_path = scanned
        result = run("report", signals_path)
        assert result.exit_code == 2

    def test_sensitivity_reports_reach_without_inventing_amounts(self, faulty_path, tmp_path):
        out = tmp_path / "choc.json"
        result = run("sensitivity", faulty_path, "--shock", "Total produits=-5%",
                     "--out", out, "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        assert "n'est pas chiffree" in result.output
        document = json.loads(out.read_text(encoding="utf-8"))
        signal = document["signals"][0]
        assert signal["evidence"]["lignes_atteintes"] > 0
        assert "refuse de simuler" in signal["evidence"]["chiffrage"]

    def test_diff_separates_new_from_resolved(self, healthy_path, faulty_path, tmp_path):
        out = tmp_path / "diff.json"
        result = run("diff", healthy_path, faulty_path, "--phases", "2", "--out", out,
                     "--cache-dir", tmp_path / "c")
        assert result.exit_code == 0
        document = json.loads(out.read_text(encoding="utf-8"))
        appeared = {s["rule_id"] for s in document["apparus"]}
        assert {"R204", "R205", "R206", "R207", "R208"} <= appeared
        assert document["avant"]["sha256"] != document["apres"]["sha256"]
