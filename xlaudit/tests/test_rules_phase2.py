"""Tests des regles de la phase 2.

Chaque regle est eprouvee deux fois : elle doit detecter son anomalie dans le
classeur fautif, et **ne rien detecter** dans le classeur sain. Le test de
non-detection compte autant que l'autre — une regle qui crie sur un modele
correct est inutilisable en pratique.
"""

from __future__ import annotations

import pytest

from xlaudit.rules.p2_r201_cached_errors import R201CachedErrors
from xlaudit.rules.p2_r202_hardcoded import R202Hardcoded
from xlaudit.rules.p2_r203_horizontal import R203Horizontal
from xlaudit.rules.p2_r204_copy_drift import R204CopyDrift
from xlaudit.rules.p2_r205_anchoring import R205Anchoring
from xlaudit.rules.p2_r206_truncated_sum import R206TruncatedSum
from xlaudit.rules.p2_r207_sumif_width import R207SumRangeWidth
from xlaudit.rules.p2_r208_heterogeneous_sum import R208HeterogeneousSum
from xlaudit.rules.p2_r215_orphans import R215Orphans

from .conftest import refs_of, signals_of


class TestR201CachedErrors:
    def test_detects_div_zero_and_ref(self, faulty_ctx):
        signals = signals_of(R201CachedErrors(), faulty_ctx)
        assert refs_of(signals) == {"F57", "D59"}
        errors = {s.evidence["erreur"] for s in signals}
        assert errors == {"#DIV/0!", "#REF!"}

    def test_identifies_the_upstream_cause(self, faulty_ctx):
        signals = signals_of(R201CachedErrors(), faulty_ctx)
        div = next(s for s in signals if s.refs == ["F57"])
        assert div.evidence["formule_conforme_a_la_ligne"] is True
        assert any("F56 = 0" in cause for cause in div.evidence["cellules_amont_en_cause"])

    def test_proposes_a_twin_cell(self, faulty_ctx):
        signals = signals_of(R201CachedErrors(), faulty_ctx)
        div = next(s for s in signals if s.refs == ["F57"])
        assert div.evidence["cellule_jumelle"].endswith("57")
        assert div.evidence["formule_jumelle"].startswith("=")

    def test_no_signal_on_healthy(self, healthy_ctx):
        assert signals_of(R201CachedErrors(), healthy_ctx, sheet=None) == []


class TestR202Hardcoded:
    def test_detects_constant_in_a_formula_row(self, faulty_ctx):
        signals = signals_of(R202Hardcoded(), faulty_ctx)
        assert {"F20", "H55"} <= refs_of(signals)

    def test_control_label_raises_confidence(self, faulty_ctx):
        signals = {s.refs[0]: s for s in signals_of(R202Hardcoded(), faulty_ctx)}
        assert signals["H55"].evidence["libelle_de_controle"] == "controle"
        assert signals["H55"].confidence > signals["F20"].confidence

    def test_proposes_the_majority_formula(self, faulty_ctx):
        signals = {s.refs[0]: s for s in signals_of(R202Hardcoded(), faulty_ctx)}
        assert signals["F20"].expected == "=F18*0.7"

    def test_input_rows_of_constants_are_not_flagged(self, faulty_ctx):
        """Les lignes 6 a 9 sont entierement constantes : ce sont des entrees."""
        refs = refs_of(signals_of(R202Hardcoded(), faulty_ctx))
        assert not any(ref.endswith(("6", "7", "8", "9")) for ref in refs if ref[1:].isdigit())

    def test_no_high_confidence_signal_on_healthy(self, healthy_ctx):
        signals = signals_of(R202Hardcoded(), healthy_ctx, sheet=None)
        # Une constante d'initialisation en colonne de bord reste exposee, mais
        # avec une confiance basse : c'est la convention, pas une anomalie.
        assert all(s.confidence < 0.6 for s in signals), [
            (s.refs, s.confidence) for s in signals
        ]


class TestR203Horizontal:
    def test_detects_the_minority_variant(self, faulty_ctx):
        signals = signals_of(R203Horizontal(), faulty_ctx)
        assert "G22" in refs_of(signals)

    def test_proposes_the_majority_formula_transposed(self, faulty_ctx):
        signal = next(s for s in signals_of(R203Horizontal(), faulty_ctx) if s.refs == ["G22"])
        assert signal.observed == "=G18/D18"
        assert signal.expected == "=G18/$D$18"

    def test_isolated_middle_variant_scores_high(self, faulty_ctx):
        signal = next(s for s in signals_of(R203Horizontal(), faulty_ctx) if s.refs == ["G22"])
        assert signal.confidence >= 0.85
        assert signal.evidence["colonnes_de_bord"] is False

    def test_no_signal_on_healthy(self, healthy_ctx):
        assert signals_of(R203Horizontal(), healthy_ctx, sheet=None) == []


