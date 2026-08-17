"""
Découpage géographique des pays : continent, puis zone.

Damodaran fournit déjà 9 régions dans `ctryprem.xlsx`, mais elles ne descendent
pas au niveau utile ici : ses 30 pays africains tiennent dans un seul bloc, sans
distinguer l'Ouest du Nord. On reprend donc la nomenclature des Nations unies,
en gardant la région Damodaran comme filet pour tout pays qu'elle ajouterait.

Deux écarts assumés par rapport au classement Damodaran, au profit de la
géographie : les Caucase et Asie centrale quittent « Eastern Europe & Russia »,
et Fidji, Papouasie et Salomon quittent « Asia » pour l'Océanie.
"""

import unicodedata

# Zone -> pays. Les libellés doivent reprendre exactement l'orthographe du
# fichier Damodaran, sinon le rapprochement échoue silencieusement.
ZONES = {
    # ---- Afrique ----
    # Couverture complète du continent, et non des seuls pays notés par
    # Damodaran : la carte doit rester entière, et l'univers de comparables
    # compte des sociétés au Zimbabwe, au Malawi ou en Algérie.
    "Afrique du Nord": ["Algeria", "Egypt", "Libya", "Morocco", "Sudan", "Tunisia"],
    "Afrique de l'Ouest": [
        "Benin", "Burkina Faso", "Cape Verde", "Côte d'Ivoire", "Gambia", "Ghana",
        "Guinea", "Guinea-Bissau", "Liberia", "Mali", "Mauritania", "Niger",
        "Nigeria", "Senegal", "Sierra Leone", "Togo",
    ],
    "Afrique centrale": [
        "Angola", "Cameroon", "Central African Republic", "Chad",
        "Congo (Democratic Republic of)", "Congo (Republic of)",
        "Equatorial Guinea", "Gabon", "Sao Tome and Principe",
    ],
    "Afrique de l'Est": [
        "Burundi", "Comoros", "Djibouti", "Eritrea", "Ethiopia", "Kenya",
        "Madagascar", "Mauritius", "Rwanda", "Seychelles", "Somalia",
        "South Sudan", "Tanzania", "Uganda",
    ],
    # Écart assumé par rapport au M49 des Nations unies, qui range Zambie,
    # Zimbabwe, Malawi et Mozambique en Afrique de l'Est. Ces quatre marchés
    # relèvent de la SADC et se lisent, en pratique financière, avec l'Afrique
    # australe — c'est aussi ce que la carte donne à voir, le bloc étant
    # contigu. L'Angola, membre de la SADC lui aussi, reste en Afrique centrale :
    # son économie pétrolière et sa position le rattachent au golfe de Guinée.
    "Afrique australe": [
        "Botswana", "Lesotho", "Malawi", "Mozambique", "Namibia", "South Africa",
        "Swaziland", "Zambia", "Zimbabwe",
    ],

    # ---- Asie ----
    "Asie de l'Est": ["China", "Hong Kong", "Japan", "Korea", "Macao", "Mongolia", "Taiwan"],
    "Asie du Sud": ["Bangladesh", "India", "Maldives", "Nepal", "Pakistan", "Sri Lanka"],
    "Asie du Sud-Est": [
        "Cambodia", "Indonesia", "Laos", "Malaysia", "Philippines",
        "Singapore", "Thailand", "Vietnam",
    ],
    "Asie centrale et Caucase": [
        "Armenia", "Azerbaijan", "Georgia", "Kazakhstan", "Kyrgyzstan",
        "Tajikistan", "Uzbekistan",
    ],
    "Moyen-Orient": [
        "Abu Dhabi", "Bahrain", "Iraq", "Israel", "Jordan", "Kuwait", "Lebanon",
        "Oman", "Qatar", "Ras Al Khaimah (Emirate of)", "Saudi Arabia",
        "Sharjah", "United Arab Emirates",
    ],

    # ---- Europe ----
    "Europe de l'Ouest": [
        "Andorra (Principality of)", "Austria", "Belgium", "France", "Germany",
        "Guernsey (States of)", "Ireland", "Isle of Man", "Jersey (States of)",
        "Liechtenstein", "Luxembourg", "Netherlands", "Switzerland", "United Kingdom",
    ],
    "Europe du Nord": [
        "Denmark", "Estonia", "Finland", "Iceland", "Latvia", "Lithuania",
        "Norway", "Sweden",
    ],
    "Europe du Sud": [
        "Albania", "Bosnia and Herzegovina", "Croatia", "Cyprus", "Greece",
        "Italy", "Macedonia", "Malta", "Montenegro", "Portugal", "Serbia",
        "Slovenia", "Spain", "Turkey",
    ],
    "Europe de l'Est": [
        "Belarus", "Bulgaria", "Czech Republic", "Hungary", "Moldova",
        "Poland", "Romania", "Slovakia", "Ukraine",
    ],

    # ---- Amériques ----
    "Amérique du Nord": ["Canada", "United States"],
    "Amérique latine": [
        "Argentina", "Belize", "Bolivia", "Brazil", "Chile", "Colombia",
        "Costa Rica", "Ecuador", "El Salvador", "Guatemala", "Honduras",
        "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru", "Suriname",
        "Uruguay", "Venezuela",
    ],
    "Caraïbes": [
        "Aruba", "Bahamas", "Barbados", "Bermuda", "Cayman Islands", "Cuba",
        "Curacao", "Dominican Republic", "Jamaica", "Montserrat", "St. Maarten",
        "St. Vincent & the Grenadines", "Trinidad and Tobago",
        "Turks and Caicos Islands",
    ],

    # ---- Océanie ----
    "Océanie": [
        "Australia", "Cook Islands", "Fiji", "New Zealand",
        "Papua New Guinea", "Solomon Islands",
    ],
}

