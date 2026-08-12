"""Tests de la couche de donnees de l'interface Streamlit.

L'interface elle-meme (`app.py`) n'est pas importable : `st.stop()` n'a aucun
effet hors du moteur Streamlit, donc importer le script deroulerait toute la mise
en page. C'est precisement pourquoi la logique vit dans `xlaudit.ui`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="l'extra `ui` n'est pas installe")

from xlaudit.ui import (  # noqa: E402
    filter_signals, format_number, persist_upload, resolve_path, restore_run_log,
    restore_signals, run_rules, signal_rows, trace_lines,
)

from .conftest import MAPPING_PATH  # noqa: E402


class FakeUpload:
    """Reproduit le contrat de `st.file_uploader` : des octets et un nom."""

    def __init__(self, path: Path, name: str | None = None) -> None:
        self._payload = Path(path).read_bytes()
        self.name = name or Path(path).name

    def getvalue(self) -> bytes:
        return self._payload


class TestPersistUpload:
    def test_writes_the_file_and_returns_its_fingerprint(self, faulty_path, tmp_path):
        target, sha = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)
        assert target.exists()
        assert target.read_bytes() == Path(faulty_path).read_bytes()
        assert len(sha) == 64

    def test_is_idempotent_for_identical_content(self, faulty_path, tmp_path):
        first, sha1 = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)
        stamp = first.stat().st_mtime_ns
        second, sha2 = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)
        assert (first, sha1) == (second, sha2)
        assert second.stat().st_mtime_ns == stamp, "le fichier ne doit pas etre reecrit"

    def test_different_content_gets_a_different_key(self, faulty_path, healthy_path, tmp_path):
        _a, sha_a = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)
        _b, sha_b = persist_upload(FakeUpload(healthy_path), work_dir=tmp_path)
        assert sha_a != sha_b, "deux classeurs distincts ne doivent pas partager de cache"

    def test_extension_is_preserved(self, faulty_path, tmp_path):
        target, _sha = persist_upload(
            FakeUpload(faulty_path, name="Modele.xlsm"), work_dir=tmp_path
        )
        assert target.suffix == ".xlsm"

    def test_resolve_path_finds_it_back(self, faulty_path, tmp_path):
        target, sha = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)
        assert resolve_path(sha, work_dir=tmp_path) == target

    def test_resolve_path_ignores_derived_deliverables(self, faulty_path, tmp_path):
        """`<sha>_constats.xlsx` ne doit jamais etre pris pour le classeur source."""
        target, sha = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)
        (tmp_path / f"{sha[:16]}_constats.xlsx").write_bytes(b"livrable")
        assert resolve_path(sha, work_dir=tmp_path) == target

    def test_missing_file_raises_a_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="redéposer"):
            resolve_path("0" * 64, work_dir=tmp_path)


class TestFiltering:
    @staticmethod
    def _signals():
        return [
            {"rule_id": "R205", "sheet": "Modele", "confidence": 1.0,
             "refs": ["D35"], "label": "x", "note": "n", "evidence": {"chiffrage": "actif"}},
            {"rule_id": "R215", "sheet": "Modele", "confidence": 0.25,
             "refs": ["20:20"], "label": "y", "note": "n", "evidence": {}},
            {"rule_id": "R215", "sheet": "Autre", "confidence": 0.9,
             "refs": ["7:7"], "label": "z", "note": "n", "evidence": {}},
        ]

    def test_confidence_threshold(self):
        assert len(filter_signals(self._signals(), min_confidence=0.5)) == 2

    def test_rule_filter(self):
        kept = filter_signals(self._signals(), rules=["R215"])
        assert {s["rule_id"] for s in kept} == {"R215"}

    def test_sheet_filter(self):
        kept = filter_signals(self._signals(), sheets=["Autre"])
        assert len(kept) == 1 and kept[0]["sheet"] == "Autre"

    def test_filtering_never_mutates_the_source(self):
        """Le filtre est un filtre d'affichage : les exports repartent du complet."""
        signals = self._signals()
        filter_signals(signals, min_confidence=0.99)
        assert len(signals) == 3


