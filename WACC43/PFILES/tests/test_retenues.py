"""Les sociétés qui alimentent la médiane sont marquées dans l'onglet Sociétés.

La médiane sectorielle ne porte pas sur toute la population d'un secteur mais sur
ses vingt plus grosses capitalisations — sans quoi 374 caisses locales
américaines décideraient du bêta des banques. L'onglet doit dire lesquelles.

Le piège : le périmètre de la médiane n'est pas toujours celui de la liste. Sur
une zone trop mince, la médiane est reprise sur le continent, et les vingt
retenues sont alors ailleurs. Sur 511 couples périmètre x secteur peuplés, c'est
le cas une fois sur cinq.

La sélection des vingt est refaite dans le navigateur plutôt que reçue du build —
embarquer les identifiants coûterait trois cent cinquante kilooctets. Le premier
test ci-dessous est ce qui rend ce raccourci sûr : il compare la médiane des
sociétés marquées à celle que le build a publiée.
"""

import statistics

import pytest

from conftest import choisir, mode_comparables

MARQUEE = "#stackSoc .comp.is-retenue"


def ouvrir(page, continent, zone, secteur):
    mode_comparables(page)
    page.evaluate("""a => { params.continent = a[0]; params.zone = a[1];
                           params.secteur = a[2]; apply(); }""",
                  [continent, zone, secteur])
    page.click('.tabs button[data-tab="societes"]')
    page.wait_for_timeout(200)


def marquees(page):
    return [e.get_attribute("data-comp") for e in page.query_selector_all(MARQUEE)]


def toutes(page):
    return [e.get_attribute("data-comp") for e in page.query_selector_all("#stackSoc .comp")]


# ------------------------------------------------------- l'invariant central

@pytest.mark.parametrize("continent, zone, secteur", [
    ("Amériques", "Amérique du Nord", "Banks"),
    ("Europe", "Europe de l'Ouest", "Banks"),
    ("Afrique", "Afrique de l'Ouest", "Banks"),
    ("Amériques", None, "Food Products"),
])
def test_les_marquees_reproduisent_la_mediane_publiee(page, donnees, continent, zone, secteur):
    """Ce que le navigateur sélectionne doit donner le chiffre calculé au build."""
    ouvrir(page, continent, zone, secteur)
    ids = marquees(page)
    assert ids, "aucune société marquée"

    soc = donnees["comparables"]["societes"]
    calculee = statistics.median([soc[i]["beta_3ans"] for i in ids])

    publiee = page.evaluate("nom => statsSecteur(nom).beta_3ans", secteur)
    assert round(calculee, 4) == publiee, (
        f"médiane des marquées {calculee:.4f} contre {publiee} publiée")


def test_le_gearing_aussi(page, donnees):
    ouvrir(page, "Amériques", "Amérique du Nord", "Banks")
    soc = donnees["comparables"]["societes"]
    ratios = [soc[i]["dette"] / soc[i]["capitalisation"] for i in marquees(page)]
    assert round(statistics.median(ratios), 4) == page.evaluate(
        "statsSecteur('Banks').gearing")


# ------------------------------------------------------------ la sélection

def test_jamais_plus_que_l_echantillon(page, donnees):
    plafond = donnees["comparables"]["echantillon"]
    ouvrir(page, "Amériques", "Amérique du Nord", "Banks")
    assert len(toutes(page)) > plafond, "le test perdrait son objet sans débordement"
    assert len(marquees(page)) == plafond


def test_ce_sont_les_plus_grosses_capitalisations(page, donnees):
    ouvrir(page, "Amériques", "Amérique du Nord", "Banks")
    soc = donnees["comparables"]["societes"]
    ids = toutes(page)
    marques = set(marquees(page))
    caps = [(soc[i]["capitalisation"], i in marques) for i in ids]
    plancher = min(c for c, m in caps if m)
    debordantes = [c for c, m in caps if not m and c > plancher]
    assert not debordantes, "une société plus grosse qu'une marquée ne l'est pas"


def test_toutes_marquees_quand_le_secteur_tient_dans_l_echantillon(page, donnees):
    ouvrir(page, "Afrique", "Afrique de l'Ouest", "Banks")
    assert len(toutes(page)) <= donnees["comparables"]["echantillon"]
    assert len(marquees(page)) == len(toutes(page))


# ------------------------------- quand la médiane vient d'un périmètre plus large

def test_seules_les_vraies_retenues_sont_marquees(page, donnees):
    """Afrique australe / Consumer Finance : une société ici, deux au continent."""
    ouvrir(page, "Afrique", "Afrique australe", "Consumer Finance")
    listees, marques = toutes(page), marquees(page)
    assert listees, "le test suppose au moins une société listée"

    soc = donnees["comparables"]["societes"]
    continent = sorted(
        (v for v in soc.values()
         if v["industrie"] == "Consumer Finance" and v["continent"] == "Afrique"),
        key=lambda v: -(v["capitalisation"] or 0))[:donnees["comparables"]["echantillon"]]
    noms = {v["nom"] for v in continent}
    for ident in marques:
        assert soc[ident]["nom"] in noms, "marquée sans être dans l'échantillon retenu"


def test_la_legende_dit_le_perimetre_de_la_mediane(page):
    ouvrir(page, "Afrique", "Afrique australe", "Consumer Finance")
    legende = page.inner_text("#stackSoc .soc-legende")
    assert "périmètre retenu" in legende
    assert "Afrique" in legende


def test_une_zone_vide_dit_ou_est_calculee_la_mediane(page):
    """Sinon « aucune société » et un CMPC chiffré se contrediraient à voix basse."""
    ouvrir(page, "Afrique", "Afrique du Nord", "Banks")
    assert page.query_selector("#stackSoc .vide404") is not None
    texte = page.inner_text("#stackSoc .vide404")
    assert "Le CMPC reste calculé" in texte
    assert "périmètre retenu" in texte


def test_la_legende_porte_la_cle_du_filet(page):
    """Un filet coloré sans légende serait une énigme."""
    ouvrir(page, "Amériques", "Amérique du Nord", "Banks")
    assert page.query_selector("#stackSoc .soc-legende .soc-filet") is not None


def test_le_filet_ne_decale_pas_les_cartes(page):
    """En ombre interne, pas en bordure : sinon les cartes se désalignent."""
    ouvrir(page, "Amériques", "Amérique du Nord", "Banks")
    gauches = page.eval_on_selector_all(
        "#stackSoc .comp", "els => els.slice(0, 30).map(e => e.getBoundingClientRect().left)")
    assert max(gauches) - min(gauches) < 0.5, "les cartes marquées sont décalées"
