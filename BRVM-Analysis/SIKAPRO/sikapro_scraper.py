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


def _extract_fundamentals(text):
    """Nombre de titres, capitalisation boursière et beta — lus dans le texte de la page."""
    out = {"nombre_titres": None, "capitalisation_mxof": None, "beta_1an": None}
    m = re.search(r"Nombre de titres\s*:\s*([\d\s ]+)", text)
    if m:
        out["nombre_titres"] = _parse_price(m.group(1))
    m = re.search(r"Capitalisation\s*:\s*([\d\s ]+)\s*MXOF", text)
    if m:
        out["capitalisation_mxof"] = _parse_price(m.group(1))
    m = re.search(r"BETA 1 AN\s+([\d,\.]+)", text)
    if m:
        out["beta_1an"] = _parse_price(m.group(1))
    return out


def _extract_technical(tables):
    """RSI 14 jours + moyennes mobiles 20/50/200 jours (déjà calculées par SikaFinance)."""
    out = {"rsi_14": None, "mm_20": None, "mm_50": None, "mm_200": None}
    for t in tables:
        tt = t.get_text(" ", strip=True)
        if "RSI" in tt and "MM 20" in tt:
            m = re.search(r"RSI 14\s*jours?\s*([\d,\.]+)", tt)
            if m:
                out["rsi_14"] = _parse_price(m.group(1))
            for mm in ("20", "50", "200"):
                m = re.search(rf"MM {mm}\s*jours?\s*([\d\s ,\.]+?)(?:MM|$)", tt)
                if m:
                    out[f"mm_{mm}"] = _parse_price(m.group(1))
            break
    return out


def _extract_performance(tables):
    """Performance depuis le 1er janvier (YTD) et sur 1 an, en %."""
    out = {"perf_ytd_pct": None, "perf_1an_pct": None}
    for t in tables:
        tt = t.get_text(" ", strip=True)
        if "1er janvier" in tt and "%" in tt and "Plus" not in tt:
            m = re.search(r"1er janvier\s*([+\-][\d,\.]+)%", tt)
            if m:
                out["perf_ytd_pct"] = _parse_price(m.group(1))
            m = re.search(r"1 an\s*([+\-][\d,\.]+)%", tt)
            if m:
                out["perf_1an_pct"] = _parse_price(m.group(1))
            break
    return out


def _extract_consensus(tables):
    """Consensus des analystes : note /9, recommandation, objectif de cours, potentiel %."""
    out = {"consensus_note": None, "consensus_reco": None,
           "objectif_cours": None, "potentiel_pct": None}
    for t in tables:
        tt = t.get_text(" ", strip=True)
        if "consensus" in tt.lower() and "Recommandation" in tt:
            m = re.search(r"Moyenne consensus\s*([\d,\.]+)\s*/\s*9", tt)
            if m:
                out["consensus_note"] = _parse_price(m.group(1))
            m = re.search(r"Recommandation\s+([A-Za-z ]+?)\s+Nombre", tt)
            if m:
                out["consensus_reco"] = m.group(1).strip()
            m = re.search(r"Pr[eé]vision\s*([\d\s ]+)\s*XOF", tt)
            if m:
                out["objectif_cours"] = _parse_price(m.group(1))
            m = re.search(r"Potentiel\s*([+\-][\d,\.]+)%", tt)
            if m:
                out["potentiel_pct"] = _parse_price(m.group(1))
            break
    return out


