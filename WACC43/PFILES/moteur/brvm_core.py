"""
Volet BRVM : condensation des données du projet BRVM-Analysis pour la page.

Le scraper SIKAPRO tourne toutes les 10 minutes dans son propre dépôt ; la page
CMPC, elle, se reconstruit trimestriellement. On prend donc ici un *instantané*
des 47 sociétés cotées au moment du build, sans jamais brancher la page sur la
cadence du scraper.
"""

import json
from pathlib import Path

BRVM_DIR = Path(__file__).parents[3] / "BRVM-Analysis"
SIKAPRO_DATA = BRVM_DIR / "SIKAPRO" / "sikapro_data.json"
CLASSIFICATION = BRVM_DIR / "classification_industries.json"

# Suffixe du ticker Sikafinance -> pays de cotation. Le drapeau est en emoji :
# aucune image à charger, donc la page reste autonome et fonctionne hors ligne.
PAYS = {
    "ci": ("Côte d'Ivoire", "🇨🇮"),
    "sn": ("Sénégal", "🇸🇳"),
    "bj": ("Bénin", "🇧🇯"),
    "bf": ("Burkina Faso", "🇧🇫"),
    "ml": ("Mali", "🇲🇱"),
    "ne": ("Niger", "🇳🇪"),
    "tg": ("Togo", "🇹🇬"),
}

POSTES = [
    ("ca", "chiffre_affaires"),
    ("ebitda", "ebitda"),
    ("charges", "charges_exploitation"),
    ("rn", "resultat_net"),
    ("capitaux_propres", "capitaux_propres"),
    ("dette_nette", "dette_nette"),
]


def disponible() -> bool:
    """Les deux fichiers sources sont-ils présents ? Le volet BRVM est optionnel."""
    return SIKAPRO_DATA.exists() and CLASSIFICATION.exists()


def _pays_du_ticker(url: str):
    suffixe = url.rstrip("/").rsplit(".", 1)[-1].lower()
    return PAYS.get(suffixe, ("—", "🏳"))


def build_brvm(progress=None) -> dict:
    """
    Instantané des sociétés cotées, regroupées par industrie.

    Retourne None si les sources ne sont pas disponibles : la page se construit
    alors sans le référentiel BRVM, sans échouer.
    """
    say = progress or (lambda *_: None)
    if not disponible():
        say("Sources BRVM absentes — référentiel BRVM non embarqué.")
        return None

    say("Sociétés cotées BRVM...")
    brut = json.loads(SIKAPRO_DATA.read_text(encoding="utf-8"))
    classification = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))

    societes = {}
    for row in brut["data"]:
        ticker = row["ticker"]
        pays, drapeau = _pays_du_ticker(row.get("url", ""))
        fin = row.get("finances") or {}
        entree = {
            "nom": row.get("nom_societe"),
            "pays": pays,
            "drapeau": drapeau,
            "presentation": row.get("presentation"),
            "capitalisation": row.get("capitalisation_mxof"),
            "beta": row.get("beta_1an"),
            "annees": fin.get("annees", []),
        }
        for cle, poste in POSTES:
            entree[cle] = fin.get(poste, {})
        societes[ticker] = entree

    industries = []
    for ind in classification["industries"]:
        tickers = [t for t in ind["tickers"] if t in societes]
        if not tickers:
            continue
        industries.append({"nom": ind["nom"], "tickers": tickers})

    manquants = sorted(set(societes) - {t for i in industries for t in i["tickers"]})
    if manquants:
        say(f"Sociétés non classées, exclues du référentiel : {', '.join(manquants)}")

    return {
        "maj": brut.get("last_update"),
        "revision_classification": classification.get("revision"),
        "industries": industries,
        "societes": societes,
        "courbes": _courbes(say),
    }


def _courbes(say):
    """
    Courbes souveraines UEMOA. Une indisponibilité du site UMOA-Titres ne doit
    pas faire échouer la construction : le référentiel BRVM reste consultable,
    seul le taux sans risque manque.
    """
    try:
        import taux_uemoa

        say("Courbes de taux UEMOA...")
        courbes = taux_uemoa.charger_courbes()
        say(f"Courbes au {courbes['date']} — {len(courbes['pays'])} États.")
        return courbes
    except Exception as exc:
        say(f"Courbes UEMOA indisponibles ({type(exc).__name__}) — taux sans risque absent.")
        return None