CONTINENT_DE_LA_ZONE = {
    "Afrique du Nord": "Afrique",
    "Afrique de l'Ouest": "Afrique",
    "Afrique centrale": "Afrique",
    "Afrique de l'Est": "Afrique",
    "Afrique australe": "Afrique",
    "Asie de l'Est": "Asie",
    "Asie du Sud": "Asie",
    "Asie du Sud-Est": "Asie",
    "Asie centrale et Caucase": "Asie",
    "Moyen-Orient": "Asie",
    "Europe de l'Ouest": "Europe",
    "Europe du Nord": "Europe",
    "Europe du Sud": "Europe",
    "Europe de l'Est": "Europe",
    "Amérique du Nord": "Amériques",
    "Amérique latine": "Amériques",
    "Caraïbes": "Amériques",
    "Océanie": "Océanie",
}

# Filet de sécurité : si Damodaran ajoute un pays absent des listes ci-dessus,
# on le rattache à partir de sa propre région plutôt que de le perdre.
REPLI_PAR_REGION = {
    "Africa": ("Afrique", "Afrique — non ventilée"),
    "Asia": ("Asie", "Asie — non ventilée"),
    "Middle East": ("Asie", "Moyen-Orient"),
    "Western Europe": ("Europe", "Europe de l'Ouest"),
    "Eastern Europe & Russia": ("Europe", "Europe de l'Est"),
    "North America": ("Amériques", "Amérique du Nord"),
    "Central and South America": ("Amériques", "Amérique latine"),
    "Caribbean": ("Amériques", "Caraïbes"),
    "Australia & New Zealand": ("Océanie", "Océanie"),
}

# Ordre d'affichage. Fixé explicitement plutôt que trié : l'ordre alphabétique
# placerait l'Océanie avant l'Europe selon la locale, et le classement doit être
# stable d'une machine à l'autre.
ORDRE_CONTINENTS = ["Afrique", "Amériques", "Asie", "Europe", "Océanie"]

_PAR_PAYS = {pays: zone for zone, pays_list in ZONES.items() for pays in pays_list}


