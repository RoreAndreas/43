"""La table des taux d'IS tirée du fichier fiscal de Damodaran.

Ce fichier suit la nomenclature des Nations unies, pas celle du fichier de
primes : « United States of America » n'y était rapproché de rien, et vingt-trois
pays restaient sans taux. Il se termine aussi par une liste qui répète des pays
à des taux antérieurs ; la dernière occurrence l'emportait. Ces tests tournent
sans navigateur, sur une table construite à la main.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "moteur"))

import wacc_core  # noqa: E402
import zones  # noqa: E402


def table(lignes):
    return pd.DataFrame(lignes, columns=["Country", "Tax Rate", "Global Minimum"])


def test_les_libelles_onusiens_sont_ramenes_a_ceux_de_damodaran():
    taux = wacc_core.taux_is_par_pays(table([
        ["United States of America", 0.2563, 0.2563],
        ["United Kingdom of Great Britain and Northern Ireland", 0.25, 0.25],
        ["Republic of Korea", 0.264, 0.264],
        ["Czechia", 0.21, 0.21],
    ]))
    assert taux["United States"] == 0.2563
    assert taux["United Kingdom"] == 0.25
    assert taux["Korea"] == 0.264
    assert taux["Czech Republic"] == 0.21


def test_la_premiere_occurrence_l_emporte():
    """La liste de queue répète le Royaume-Uni à 19 %, son taux d'avant 2023."""
    taux = wacc_core.taux_is_par_pays(table([
        ["United Kingdom of Great Britain and Northern Ireland", 0.25, 0.25],
        ["United Arab Emirates", 0.09, 0.09],
        ["United Arab Emirates", 0.0, 0.0],
        ["United Kingdom of Great Britain and Northern Ireland", 0.19, 0.19],
    ]))
    assert taux["United Kingdom"] == 0.25
    assert taux["United Arab Emirates"] == 0.09


def test_les_emirats_prennent_le_taux_federal():
    taux = wacc_core.taux_is_par_pays(table([["United Arab Emirates", 0.09, 0.09]]))
    for emirat in ("Abu Dhabi", "Sharjah", "Ras Al Khaimah (Emirate of)"):
        assert taux[emirat] == 0.09


def test_les_libelles_s_and_p_sont_ramenes_aussi():
    """Les comparables écrivent « USA » et « Türkiye » : leur taux de
    désendettement se cherche sous le libellé Damodaran."""
    assert zones.nom_damodaran("USA") == "United States"
    assert zones.nom_damodaran("Türkiye") == "Turkey"
    assert zones.nom_damodaran("Bénin") == "Benin"
    assert zones.nom_damodaran("Nulle Part") == "Nulle Part"
