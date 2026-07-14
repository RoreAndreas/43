import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
from urllib.parse import urljoin

BASE_URL = "https://www.richbourse.com"
INDEX_URL = f"{BASE_URL}/common/actualite/index"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="126", "Not.A/Brand";v="24", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def scrape_richbourse_actualites():
    """Récupère les publications officielles BRVM listées sur RichBourse, groupées par semaine.

    Le WAF du site bloque les requêtes sans en-têtes de navigateur complets (Sec-Fetch-*,
    Sec-Ch-Ua) : une requête initiale sur la page d'accueil établit une session valide
    avant l'appel à la page des actualités.
    """
    session = requests.Session()
    session.get(f"{BASE_URL}/", headers=HEADERS, timeout=30)

    response = session.get(
        INDEX_URL,
        headers={**HEADERS, "Referer": f"{BASE_URL}/", "Sec-Fetch-Site": "same-origin"},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    weeks = []
    for week_div in soup.select("div[id^='parcours_actualite_semaine_']"):
        label_tag = week_div.find("b")
        week_label = label_tag.get_text(strip=True) if label_tag else None

        publications = []
        for row in week_div.select("div.ligne_impaire, div.ligne_paire"):
            cols = row.find_all("div", recursive=False)
            if len(cols) < 2:
                continue
            link = cols[1].find("a")
            if not link or not link.get("href"):
                continue
            publications.append({
                "date": cols[0].get_text(strip=True),
                "titre": link.get_text(strip=True),
                "url": urljoin(BASE_URL, link["href"]),
            })

        if publications:
            weeks.append({"semaine": week_label, "publications": publications})

    return weeks


def update_data():
    try:
        weeks = scrape_richbourse_actualites()
    except Exception as e:
        print(f"[{datetime.now()}] Échec de la mise à jour RichBourse : {e}")
        return

    if not weeks:
        print(f"[{datetime.now()}] Aucune publication trouvée sur RichBourse.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {
        "last_update": timestamp,
        "count": sum(len(w["publications"]) for w in weeks),
        "weeks": weeks,
    }

    script_dir = os.path.dirname(os.path.abspath(__file__))
    latest_file = os.path.join(script_dir, "richbourse_actualites.json")
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    print(f"[{timestamp}] Mise à jour réussie : {result['count']} publications récupérées ({len(weeks)} semaines).")


if __name__ == "__main__":
    update_data()