def _sans_accent(texte: str) -> str:
    """Minuscules sans accent ni ponctuation, pour rapprocher deux orthographes."""
    decompose = unicodedata.normalize("NFKD", str(texte))
    return "".join(c for c in decompose.lower() if c.isalnum())


# Le découpage suit l'orthographe anglaise de Damodaran, mais les sociétés sont
# libellées en français : « Bénin » et « Sénégal » ne tombaient sur rien. On
# indexe donc aussi une forme sans accent, sans quoi le rattachement échoue en
# silence — précisément le risque annoncé en tête de ce module.
_PAR_PAYS_NORMALISE = {_sans_accent(pays): zone for pays, zone in _PAR_PAYS.items()}

# Libellés que d'autres sources écrivent autrement. S&P abrège la République
# démocratique du Congo, Natural Earth a suivi les renommages officiels.
_ALIAS = {
    "demrepcongo": "Congo (Democratic Republic of)",
    "democraticrepublicofthecongo": "Congo (Democratic Republic of)",
    "republicofthecongo": "Congo (Republic of)",
    "congo": "Congo (Republic of)",
    "southkorea": "Korea",
    "northmacedonia": "Macedonia",
    "eswatini": "Swaziland",
    "capeverde": "Cape Verde",
    "caboverde": "Cape Verde",
    "ivorycoast": "Côte d'Ivoire",
    "thegambia": "Gambia",
    "saotomeandprincipe": "Sao Tome and Principe",
}


def classer(pays: str, region_damodaran: str = None):
    """(continent, zone) d'un pays. Retourne (None, None) si inclassable."""
    libelle = str(pays).strip()
    cle = _sans_accent(libelle)
    zone = _PAR_PAYS.get(libelle) or _PAR_PAYS_NORMALISE.get(cle)
    if zone is None and cle in _ALIAS:
        zone = _PAR_PAYS.get(_ALIAS[cle])
    if zone:
        return CONTINENT_DE_LA_ZONE[zone], zone
    if region_damodaran:
        replis = REPLI_PAR_REGION.get(str(region_damodaran).strip())
        if replis:
            return replis
    return None, None


def verifier_couverture(pays_damodaran):
    """
    Confronte le découpage à la liste de pays réellement publiée par Damodaran.

    Rend (manquants, hors_damodaran) : les pays Damodaran qu'aucune zone ne
    réclame, et les pays du découpage absents du jeu Damodaran.

    Seul le premier terme est une anomalie. Le second est attendu : le découpage
    couvre les continents en entier, alors que Damodaran ne note que les pays
    dotés d'une prime de risque. Un pays du Sahel sans notation doit tout de même
    être colorié sur la carte et pouvoir accueillir des comparables.

    Ce contrôle existe parce que le rapprochement se fait sur le libellé exact.
    Damodaran republie chaque janvier, et une simple retouche d'orthographe —
    « Congo (Republic of) » devenant « Republic of Congo » — sortirait le pays du
    découpage sans provoquer la moindre erreur. C'est le mode de défaillance
    qu'annonce l'en-tête de ce module : silencieux.
    """
    references = {str(p).strip() for p in pays_damodaran}
    couverts = set(_PAR_PAYS)
    return sorted(references - couverts), sorted(couverts - references)


def grouper_par_continent(pays_noms):
    """
    Regroupe des pays par continent, prêt pour un affichage en `<optgroup>`.

    Rend [[continent, [pays triés]], ...] dans l'ordre d'ORDRE_CONTINENTS. Les
    pays inclassables sont rassemblés sous « Autres » plutôt que d'être écartés :
    un pays absent du menu serait un pays qu'on ne peut plus sélectionner.
    """
    paniers = {}
    for nom in pays_noms:
        continent, _zone = classer(nom)
        paniers.setdefault(continent or "Autres", []).append(nom)

    groupes = []
    for continent in ORDRE_CONTINENTS:
        if continent in paniers:
            groupes.append([continent, sorted(paniers.pop(continent))])
    for reste in sorted(paniers):  # « Autres », et tout continent non prévu
        groupes.append([reste, sorted(paniers[reste])])
    return groupes


