"""Le cadrage et l'onglet Sociétés doivent décrire la même population.

Le défaut d'origine : le cadrage chiffrait l'univers de comparables — deux cent
neuf sociétés sur toute l'Afrique — pendant que l'onglet Sociétés ne lisait que
le volet BRVM, quarante-sept valeurs d'Abidjan. Sur « Consumer Finance », qui
compte une société à Maurice et une au Botswana mais aucune à Abidjan, l'écran
annonçait deux sociétés et l'onglet répondait 404.

Le balayage exhaustif ci-dessous est le garde-fou : toute nouvelle source de
divergence — un pays classé d'un côté et pas de l'autre, un filtre appliqué à
l'un des deux affichages seulement — le fait tomber.
"""

from conftest import choisir, mode_comparables


def test_aucun_ecart_sur_toutes_les_combinaisons(page):
    """Effectif annoncé et sociétés listées, pour chaque zone et chaque secteur."""
    ecarts = page.evaluate("""() => {
      const sortie = [];
      const memoire = { c: params.continent, z: params.zone, i: params.secteur,
                        r: params.referentiel, p: params.country };
      params.referentiel = "comparables";
      params.country = "Benin";
      for (const [continent] of DATA.options.countries_grouped) {
        const zones = (DATA.options.zones_par_continent[continent] || []).map((z) => z[0]);
        for (const zone of [null].concat(zones)) {
          for (const i of DATA.comparables.industries) {
            params.continent = continent;
            params.zone = zone;
            params.secteur = i.nom;
            const annonce = perimetreCourant().n;
            const listees = societesDuPerimetre().length;
            if (annonce !== listees) {
              sortie.push(continent + " / " + zone + " / " + i.nom +
                          " : annoncé " + annonce + ", listé " + listees);
            }
          }
        }
      }
      Object.assign(params, { continent: memoire.c, zone: memoire.z,
                              secteur: memoire.i, referentiel: memoire.r,
                              country: memoire.p });
      return sortie;
    }""")
    assert ecarts == [], "divergences :\n  " + "\n  ".join(ecarts[:20])


def test_le_balayage_couvre_bien_quelque_chose(page):
    """Un balayage qui ne parcourrait rien passerait sans rien vérifier."""
    combinaisons = page.evaluate("""() => {
      const zones = Object.values(DATA.options.zones_par_continent)
        .reduce((a, v) => a + v.length, 0);
      return (DATA.options.countries_grouped.length + zones)
        * DATA.comparables.industries.length;
    }""")
    assert combinaisons > 500, f"seulement {combinaisons} combinaisons parcourues"


def test_le_cas_signale_consumer_finance(page, donnees):
    """Deux sociétés annoncées, deux sociétés affichées — aucune à Abidjan."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Consumer Finance")

    assert "2 sociétés" in page.inner_text("#paramsMain .block-head .chip")

    page.click('.tabs button[data-tab="societes"]')
    assert page.query_selector("#stackSoc .vide404") is None
    cartes = page.query_selector_all("#stackSoc .comp")
    assert len(cartes) == 2

    pays = {donnees["comparables"]["societes"][c.get_attribute("data-comp")]["pays"]
            for c in cartes}
    assert pays == {"Botswana", "Mauritius"}


def test_les_societes_listees_appartiennent_a_la_zone(page, donnees):
    """Restreindre à une zone ne doit laisser que les sociétés de cette zone."""
    mode_comparables(page)
    choisir(page, "continent", "Afrique")
    choisir(page, "secteur", "Banks")
    page.click('#paramsMain .zone[data-zone="Afrique australe"]')

    page.click('.tabs button[data-tab="societes"]')
    cartes = page.query_selector_all("#stackSoc .comp")
    assert cartes

    for carte in cartes:
        societe = donnees["comparables"]["societes"][carte.get_attribute("data-comp")]
        assert societe["zone"] == "Afrique australe", societe["nom"]
        assert societe["industrie"] == "Banks"


def test_toute_societe_embarquee_est_classee(page, donnees):
    """Une société sans zone serait comptée nulle part et introuvable partout."""
    orphelines = [s["nom"] for s in donnees["comparables"]["societes"].values()
                  if not s.get("zone")]
    assert orphelines == [], f"sociétés sans zone : {orphelines[:10]}"