class TestR204CopyDrift:
    def test_detects_the_drifting_block(self, faulty_ctx):
        signals = signals_of(R204CopyDrift(), faulty_ctx)
        assert len(signals) == 1
        assert signals[0].refs == ["30:33"]

    def test_reports_captured_subtotal_and_omitted_items(self, faulty_ctx):
        signal = signals_of(R204CopyDrift(), faulty_ctx)[0]
        captured = {c["ligne"] for c in signal.evidence["sous_totaux_captures"]}
        omitted = {o["ligne"] for o in signal.evidence["articles_omis"]}
        assert 10 in captured, "la ligne de total produits est capturee par la derive"
        assert 6 in omitted, "le premier article du bloc finit par etre omis"

    def test_quantifies_the_gap(self, faulty_ctx):
        signal = signals_of(R204CopyDrift(), faulty_ctx)[0]
        assert signal.evidence["chiffrage"] == "actif"
        assert signal.evidence["ecart_max_absolu"] > 0
        assert signal.evidence["cache_confirme_la_formule"] is True

    def test_proposes_an_anchored_range(self, faulty_ctx):
        signal = signals_of(R204CopyDrift(), faulty_ctx)[0]
        assert signal.expected == "=SUM(D$6:D$9)"

    def test_no_signal_on_healthy(self, healthy_ctx):
        assert signals_of(R204CopyDrift(), healthy_ctx, sheet=None) == []


class TestR205Anchoring:
    def test_detects_the_asymmetric_anchor(self, faulty_ctx):
        signals = signals_of(R205Anchoring(), faulty_ctx)
        assert len(signals) == 1
        assert signals[0].evidence["motif_ancrage"] == "AR:RR"

    def test_range_widens_along_the_row(self, faulty_ctx):
        signal = signals_of(R205Anchoring(), faulty_ctx)[0]
        widths = signal.evidence["largeur_par_colonne"]
        assert widths["D"] == 1 and widths["I"] == 6

    def test_exact_cache_match_gives_full_confidence(self, faulty_ctx):
        """L'ecart chiffre egale exactement le terme neutralise."""
        signal = signals_of(R205Anchoring(), faulty_ctx)[0]
        assert signal.evidence["chiffrage"] == "actif"
        assert signal.evidence["cache_confirme_la_formule"] is True
        assert signal.confidence == 1.0

    def test_gap_matches_the_accumulated_columns(self, faulty_ctx):
        """En colonne E, l'ecart doit valoir le total produits de la colonne D."""
        signal = signals_of(R205Anchoring(), faulty_ctx)[0]
        by_ref = {c["ref"]: c for c in signal.evidence["detail_colonnes"]}
        assert by_ref["E35"]["ecart"] == pytest.approx(-1000.0)
        assert by_ref["D35"]["ecart"] in (None, pytest.approx(0.0))

    def test_no_signal_on_healthy(self, healthy_ctx):
        assert signals_of(R205Anchoring(), healthy_ctx, sheet=None) == []


class TestR206TruncatedSum:
    def test_detects_the_short_column(self, faulty_ctx):
        signals = signals_of(R206TruncatedSum(), faulty_ctx)
        assert refs_of(signals) == {"F37"}

    def test_names_the_omitted_row(self, faulty_ctx):
        signal = signals_of(R206TruncatedSum(), faulty_ctx)[0]
        omitted = {o["ligne"]: o["libelle"] for o in signal.evidence["lignes_omises"]}
        assert omitted == {15: "Charge D"}

    def test_quantifies_the_gap(self, faulty_ctx):
        signal = signals_of(R206TruncatedSum(), faulty_ctx)[0]
        assert signal.evidence["chiffrage"] == "actif"
        # Charge D en periode 3 vaut 40*4 + 3*2 = 166.
        assert signal.evidence["ecart_max_absolu"] == pytest.approx(166.0)

    def test_no_signal_on_healthy(self, healthy_ctx):
        assert signals_of(R206TruncatedSum(), healthy_ctx, sheet=None) == []


