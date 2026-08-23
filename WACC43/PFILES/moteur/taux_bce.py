"""
Courbe des taux souverains de la zone euro, publiée par la BCE.

Le portail de données de la BCE expose la courbe zéro-coupon quotidienne sans
clé ni inscription. Deux variantes coexistent, et le choix n'est pas neutre :

    G_N_A   émetteurs notés AAA seulement   3,28 % à 10 ans
    G_N_C   tous émetteurs souverains       3,71 % à 10 ans

On retient la courbe AAA. Les 43 points de base d'écart sont du risque pays
moyen de la zone, agrégé sur des États dont le risque n'a rien de commun. Les
mélanger reviendrait à prêter le risque italien à l'Allemagne et le risque
allemand à la Grèce. Le socle est donc pris sans risque pays, et la prime du
pays retenu s'y ajoute explicitement — même construction que sous Damodaran.
"""

import re

import requests

SERVICE = "https://data-api.ecb.europa.eu/service/data/YC"

# Clé de série : fréquence.zone.devise.fournisseur.instrument.méthode.type
# `U2` = zone euro à composition variable, `SV_C_YM` = modèle de Svensson.
PREFIXE = "B.U2.EUR.4F.G_N_A.SV_C_YM"

# Maturités retenues, dans les libellés des courbes UMOA-Titres : la page les
# présente dans un même menu, elles doivent se lire de la même façon.
MATURITES = [
    ("3M", "3 mois", 0.25),
    ("6M", "6 mois", 0.5),
    ("1Y", "1 an", 1.0),
    ("2Y", "2 ans", 2.0),
    ("3Y", "3 ans", 3.0),
    ("5Y", "5 ans", 5.0),
    ("7Y", "7 ans", 7.0),
    ("10Y", "10 ans", 10.0),
    ("15Y", "15 ans", 15.0),
    ("20Y", "20 ans", 20.0),
    ("30Y", "30 ans", 30.0),
]

_CODE = re.compile(r"SR_(\w+)$")


def charger_courbe() -> dict:
    """
    Dernier point coté de chaque maturité.

    Retourne {"date": "AAAA-MM-JJ", "source": url, "points": [[libellé, années, taux], ...]}
    Les taux sont en décimal, comme ceux d'UMOA-Titres.

    Toutes les maturités sont demandées en une seule requête : onze appels
    séparés ont expiré une fois sur trois depuis une connexion domestique.
    """
    cle = PREFIXE + "." + "+".join("SR_" + code for code, _, _ in MATURITES)
    url = SERVICE + "/" + cle
    reponse = requests.get(
        url, params={"lastNObservations": 1, "format": "csvdata"}, timeout=120
    )
    reponse.raise_for_status()

    lignes = reponse.text.splitlines()
    if len(lignes) < 2:
        raise RuntimeError("Réponse BCE vide : aucune observation.")
    entetes = lignes[0].split(",")
    i_cle, i_date, i_valeur = (entetes.index(c) for c in ("KEY", "TIME_PERIOD", "OBS_VALUE"))

    annees = {code: (libelle, duree) for code, libelle, duree in MATURITES}
    points, dates = [], []
    for ligne in lignes[1:]:
        cases = ligne.split(",")
        if len(cases) <= max(i_cle, i_date, i_valeur):
            continue
        trouve = _CODE.search(cases[i_cle])
        if not trouve or trouve.group(1) not in annees:
            continue
        try:
            taux = float(cases[i_valeur]) / 100.0
        except ValueError:
            continue
        if not (-0.05 < taux < 0.5):
            continue
        libelle, duree = annees[trouve.group(1)]
        points.append([libelle, duree, taux])
        dates.append(cases[i_date])

    if len(points) < 5:
        raise RuntimeError(f"Courbe BCE incomplète : {len(points)} maturité(s) lisible(s).")

    return {
        "date": max(dates),
        "source": url,
        "points": sorted(points, key=lambda p: p[1]),
    }


if __name__ == "__main__":
    courbe = charger_courbe()
    print(f"Courbe BCE au {courbe['date']}")
    for libelle, _annees, taux in courbe["points"]:
        print(f"  {libelle:>8} : {taux * 100:6.3f} %")