class TestRows:
    def test_columns_are_stable(self):
        rows = signal_rows(
            [
                {"rule_id": "R206", "sheet": "S", "confidence": 0.9, "refs": ["F37"],
                 "label": "Total", "note": "tronquee",
                 "evidence": {"chiffrage": "actif", "ecart_max_absolu": 166.0}}
            ]
        )
        assert list(rows[0]) == [
            "Règle", "Confiance", "Onglet", "Références", "Libellé",
            "Chiffrage", "Écart max", "Constat",
        ]
        assert rows[0]["Écart max"] == 166.0
        assert "actif" in rows[0]["Chiffrage"]

    def test_missing_evidence_does_not_break(self):
        rows = signal_rows(
            [{"rule_id": "R101", "sheet": "S", "confidence": 0.1, "refs": [],
              "label": "", "note": "", "evidence": {}}]
        )
        assert rows[0]["Chiffrage"] == ""
        assert rows[0]["Écart max"] is None


class TestFormatting:
    @pytest.mark.parametrize(
        "value,expected",
        [(None, "—"), (True, "oui"), (False, "non"), (1234.5, "1 234"), ("x", "x")],
    )
    def test_format_number(self, value, expected):
        assert format_number(value) == expected


class TestTraceLines:
    def test_renders_a_nested_tree(self):
        node = {
            "ref": "Modele!D18", "label": "Marge", "formula": "=D10-D16", "value": 600.0,
            "children": [
                {"ref": "Modele!D10", "label": "Total produits",
                 "formula": "=SUM(D6:D9)", "value": 1000.0, "children": []}
            ],
        }
        lines = trace_lines(node)
        assert lines[0].startswith("Modele!D18")
        assert "[Marge]" in lines[0] and "=D10-D16" in lines[0]
        assert lines[1].startswith("    └── Modele!D10")

    def test_truncation_note_is_shown(self):
        node = {"ref": "S!A1", "children": [], "note": "profondeur maximale atteinte"}
        assert "(profondeur maximale atteinte)" in trace_lines(node)[0]


class TestPipeline:
    """Le chemin complet dépôt → analyse, hors de toute mise en page."""

    def test_scan_from_an_uploaded_workbook(self, faulty_path, tmp_path, monkeypatch):
        import xlaudit.ui as ui

        monkeypatch.setattr(ui, "WORK_DIR", tmp_path)
        monkeypatch.setattr(ui, "CACHE_DIR", tmp_path / "cache")
        _target, sha = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)

        document = run_rules(sha, (2,), (), None)
        rules = {s["rule_id"] for s in document["signals"]}
        assert {"R204", "R205", "R206", "R207", "R208"} <= rules
        assert document["run"]["sha256"]
        assert document["validation_mapping"] == []

    def test_mapping_drives_phase_three(self, faulty_path, tmp_path, monkeypatch):
        import xlaudit.ui as ui

        monkeypatch.setattr(ui, "WORK_DIR", tmp_path)
        monkeypatch.setattr(ui, "CACHE_DIR", tmp_path / "cache")
        _target, sha = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)

        document = run_rules(
            sha, (3,), (), MAPPING_PATH.read_text(encoding="utf-8")
        )
        assert document["validation_mapping"], "la validation doit etre rapportee"
        assert all(v["valide"] for v in document["validation_mapping"])
        controls = {
            (s["evidence"] or {}).get("controle") for s in document["signals"]
        }
        assert "bilan" in controls

    def test_restored_objects_feed_the_renderers(self, faulty_path, tmp_path, monkeypatch):
        import xlaudit.ui as ui

        monkeypatch.setattr(ui, "WORK_DIR", tmp_path)
        monkeypatch.setattr(ui, "CACHE_DIR", tmp_path / "cache")
        _target, sha = persist_upload(FakeUpload(faulty_path), work_dir=tmp_path)
        document = run_rules(sha, (2,), (), None)

        from xlaudit.render.markdown import render_markdown
        from xlaudit.render.xlsx import write_report

        signals = restore_signals(document["signals"])
        log = restore_run_log(document["run"])
        assert signals and log.rules

        text = render_markdown(signals, log)
        assert "ne contient aucun constat d'audit" in text
        out = write_report(signals, tmp_path / "constats.xlsx", log)
        assert out.exists() and out.stat().st_size > 0