class TestR207SumRangeWidth:
    def test_detects_the_width_mismatch(self, faulty_ctx):
        signals = signals_of(R207SumRangeWidth(), faulty_ctx)
        assert len(signals) == 1
        evidence = signals[0].evidence
        assert evidence["forme_criteres"] == "4x1"
        assert evidence["forme_somme_citee"] == "4x2"

    def test_reports_both_amounts(self, faulty_ctx):
        """Ce qui est somme, et ce qu'un lecteur croirait somme."""
        evidence = signals_of(R207SumRangeWidth(), faulty_ctx)[0].evidence
        assert evidence["montant_somme"] == pytest.approx(40.0)   # E44 + E46
        assert evidence["montant_apparent"] == pytest.approx(44.0)  # + F44 + F46
        assert evidence["ecart_de_lecture"] == pytest.approx(4.0)
        assert evidence["critere_applique"] is True

    def test_proposes_the_effective_range(self, faulty_ctx):
        signal = signals_of(R207SumRangeWidth(), faulty_ctx)[0]
        assert signal.expected == '=SUMIF($D$44:$D$47,"A",$E$44:$E$47)'

    def test_no_signal_on_healthy(self, healthy_ctx):
        assert signals_of(R207SumRangeWidth(), healthy_ctx, sheet=None) == []


class TestR208HeterogeneousSum:
    def test_detects_the_extra_term(self, faulty_ctx):
        signals = signals_of(R208HeterogeneousSum(), faulty_ctx)
        assert refs_of(signals) == {"F41"}
        assert signals[0].evidence["nombre_majoritaire_de_termes"] == 2

    def test_identifies_the_double_count(self, faulty_ctx):
        signal = signals_of(R208HeterogeneousSum(), faulty_ctx)[0]
        double = signal.evidence["double_comptage"]
        assert double, "la ligne 18 agrege deja la ligne 10"
        assert any("18" in d["explication"] for d in double)

    def test_lists_the_source_blocks(self, faulty_ctx):
        signal = signals_of(R208HeterogeneousSum(), faulty_ctx)[0]
        rows = {b["ligne"] for b in signal.evidence["blocs_sources"]}
        assert rows == {10, 16, 18}

    def test_no_signal_on_healthy(self, healthy_ctx):
        assert signals_of(R208HeterogeneousSum(), healthy_ctx, sheet=None) == []


class TestR215Orphans:
    def test_detects_the_disconnected_channel(self, faulty_ctx):
        signals = signals_of(R215Orphans(), faulty_ctx)
        high = {s.refs[0]: s for s in signals if s.confidence >= 0.8}
        assert "49:49" in high
        assert high["49:49"].label == "Impasse de tresorerie"
        assert high["49:49"].evidence["canal_debranche"] is True

    def test_orphan_has_no_consumer(self, faulty_ctx):
        signal = next(
            s for s in signals_of(R215Orphans(), faulty_ctx) if s.refs == ["49:49"]
        )
        assert signal.consumers == []
        assert signal.evidence["alimentee_par"], "la ligne est bien alimentee en amont"

    def test_generic_labels_score_low(self, faulty_ctx):
        signals = {s.refs[0]: s for s in signals_of(R215Orphans(), faulty_ctx)}
        assert signals["20:20"].confidence < 0.4  # « Marge nette »

    def test_no_high_confidence_orphan_on_healthy(self, healthy_ctx):
        """Dans le classeur sain, tous les canaux significatifs sont branches."""
        signals = signals_of(R215Orphans(), healthy_ctx, sheet=None)
        offenders = [(s.sheet, s.refs, s.label, s.confidence) for s in signals if s.confidence >= 0.8]
        assert not offenders, offenders


class TestNoFalsePositivesOverall:
    """Aucune regle de plage ne doit parler sur un classeur sain."""

    @pytest.mark.parametrize(
        "rule",
        [
            R201CachedErrors(), R203Horizontal(), R204CopyDrift(), R205Anchoring(),
            R206TruncatedSum(), R207SumRangeWidth(), R208HeterogeneousSum(),
        ],
        ids=lambda r: r.id,
    )
    def test_silent_on_healthy_workbook(self, rule, healthy_ctx):
        signals = rule.run(healthy_ctx)
        assert signals == [], [(s.sheet, s.refs, s.note) for s in signals]
