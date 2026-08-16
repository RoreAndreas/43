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

# Zone -> pays. Les libellés doivent reprendre exactement l'orthographe du
# fichier Damodaran, sinon le rapprochement échoue silencieusement.
ZONES = {
    # ---- Afrique ----
    "Afrique du Nord": ["Egypt", "Morocco", "Tunisia"],
    "Afrique de l'Ouest": [
        "Benin", "Burkina Faso", "Cape Verde", "Côte d'Ivoire", "Ghana",
        "Mali", "Niger", "Nigeria", "Senegal", "Togo",
    ],
    "Afrique centrale": [
        "Angola", "Cameroon", "Congo (Democratic Republic of)",
        "Congo (Republic of)", "Gabon",
    ],
    "Afrique de l'Est": [
        "Ethiopia", "Kenya", "Mauritius", "Mozambique", "Rwanda",
        "Tanzania", "Uganda", "Zambia",
    ],
    "Afrique australe": ["Botswana", "Namibia", "South Africa", "Swaziland"],

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

_PAR_PAYS = {pays: zone for zone, pays_list in ZONES.items() for pays in pays_list}


def classer(pays: str, region_damodaran: str = None):
    """(continent, zone) d'un pays. Retourne (None, None) si inclassable."""
    zone = _PAR_PAYS.get(str(pays).strip())
    if zone:
        return CONTINENT_DE_LA_ZONE[zone], zone
    if region_damodaran:
        replis = REPLI_PAR_REGION.get(str(region_damodaran).strip())
        if replis:
            return replis
    return None, None


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
