"""
Taux sans risque du référentiel Comparables, pour les 157 pays sélectionnables.

Avant ce module, une seule source alimentait ce référentiel — les courbes
UMOA-Titres — soit sept États sur cent cinquante-sept, et trente-deux sociétés
de comparables sur six mille huit cent quatre-vingt-deux. Choisir n'importe quel
autre pays laissait le CMPC vide.

Trois socles de courbe, une seule formule :

    taux retenu = socle(maturité) + prime de risque pays

Le socle est la courbe souveraine la plus proche disponible, et la prime celle
que Damodaran publie pour les 157 pays. Quand le socle est déjà la courbe de
l'État lui-même — un État de l'UMOA sur sa propre courbe, les États-Unis sur
leur Treasury — aucune prime ne s'ajoute : elle y est déjà.

    socle       source                      couverture
    XOF         UMOA-Titres                 7 États de l'UMOA
    EUR         BCE, courbe AAA zone euro   zone euro et utilisateurs de l'euro
    USD         US Treasury (déjà chargé)   tous les autres

Le socle porte sa devise, et le CMPC qui en découle est libellé dedans. La page
le convertit ensuite en monnaie locale par le différentiel d'inflation, sauf
lorsque la devise du socle est déjà celle du pays — d'où le drapeau `locale`.
"""

# Les États dont UMOA-Titres publie la courbe, sous le libellé Damodaran.
# Le classeur nomme ses feuilles en français ; Damodaran mêle les deux usages.
# La Guinée-Bissau a une courbe mais ne figure pas au référentiel Damodaran :
# elle reste hors de portée tant qu'aucun pays ne peut la désigner.
UMOA = {
    "Bénin": "Benin",
    "Burkina Faso": "Burkina Faso",
    "Côte d'Ivoire": "Côte d'Ivoire",
    "Mali": "Mali",
    "Niger": "Niger",
    "Sénégal": "Senegal",
    "Togo": "Togo",
}

# Zone euro au 1er janvier 2026, Bulgarie comprise, augmentée des États qui
# utilisent l'euro sans en être membres : leur monnaie locale est bien l'euro,
# c'est ce qui compte ici.
ZONE_EURO = [
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Estonia", "Finland",
    "France", "Germany", "Greece", "Ireland", "Italy", "Latvia", "Lithuania",
    "Luxembourg", "Malta", "Netherlands", "Portugal", "Slovakia", "Slovenia",
    "Spain",
    "Andorra (Principality of)", "Monaco", "Montenegro", "San Marino",
    "Kosovo", "Vatican City",
]

# Économies officiellement dollarisées : le dollar y est la monnaie qui a cours
# légal, pas une devise d'ancrage. Les monnaies simplement arrimées au dollar
# — riyal saoudien, dirham, dollar de Hong Kong — n'y figurent pas : un ancrage
# se défait, et le différentiel d'inflation reste alors le bon véhicule.
DOLLARISES = [
    "Ecuador", "El Salvador", "Panama", "Timor-Leste", "Marshall Islands",
    "Micronesia", "Palau", "British Virgin Islands", "Turks and Caicos Islands",
]

# Le pays dont le Treasury est la courbe souveraine : aucune prime ne s'y ajoute.
EMETTEUR_USD = "United States"


def construire(pays_damodaran, progress=None, umoa=None, bce=None) -> dict:
    """
    Affectation d'un socle de courbe à chacun des pays du référentiel.

    `umoa` et `bce` peuvent être passés déjà chargés (les tests le font) ; sinon
    ils sont téléchargés ici. L'indisponibilité d'une source ne fait pas échouer
    la construction : les pays qu'elle desservait retombent sur le socle dollar,
    et la page dit de quel socle vient le taux qu'elle affiche.
    """
    def dire(message):
        if progress:
            progress(message)

    if umoa is None:
        umoa = _charger(dire, "Courbes souveraines UMOA-Titres...", _umoa)
    if bce is None:
        bce = _charger(dire, "Courbe souveraine BCE (zone euro)...", _bce)

    courbes_umoa = {}
    if umoa:
        for feuille, libelle in UMOA.items():
            if feuille in umoa["pays"] and libelle in pays_damodaran:
                courbes_umoa[libelle] = umoa["pays"][feuille]

    euro = [p for p in ZONE_EURO if p in pays_damodaran] if bce else []
    dollarises = [p for p in DOLLARISES if p in pays_damodaran]

    affectation = {}
    for nom in pays_damodaran:
        if nom in courbes_umoa:
            # Sa propre courbe, dans sa propre monnaie : rien à ajouter.
            affectation[nom] = {"socle": "XOF", "prime": False, "locale": True}
        elif nom in euro:
            affectation[nom] = {"socle": "EUR", "prime": True, "locale": True}
        elif nom == EMETTEUR_USD:
            affectation[nom] = {"socle": "USD", "prime": False, "locale": True}
        else:
            affectation[nom] = {
                "socle": "USD", "prime": True, "locale": nom in dollarises,
            }

    dire(f"Taux sans risque : {len(courbes_umoa)} courbes UMOA, "
         f"{len(euro)} pays sur la courbe BCE, "
         f"{len(pays_damodaran) - len(courbes_umoa) - len(euro)} sur le Treasury.")

    return {
        "umoa": None if not courbes_umoa else {
            "date": umoa["date"], "source": umoa["source"], "pays": courbes_umoa,
        },
        "bce": bce,
        "pays": affectation,
    }


def _charger(dire, annonce, charger):
    """Une source injoignable dégrade la page, elle ne fait pas échouer le build."""
    try:
        dire(annonce)
        return charger()
    except Exception as exc:
        dire(f"  indisponible ({type(exc).__name__}) — repli sur le socle dollar.")
        return None


def _umoa():
    import taux_uemoa

    return taux_uemoa.charger_courbes()


def _bce():
    import taux_bce

    return taux_bce.charger_courbe()