def _extract_finance(session, fiche_url):
    """Onglet FINANCE (/finance/TICKER) : dernier exercice annuel — résultat net,
    capitaux propres, dette nette, chiffre d'affaires (en MFCFA)."""
    out = {"resultat_net_annuel": None, "capitaux_propres": None,
           "dette_nette_annuelle": None, "chiffre_affaires_annuel": None}
    fin_url = fiche_url.replace("/fiche/", "/finance/")
    try:
        resp = session.get(fin_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[AVERTISSEMENT] Onglet finance indisponible pour {fin_url} : {e}")
        return out

    soup = BeautifulSoup(resp.text, "html.parser")

    def last_value(patterns, exclude=("croissance", "marge", "%")):
        """Dans une ligne de tableau dont le libellé matche, renvoie la DERNIÈRE
        valeur numérique (l'exercice le plus récent)."""
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) < 2:
                    continue
                head = cells[0].get_text(" ", strip=True)
                if any(x in head.lower() for x in exclude):
                    continue
                if any(re.search(p, head, re.IGNORECASE) for p in patterns):
                    for cell in reversed(cells[1:]):
                        v = _parse_price(cell.get_text(" ", strip=True))
                        if v is not None:
                            return v
        return None

    out["resultat_net_annuel"]     = last_value([r"^R[ée]sultat net"])
    out["capitaux_propres"]        = last_value([r"Capitaux propres", r"Fonds propres"])
    out["dette_nette_annuelle"]    = last_value([r"Dette nette"])
    out["chiffre_affaires_annuel"] = last_value([r"Chiffre d'affaires"])
    return out


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
    cours_bas_1mois = cours_bas_1mois_str = None
    cours_haut_1mois = cours_haut_1mois_str = None
    haut_52sem = bas_52sem = None

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

        # Lecture cellule par cellule des (plus haut, plus bas) pour la ligne recherchée
        # (robuste aux espaces des milliers, ex. "30 000")
        def _row_high_low(matches):
            for row in rows:
                cells = row.find_all(["th", "td"])
                if not cells:
                    continue
                label = cells[0].get_text(" ", strip=True).lower()
                if matches(label):
                    haut = bas = None
                    if col_index_haut < len(cells):
                        haut = cells[col_index_haut].get_text(" ", strip=True).replace("\xa0", " ").strip()
                    if col_index_bas < len(cells):
                        bas = cells[col_index_bas].get_text(" ", strip=True).replace("\xa0", " ").strip()
                    return haut, bas
            return None, None

        # 1 mois (label reconstruit "1 mois" depuis <td>1<span>mois</span></td>)
        cours_haut_1mois_str, cours_bas_1mois_str = _row_high_low(lambda l: "1 mois" in l or "1mois" in l)
        cours_haut_1mois = _parse_price(cours_haut_1mois_str)
        cours_bas_1mois  = _parse_price(cours_bas_1mois_str)

        # 1 an = plus haut / plus bas sur 52 semaines (attention : "1 an" ≠ "3 ans")
        haut_52sem_str, bas_52sem_str = _row_high_low(lambda l: l.strip() in ("1 an", "1an"))
        haut_52sem = _parse_price(haut_52sem_str)
        bas_52sem  = _parse_price(bas_52sem_str)
    else:
        print(f"[AVERTISSEMENT] Table historique introuvable pour {url}")

    # --- Données fondamentales, techniques, performance et consensus ---
    fundamentals = _extract_fundamentals(full_text)
    technical    = _extract_technical(tables)
    performance  = _extract_performance(tables)
    consensus    = _extract_consensus(tables)
    finance      = _extract_finance(session, url)

    result = {
        "ticker":               ticker,
        "nom_societe":          nom_societe,
        "cours_bas_1mois":      cours_bas_1mois,
        "cours_bas_1mois_str":  cours_bas_1mois_str,
        "cours_haut_1mois":     cours_haut_1mois,
        "cours_haut_1mois_str": cours_haut_1mois_str,
        "haut_52sem":           haut_52sem,
        "bas_52sem":            bas_52sem,
        "url":                  url,
        **fundamentals,
        **technical,
        **performance,
        **consensus,
        **finance,
    }

    status_bas = cours_bas_1mois_str if cours_bas_1mois_str else "N/A"
    reco = consensus.get("consensus_reco") or "N/A"
    print(f"[OK] {ticker:10s} | {nom_societe[:28]:28s} | Bas 1M: {status_bas:>10s} | Reco: {reco}")
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

    print(f"\n[{timestamp}] Termine : {len(data)} titre(s) traite(s). -> sikapro_data.json")


if __name__ == "__main__":
    scrape_all()
