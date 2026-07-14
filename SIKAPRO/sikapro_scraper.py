import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
URLS_FILE   = os.path.join(SCRIPT_DIR, "urls.json")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "sikapro_data.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def load_config():
    """Identifiants SikaFinance PRO : config.json en local (non versionné),
    sinon variables d'environnement SIKAPRO_LOGIN / SIKAPRO_PASSWORD
    (transmises via les Secrets Streamlit Cloud par app.py)."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    config = {
        "login": os.environ.get("SIKAPRO_LOGIN", ""),
        "password": os.environ.get("SIKAPRO_PASSWORD", ""),
        "base_url": os.environ.get("SIKAPRO_BASE_URL", "https://pro.sikafinance.com"),
    }
    if not config["login"] or not config["password"]:
        raise RuntimeError(
            "Identifiants SikaFinance PRO manquants : créez SIKAPRO/config.json en local, "
            "ou définissez SIKAPRO_LOGIN / SIKAPRO_PASSWORD dans les Secrets Streamlit Cloud."
        )
    return config


def load_urls():
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def create_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def login(session, config):
    """
    Se connecte à pro.sikafinance.com.
    1. GET /login pour récupérer le token CSRF
    2. POST /login avec les credentials
    Retourne True si la connexion est réussie.
    """
    base_url = config["base_url"]
    login_url = f"{base_url}/login"

    # Étape 1 — récupérer la page de login et le token CSRF
    resp = session.get(login_url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Chercher le token CSRF (ASP.NET anti-forgery ou Laravel)
    csrf_token = None
    for token_name in ["__RequestVerificationToken", "_token"]:
        token_input = soup.find("input", {"name": token_name})
        if token_input:
            csrf_token = (token_name, token_input.get("value"))
            break
    if csrf_token is None:
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta:
            csrf_token = ("_token", meta.get("content"))

    # Étape 2 — POST avec les credentials
    # Noms des champs réels du formulaire pro.sikafinance.com (ASP.NET)
    payload = {
        "UserName": config["login"],
        "Password": config["password"],
    }
    if csrf_token:
        payload[csrf_token[0]] = csrf_token[1]

    post_resp = session.post(login_url, data=payload, timeout=30, allow_redirects=True)
    post_resp.raise_for_status()

    # Vérifier que la connexion a réussi :
    # après login réussi, on ne devrait plus voir le lien "Connexion" sur la page
    page_text = post_resp.text
    if "Connexion" in page_text and "/login" in page_text and config["login"] not in page_text:
        print("[LOGIN] Échec : toujours sur la page de connexion.")
        return False

    print("[LOGIN] Connexion réussie.")
    return True


def _parse_price(text):
    """Nettoie une chaîne de prix et retourne un float ou None."""
    if not text:
        return None
    # Supprimer les espaces insécables, espaces, "XOF", "FCFA", etc.
    cleaned = re.sub(r"[^\d,.\-]", "", text.replace("\xa0", "").replace(" ", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def scrape_ticker(session, url):
    """
    Scrape une page de titre sur pro.sikafinance.com.
    URL attendue : https://pro.sikafinance.com/fiche/TICKER.pays
    Extrait :
      - Le ticker (depuis "Ticker : PRSC" dans la page, fallback = segment URL sans extension)
      - Le nom de la société (texte de la page)
      - Le "Plus bas 1 mois" du tableau HISTORIQUE DU TITRE (Table index 1)
    Retourne un dict ou None en cas d'erreur.
    """
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERREUR] Impossible de charger {url} : {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    full_text = soup.get_text(" ", strip=True)

    # --- Ticker ---
    # Format page : "ISIN : CI0000000055 - Ticker : PRSC"
    # Fallback : segment URL sans extension pays (PRSC.ci -> PRSC)
    ticker_raw = url.rstrip("/").split("/")[-1]          # ex: PRSC.ci
    ticker = ticker_raw.split(".")[0].upper()            # ex: PRSC
    m = re.search(r"Ticker\s*:\s*([A-Z0-9]+)", full_text, re.IGNORECASE)
    if m:
        ticker = m.group(1).upper()

    # --- Nom de la société ---
    # Il apparaît en majuscules avant "USD EUR XOF" et le bloc de navigation
    # On cherche dans les éléments h1 ou dans le texte complet
    nom_societe = ticker  # fallback
    for tag in soup.find_all(["h1", "h2"]):
        t = tag.get_text(strip=True)
        if t and len(t) > 3 and t.upper() == t:  # tout en majuscules = nom société
            nom_societe = t
            break
    if nom_societe == ticker:
        # Chercher avant "USD EUR XOF" dans le texte complet
        m2 = re.search(r"Se déconnecter\s+(.+?)\s+USD EUR XOF", full_text)
        if m2:
            nom_societe = m2.group(1).strip()

    # --- Tableau HISTORIQUE DU TITRE ---
    # Structure (confirmée sur /fiche/PRSC.ci) :
    #   Table index 1 dans la page
    #   Header row : [vide/] Plus Haut | Plus bas | Variation
    #   Lignes      : label | val_haut | val_bas | variation
    #   Ligne cible : "1 mois" -> col_index 2 = Plus bas
    cours_bas_1mois = None
    cours_bas_1mois_str = None
    cours_haut_1mois = None
    cours_haut_1mois_str = None

    tables = soup.find_all("table")

    # Chercher la table contenant "Plus bas" et "1 mois"
    target_table = None
    for table in tables:
        txt = table.get_text(" ", strip=True).lower()
        if "plus bas" in txt and "1 mois" in txt:
            target_table = table
            break

    if target_table is not None:
        rows = target_table.find_all("tr")

        # Trouver dynamiquement les index des colonnes "Plus bas" et "Plus Haut"
        col_index_bas  = 2  # défaut confirmé sur PRSC.ci
        col_index_haut = 1  # défaut confirmé sur PRSC.ci
        for row in rows:
            cells = row.find_all(["th", "td"])
            for i, cell in enumerate(cells):
                cell_txt = cell.get_text(strip=True).lower()
                if "plus bas" in cell_txt:
                    col_index_bas = i
                elif "plus haut" in cell_txt:
                    col_index_haut = i

        # Localiser la ligne "1 mois"
        # get_text(" ", strip=True) pour reconstruire "1 mois" depuis <td>1<span>mois</span></td>
        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            label = cells[0].get_text(" ", strip=True).lower()
            if "1 mois" in label or "1mois" in label:
                if col_index_bas < len(cells):
                    raw = cells[col_index_bas].get_text(" ", strip=True)
                    cours_bas_1mois_str = raw.replace("\xa0", " ").strip()
                    cours_bas_1mois = _parse_price(cours_bas_1mois_str)
                if col_index_haut < len(cells):
                    raw = cells[col_index_haut].get_text(" ", strip=True)
                    cours_haut_1mois_str = raw.replace("\xa0", " ").strip()
                    cours_haut_1mois = _parse_price(cours_haut_1mois_str)
                break
    else:
        print(f"[AVERTISSEMENT] Table historique introuvable pour {url}")

    result = {
        "ticker":               ticker,
        "nom_societe":          nom_societe,
        "cours_bas_1mois":      cours_bas_1mois,
        "cours_bas_1mois_str":  cours_bas_1mois_str,
        "cours_haut_1mois":     cours_haut_1mois,
        "cours_haut_1mois_str": cours_haut_1mois_str,
        "url":                  url,
    }

    status_bas  = cours_bas_1mois_str  if cours_bas_1mois_str  else "N/A"
    status_haut = cours_haut_1mois_str if cours_haut_1mois_str else "N/A"
    print(f"[OK] {ticker:10s} | {nom_societe[:35]:35s} | Plus bas 1 mois : {status_bas} | Plus haut 1 mois : {status_haut}")
    return result


def scrape_all():
    config = load_config()
    urls   = load_urls()

    session = create_session()

    if not login(session, config):
        print("[ABORT] Connexion échouée. Vérifiez les credentials dans config.json.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = []

    for url in urls:
        result = scrape_ticker(session, url)
        if result:
            data.append(result)

    output = {
        "last_update": timestamp,
        "count":       len(data),
        "data":        data,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"\n[{timestamp}] Terminé : {len(data)} titre(s) traité(s). → sikapro_data.json")


if __name__ == "__main__":
    scrape_all()