def enrichir_dataset(dataset: dict) -> list:
    """
    Ajoute continent et zone au jeu de données, et le menu groupé.

    Modifie `dataset` sur place : chaque entrée de `pays` reçoit `continent` et
    `zone`, et `options` reçoit `countries_grouped`. La liste plate
    `options.countries` est conservée telle quelle — plusieurs endroits de la
    page s'en servent pour résoudre un paramètre d'URL.

    Rend la liste des pays inclassables, pour que l'appelant décide quoi en faire.
    """
    pays = dataset.get("pays") or {}
    inclassables = []
    for nom, entree in pays.items():
        continent, zone = classer(nom)
        if continent is None:
            inclassables.append(nom)
            continue
        entree["continent"] = continent
        entree["zone"] = zone

    options = dataset.setdefault("options", {})
    options["countries_grouped"] = grouper_par_continent(sorted(pays))

    # Zones du continent, pour le panneau géographique. Une zone n'apparaît que
    # si elle compte au moins un pays du jeu de données.
    par_continent = {}
    for nom in pays:
        continent, zone = classer(nom)
        if continent:
            par_continent.setdefault(continent, {}).setdefault(zone, []).append(nom)
    options["zones_par_continent"] = {
        continent: [[zone, sorted(membres)] for zone, membres in sorted(paniers.items())]
        for continent, paniers in par_continent.items()
    }
    return inclassables


def indexer_societes(dataset: dict) -> dict:
    """
    Compte les sociétés référencées par zone, et par industrie au sein d'une zone.

    Écrit `dataset["zones_societes"]`. Les effectifs sortent des seules sociétés
    réellement présentes dans le jeu de données : aujourd'hui les 47 valeurs de
    la place d'Abidjan, qui couvrent sept pays et donc **une seule zone sur les
    dix-huit**. Les autres zones sortent à zéro, et la page doit le dire au lieu
    d'afficher un tiret qu'on lirait comme une donnée manquante.

    Rend les pays de sociétés qu'aucune zone ne réclame, pour que le build le
    signale plutôt que de les perdre.
    """
    brvm = dataset.get("brvm") or {}
    societes = brvm.get("societes") or {}
    industries = brvm.get("industries") or []

    industrie_du_ticker = {}
    for entree in industries:
        for ticker in entree.get("tickers", []):
            industrie_du_ticker[ticker] = entree.get("nom")

    index, orphelins = {}, []
    for ticker, societe in societes.items():
        pays = societe.get("pays")
        if not pays:
            continue
        _continent, zone = classer(pays)
        if zone is None:
            orphelins.append(pays)
            continue
        # La place de cotation, pas le pays du siège : les 47 valeurs du jeu de
        # données sont toutes cotées à Abidjan. Le jour où une autre place entre
        # dans le périmètre, ce libellé devra venir de la donnée et non d'ici.
        place = societe.get("place") or "BRVM"
        seau = index.setdefault(zone, {"total": 0, "places": {}, "industries": {}})
        seau["total"] += 1
        seau["places"][place] = seau["places"].get(place, 0) + 1
        nom_industrie = industrie_du_ticker.get(ticker)
        if nom_industrie:
            detail = seau["industries"].setdefault(nom_industrie, {"n": 0, "places": {}})
            detail["n"] += 1
            detail["places"][place] = detail["places"].get(place, 0) + 1

    dataset["zones_societes"] = index
    dataset["societes_hors_zone"] = sorted(set(orphelins))
    return dataset["societes_hors_zone"]


def index_par_pays(pays_regions) -> dict:
    """
    {pays: {"continent": ..., "zone": ...}} pour la liste fournie.

    `pays_regions` : itérable de couples (pays, région Damodaran).
    """
    index = {}
    for pays, region in pays_regions:
        continent, zone = classer(pays, region)
        if continent:
            index[pays] = {"continent": continent, "zone": zone}
    return index
