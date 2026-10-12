"""Statut dans le groupe, lu dans la description S&P intégrale.

Aucun export ne donne la filiation en colonne. S&P l'écrit presque toujours en
fin de description — « … operates as a subsidiary of Absa Group Limited. » —,
que la page n'embarque pas : c'est donc le build qui la lit. Ces tests
tournent sans navigateur, sur des descriptions écrites à la main d'après les
formulations relevées dans les exports d'octobre 2026.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "moteur"))

from comparables import statut_groupe  # noqa: E402


def test_une_filiale_porte_le_nom_de_sa_mere():
    d = ("Absa Bank Botswana Limited provides banking products. The company was founded in 1950 and is "
         "headquartered in Gaborone, Botswana. Absa Bank Botswana Limited operates as a subsidiary of Absa Group Limited.")
    assert statut_groupe("Absa Bank Botswana Limited", d) == ("filiale", "Absa Group Limited")


def test_le_nom_de_la_mere_ne_s_arrete_pas_a_sa_forme_juridique():
    d = "X makes cement. X operates as a wholly-owned subsidiary of Société Générale S.A."
    assert statut_groupe("X", d) == ("filiale", "Société Générale S.A")
    d = "Y sells shoes. Y is a subsidiary of Alphabet Inc. As of 2020, Y changed its name."
    assert statut_groupe("Y", d) == ("filiale", "Alphabet Inc")


def test_filiale_l_emporte_sur_les_filiales_que_la_societe_decrit():
    d = ("Absa Bank Kenya PLC, together with its subsidiaries, provides banking services. "
         "Absa Bank Kenya PLC operates as a subsidiary of Absa Group Limited.")
    assert statut_groupe("Absa Bank Kenya PLC", d)[0] == "filiale"


def test_une_tete_de_groupe_se_reconnait_a_ses_filiales_ses_segments_ou_son_nom():
    assert statut_groupe("Z SA", "Z SA, through its subsidiaries, operates hotels.") == ("groupe", None)
    assert statut_groupe("AT&T Inc.", "AT&T Inc. provides telecom services. It operates through two segments, "
                                      "Communications and Latin America.") == ("groupe", None)
    assert statut_groupe("Sonatel Group SA", "Sonatel provides telecom services in Senegal.") == ("groupe", None)
    assert statut_groupe("Holdings Ltd", "Sells things.") == ("groupe", None)


def test_sans_signal_le_statut_reste_inconnu():
    assert statut_groupe("Shoes Ltd", "Shoes Ltd sells shoes in Kenya.") == (None, None)
    assert statut_groupe("Shoes Ltd", None) == (None, None)
    # « Grouper » ou « regroupe » ne font pas un groupe.
    assert statut_groupe("Groupers Fishing Ltd", "Catches fish.") == (None, None)
