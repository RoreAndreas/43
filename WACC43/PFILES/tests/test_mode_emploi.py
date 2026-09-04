"""L'onglet « Mode d'emploi » : un guide illustré, pas un calcul.

Contrairement aux onglets Sociétés et Comparables, ce guide ne dépend d'aucun
référentiel : quelqu'un qui n'a encore rien choisi doit pouvoir comprendre
l'outil avant de s'en servir. Il vit dans le même vocabulaire graphique que
l'ordinateur perplexe des écrans vides — mêmes classes CSS (v4-corps, v4-plein,
v4-trait) — et sa note de clôture réutilise ce personnage à l'identique : c'est
délibéré, la demande était des illustrations « dans le sens du 404 ».
"""

from conftest import mode_comparables

ONGLET = '.tabs button[data-tab="aide"]'
PANNEAU = "#panel-aide"


def test_l_onglet_est_visible_sans_rien_choisir(page):
    """Contrairement à Sociétés et Comparables, le guide ne dépend pas du
    référentiel : il doit s'ouvrir dès l'arrivée sur la page."""
    assert page.get_attribute("#tabAide", "hidden") is None


def test_l_onglet_reste_visible_sous_comparables(page):
    mode_comparables(page)
    assert page.get_attribute("#tabAide", "hidden") is None
    assert page.get_attribute("#tabSocietes", "hidden") is None


def test_cliquer_l_onglet_affiche_le_panneau(page):
    page.click(ONGLET)
    assert page.is_visible(PANNEAU)
    assert page.is_hidden("#panel-params")


def test_les_etapes_se_suivent_sans_trou(page):
    """Le compte n'est pas figé — des cartes ont déjà fusionné — mais la
    numérotation doit rester continue : un saut se verrait tout de suite."""
    page.click(ONGLET)
    etapes = page.query_selector_all(".aide-etape")
    assert len(etapes) >= 5
    numeros = [e.query_selector(".aide-num").inner_text() for e in etapes]
    assert numeros == [str(n) for n in range(1, len(etapes) + 1)]


def test_la_derniere_carte_occupe_la_ligne_si_le_compte_est_impair(page):
    """Sans cela elle resterait seule à gauche, la moitié droite vide."""
    page.click(ONGLET)
    etapes = page.query_selector_all(".aide-etape")
    largeurs = [e.bounding_box()["width"] for e in etapes]
    if len(etapes) % 2:
        assert largeurs[-1] > largeurs[0] * 1.5
    else:
        assert abs(largeurs[-1] - largeurs[0]) < 2


def test_chaque_etape_porte_un_titre_un_texte_et_une_icone(page):
    """Le corps peut être un paragraphe ou une liste : la carte des cadenas
    n'est faite que de puces, et n'a pas à s'inventer une phrase d'introduction
    pour satisfaire un test."""
    page.click(ONGLET)
    for etape in page.query_selector_all(".aide-etape"):
        titre = etape.query_selector("h2").inner_text().strip()
        assert titre
        corps = etape.query_selector("p") or etape.query_selector("ul")
        assert corps is not None and corps.inner_text().strip(), titre
        assert etape.query_selector(".aide-icon svg") is not None, titre


def test_les_fonctionnalites_cles_sont_couvertes(page):
    """Pas une liste arbitraire : chaque mécanique que l'outil propose doit
    être nommée quelque part dans le guide."""
    page.click(ONGLET)
    texte = page.inner_text(PANNEAU)
    attendus = [
        "Damodaran", "Comparables",
        "Continent", "Zone", "Industrie",
        "Pays de valorisation",
        "gearing", "place de cotation",
        "CMPC", "Sociétés", "VE / EBITDA", "Excel",
    ]
    for mot in attendus:
        assert mot in texte, f"« {mot} » absent du mode d'emploi"


def test_chaque_carte_dit_ou_trouver_la_commande(page):
    """Un guide qui décrit un réglage sans dire où l'on clique n'aide personne :
    chaque carte porte son chemin, en toutes lettres."""
    page.click(ONGLET)
    for etape in page.query_selector_all(".aide-etape"):
        ou = etape.query_selector(".aide-ou")
        assert ou is not None, etape.query_selector("h2").inner_text()
        assert ou.inner_text().strip()


def test_les_deux_cadenas_sont_expliques_ensemble(page):
    """Gearing et place de cotation partagent le même cadenas : les séparer en
    deux cartes ferait chercher deux mécaniques là où il n'y en a qu'une."""
    page.click(ONGLET)
    cartes = [e.inner_text() for e in page.query_selector_all(".aide-etape")]
    fusionnee = [c for c in cartes if "gearing" in c and "place de cotation" in c]
    assert len(fusionnee) == 1, "les deux cadenas ne sont pas dans la même carte"
    assert "Observé" in fusionnee[0] and "Cible" in fusionnee[0]
    assert "Toutes" in fusionnee[0] and "Focus" in fusionnee[0]


def test_la_zone_se_choisit_en_cliquant_la_carte(page):
    """Le point que le guide manquait : la zone n'a pas de menu déroulant."""
    page.click(ONGLET)
    texte = page.inner_text(PANNEAU)
    assert "Cliquez directement sur la carte" in texte


def test_la_note_de_cloture_reutilise_le_personnage_du_404(page):
    """La demande était explicite : des illustrations dans le sens de celle
    des écrans vides. La note de clôture va plus loin qu'un simple style
    voisin — c'est le même dessin, tag 404 et boulons tombés compris —
    puisqu'elle explique justement ce que ce personnage signifie ailleurs."""
    page.click(ONGLET)
    note = page.query_selector(".aide-note")
    # <text> SVG, pas un élément HTML : inner_text() n'y a pas prise.
    assert note.query_selector(".v4-etiquette-texte").text_content() == "404"
    assert note.query_selector(".v4-boulon") is not None
    assert "panne" in note.inner_text()


def test_va_et_vient_entre_le_guide_et_les_autres_onglets(page):
    """Le fixture `page` échoue déjà sur toute erreur JS : ce test se contente
    de solliciter le va-et-vient qui la révélerait."""
    mode_comparables(page)
    page.click(ONGLET)
    page.click('.tabs button[data-tab="wacc"]')
    page.click(ONGLET)
    assert page.is_visible(PANNEAU)
