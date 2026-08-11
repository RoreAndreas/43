
import requests
import re
import os
from bs4 import BeautifulSoup
import pdfplumber
from urllib.parse import urljoin

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_URL = "https://www.brvm.org"
BULLETINS_URL = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"
DOWNLOAD_DIR = "./brvm_bulletins"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─── ÉTAPE 1 : Récupérer le lien du dernier bulletin PDF ──────────────────────
def get_latest_bulletin_url():
    session = requests.Session()
    session.verify = False  # Le site BRVM a parfois des pb de certificat SSL
    requests.packages.urllib3.disable_warnings()

    response = session.get(BULLETINS_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Recherche plus ciblée des liens PDF
    pdf_links = []
    # Cible les liens qui contiennent 'bulletin' et se terminent par '.pdf'
    for a_tag in soup.find_all("a", href=re.compile(r"bulletin.*\.pdf", re.IGNORECASE)):
        href = a_tag["href"]
        full_url = urljoin(BASE_URL, href)
        pdf_links.append(full_url)

    if not pdf_links:
        # Fallback si la première méthode échoue
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if ".pdf" in href.lower():
                full_url = urljoin(BASE_URL, href)
                pdf_links.append(full_url)

    if not pdf_links:
        raise ValueError("Aucun lien PDF de bulletin trouvé. La structure du site a peut-être changé.")

    print(f"[✓] {len(pdf_links)} bulletin(s) potentiel(s) trouvé(s). Sélection du plus récent...")
    # Le premier lien correspondant est généralement le plus récent sur ce site.
    return pdf_links[0]


# ─── ÉTAPE 2 : Télécharger le PDF ─────────────────────────────────────────────
def download_pdf(pdf_url):
    session = requests.Session()
    session.verify = False

    print(f"[↓] Téléchargement : {pdf_url}")
    response = session.get(pdf_url, headers=HEADERS, timeout=60, stream=True)
    response.raise_for_status()

    # Vérifier si le contenu est bien un PDF
    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" not in content_type:
        raise ValueError(
            f"Le lien {pdf_url} ne pointe pas vers un fichier PDF valide. "
            f"Content-Type: {content_type}"
        )

    filename = pdf_url.split("/")[-1].split("?")[0]
    if not filename.endswith(".pdf"):
        filename = "bulletin_brvm_latest.pdf"

    filepath = os.path.join(DOWNLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"[✓] PDF sauvegardé : {filepath}")
    return filepath


# ─── ÉTAPE 3 : Extraire les obligations souveraines du PDF ───────────────────
def extract_obligations_souveraines(pdf_path):
    """
    Parcourt le PDF, extrait les 'Obligations Souveraines' et formate le titre
    pour s'arrêter après la date (ex: 2017-2024).
    """
    titres = []
    in_section = False

    # Mots-clés pour détecter le début/fin de la section
    START_KEYWORDS = ["obligations souveraines", "OBLIGATIONS SOUVERAINES"]
    STOP_KEYWORDS = [
        "obligations corporate", "OBLIGATIONS CORPORATE",
        "obligations classiques", "OBLIGATIONS CLASSIQUES",
        "actions", "ACTIONS",
        "sukuk", "SUKUK"
    ]

    # Regex pour trouver le titre jusqu'à la date de type XX-XX
    # Ex: "EMPRUNT OBLIGATAIRE TPCI 5.99% 2017-2024" -> capture tout
    date_pattern = re.compile(r"(.*? \d{4}-\d{4})")

    print(f"\n[🔍] Analyse du PDF : {pdf_path}\n")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split("\n")
                for line in lines:
                    line_clean = line.strip()

                    # Détection du début de la section
                    if not in_section and any(kw.lower() in line_clean.lower() for kw in START_KEYWORDS):
                        in_section = True
                        print(f"  → Section 'Obligations Souveraines' détectée (page {page_num})")
                        continue

                    # Détection de la fin de la section
                    if in_section and any(kw.lower() in line_clean.lower() for kw in STOP_KEYWORDS):
                        in_section = False
                        break  # Sortir de la boucle des lignes pour cette page

                    # Extraction et formatage des titres dans la section
                    if in_section and line_clean:
                        match = date_pattern.search(line_clean)
                        if match:
                            # On a trouvé un titre avec une date, on le garde formaté
                            formatted_title = match.group(1).strip()
                            titres.append(formatted_title)

    except Exception as e:
        print(f"[✗] Erreur lors de l'analyse du PDF : {e}")

    return titres


# ─── ÉTAPE 4 : Afficher les résultats ─────────────────────────────────────────
def display_results(titres):
    print("\n" + "=" * 60)
    print(f"  OBLIGATIONS SOUVERAINES ({len(titres)} titres extraits)")
    print("=" * 60)
    for i, titre in enumerate(titres, start=1):
        print(f"  {i:3}. {titre}")
    print("=" * 60 + "\n")


# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # 1. Trouver le dernier bulletin
        pdf_url = get_latest_bulletin_url()

        # 2. Télécharger le PDF
        pdf_path = download_pdf(pdf_url)

        # 3. Extraire les obligations
        titres_obligations = extract_obligations_souveraines(pdf_path)

        # 4. Afficher
        display_results(titres_obligations)

        # Optionnel : sauvegarder dans un fichier texte
        output_txt = os.path.join(DOWNLOAD_DIR, "obligations_souveraines.txt")
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(titres_obligations))
        print(f"[💾] Liste sauvegardée dans : {output_txt}")

    except Exception as e:
        print(f"[✗] Erreur : {e}")
        raise

