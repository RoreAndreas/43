"""Inventaire du portfolio : écrit site/catalogue.json.

Un site hébergé ne peut pas lister lui-même un dossier : ce script le fait
pour lui. Chaque cadre de l'accueil a son dossier dans site/cadres/, et le
contenu vient de deux sources, rien à déclarer ailleurs :

  1. les fichiers déposés dans le dossier du cadre : images (.jpg, .jpeg,
     .png, .webp, .avif, .gif), vidéos (.mp4, .m4v, .webm, .mov) et audios
     (.mp3, .wav, .m4a, .aac, .ogg, .opus, .flac). Le titre est le nom du
     fichier sans son extension ; un numéro en tête (« 01 - Mon film.mp4 »)
     fixe l'ordre et ne s'affiche pas. Sans numéro, les noms sont triés comme
     on les lit : « Diapositive2 » avant « Diapositive10 » ;

  2. les liens de site/cadres/youtube.txt, rangés sous le nom de leur cadre
     entre crochets. Le titre est celui de la vidéo sur YouTube, sauf si la
     ligne en donne un : « Mon titre | https://youtu.be/… ».

Les dossiers peuvent eux aussi commencer par un numéro (« 1 - Présentation ») :
il ne sert qu'à les ranger dans l'ordre de la page, et ne compte pas dans leur
nom.

Les dimensions des images sont notées au passage : le diaporama prend le
format de ses pages.

serve.py le relance à chaque chargement de la page, et Cloudflare à chaque
mise en ligne si sa commande de construction est « python3 inventaire.py » :
il n'y a normalement pas à le lancer soi-même. Sinon : python inventaire.py
"""

import json
import re
import struct
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ICI = Path(__file__).resolve().parent
SITE = ICI / "site"
CADRES = SITE / "cadres"
LIENS = CADRES / "youtube.txt"
CATALOGUE = SITE / "catalogue.json"

IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
VIDEO = {".mp4", ".m4v", ".webm", ".mov"}
AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac"}
LIMITE = 25 * 1024 * 1024  # Cloudflare refuse les fichiers plus lourds
IMAGE_LOURDE = 5 * 1024 * 1024  # une image de 2 000 px de large suffit à l'écran

# « 01 - Titre », « 1. Titre », « 03) Titre », « 12 Titre » : trois chiffres
# au plus, pour ne pas prendre une année (« 2024 Spot radio ») pour un rang.
RANG = re.compile(r"^\s*(\d{1,3})(?:\s*[-–—_.)]\s*|\s+)(?=\S)")
ID_YOUTUBE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def cle(texte):
    """Forme de comparaison d'un nom de cadre : sans accents, casse ni espaces en trop."""
    t = unicodedata.normalize("NFD", texte)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(t.casefold().split())


def naturel(texte):
    """Clé de tri qui lit les nombres comme des nombres : « 2 » avant « 10 »."""
    return [(0, int(m)) if m.isdigit() else (1, cle(m)) for m in re.split(r"(\d+)", texte) if m]


def titre_et_rang(nom, extension=True):
    base = (Path(nom).stem if extension else nom).replace("_", " ")
    m = RANG.match(base)
    if m:
        base = base[m.end():]
    titre = " ".join(base.split()) or (Path(nom).stem if extension else nom)
    return titre, int(m.group(1)) if m else None


def ordre(titre, rang):
    """Les éléments numérotés d'abord, dans l'ordre de leur numéro ; les autres
    ensuite, dans l'ordre naturel de leur nom."""
    return (rang is None, rang or 0, naturel(titre))


# Marqueurs JPEG qui ouvrent une image (SOF) et donnent ses dimensions.
SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def dimensions(f):
    """(largeur, hauteur) d'une image telle qu'elle s'affiche, lues dans son
    en-tête sans la décoder. None pour un format non lu ici (AVIF) : le site
    les mesure alors lui-même au chargement."""
    try:
        with f.open("rb") as h:
            tete = h.read(40)
            if tete.startswith(b"\x89PNG\r\n\x1a\n") and tete[12:16] == b"IHDR":
                return struct.unpack(">II", tete[16:24])
            if tete[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", tete[6:10])
            if tete[:4] == b"RIFF" and tete[8:12] == b"WEBP":
                return dimensions_webp(tete)
            if tete[:2] == b"\xff\xd8":
                h.seek(2)
                return dimensions_jpeg(h)
    except (OSError, struct.error, IndexError):
        pass
    return None


def dimensions_webp(b):
    morceau = b[12:16]
    if morceau == b"VP8 " and b[23:26] == b"\x9d\x01\x2a":
        largeur, hauteur = struct.unpack("<HH", b[26:30])
        return largeur & 0x3FFF, hauteur & 0x3FFF
    if morceau == b"VP8L" and b[20] == 0x2F:
        bits = int.from_bytes(b[21:25], "little")
        return (bits & 0x3FFF) + 1, (bits >> 14 & 0x3FFF) + 1
    if morceau == b"VP8X":
        return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    return None


def dimensions_jpeg(h):
    """Parcourt les segments jusqu'au premier SOF. Une photo de téléphone
    tournée par son orientation EXIF (5 à 8) s'affiche largeur et hauteur
    échangées."""
    tournee = False
    while True:
        octet = h.read(1)
        if not octet:
            return None
        if octet != b"\xff":
            continue
        marqueur = h.read(1)
        while marqueur == b"\xff":  # octets de bourrage
            marqueur = h.read(1)
        if not marqueur or marqueur[0] in (0xD9, 0xDA):  # fin, ou image sans SOF avant elle
            return None
        m = marqueur[0]
        if m == 0x01 or 0xD0 <= m <= 0xD8:  # marqueurs sans longueur
            continue
        donnees = h.read(struct.unpack(">H", h.read(2))[0] - 2)
        if m in SOF:
            hauteur, largeur = struct.unpack(">HH", donnees[1:5])
            return (hauteur, largeur) if tournee else (largeur, hauteur)
        if m == 0xE1 and donnees[:6] == b"Exif\x00\x00":
            tournee = orientation_exif(donnees[6:]) in (5, 6, 7, 8)


def orientation_exif(tiff):
    """L'orientation EXIF (1 à 8) d'une photo, 1 si elle n'en dit rien."""
    try:
        ordre = {b"II": "<", b"MM": ">"}[tiff[:2]]
        ifd = struct.unpack(ordre + "I", tiff[4:8])[0]
        for i in range(struct.unpack(ordre + "H", tiff[ifd:ifd + 2])[0]):
            e = ifd + 2 + 12 * i
            if struct.unpack(ordre + "H", tiff[e:e + 2])[0] == 0x0112:
                return struct.unpack(ordre + "H", tiff[e + 8:e + 10])[0]
    except (KeyError, struct.error):
        pass
    return 1


def lire_fichiers(dossier, avertir):
    """Les images, vidéos et audios d'un dossier de cadre, dans l'ordre d'affichage."""
    trouves = []
    for f in dossier.iterdir():
        if not f.is_file() or f.name.startswith("."):
            continue
        ext = f.suffix.lower()
        if ext == ".pdf":
            avertir(f"{dossier.name}/{f.name} : un PDF ne s'affiche pas, exportez ses pages en images (voir LISEZMOI.txt)")
            continue
        genre = "image" if ext in IMAGE else "video" if ext in VIDEO else "audio" if ext in AUDIO else None
        if not genre:
            continue  # LISEZMOI.txt, fichiers système…
        taille = f.stat().st_size
        if taille > LIMITE:
            avertir(f"{dossier.name}/{f.name} : {taille / 1048576:.0f} Mo, au-delà des 25 Mo que Cloudflare accepte")
        elif genre == "image" and taille > IMAGE_LOURDE:
            avertir(f"{dossier.name}/{f.name} : image de {taille / 1048576:.0f} Mo, lente à charger ; 2 000 px de large suffisent")
        titre, rang = titre_et_rang(f.name)
        # Parenthèses, apostrophes et autres signes restent tels quels : encodés
        # (%28, %27…), Cloudflare les redirige vers leur forme lisible, un
        # aller-retour de plus à chaque fichier.
        chemin = "/".join(urllib.parse.quote(p, safe="!$&'()*+,;=:@") for p in ("cadres", dossier.name, f.name))
        x = {"titre": titre, "type": genre, "fichier": chemin}
        taille_image = dimensions(f) if genre == "image" else None
        if taille_image:
            x["largeur"], x["hauteur"] = taille_image
        trouves.append((ordre(titre, rang), x))
    return [x for _, x in sorted(trouves, key=lambda t: t[0])]


def secondes(t):
    if not t:
        return 0
    if t.isdigit():
        return int(t)
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", t)
    return sum(int(v or 0) * k for v, k in zip(m.groups(), (3600, 60, 1))) if m else 0


def lien_youtube(lien):
    """(identifiant, début en secondes) d'un lien YouTube, ou None."""
    try:
        u = urllib.parse.urlparse(lien)
    except ValueError:
        return None
    hote = re.sub(r"^(www|m|music)\.", "", (u.hostname or "").lower())
    requete = urllib.parse.parse_qs(u.query)
    ident = None
    if hote == "youtu.be":
        ident = u.path.strip("/").split("/")[0]
    elif hote in ("youtube.com", "youtube-nocookie.com"):
        ident = (requete.get("v") or [None])[0]
        if not ident:
            m = re.match(r"^/(?:embed|shorts|live|v)/([^/?#]+)", u.path)
            ident = m.group(1) if m else None
    if not ident or not ID_YOUTUBE.match(ident):
        return None
    return ident, secondes((requete.get("t") or requete.get("start") or [""])[0])


def lire_liens(avertir):
    """{clé de cadre : [nom tel qu'écrit, [(titre choisi ou None, identifiant, début)]]}"""
    if not LIENS.exists():
        return {}
    brut = LIENS.read_bytes()
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("cp1252")  # enregistré en « ANSI » par un vieil éditeur
    sections, courante = {}, None
    for n, ligne in enumerate(texte.splitlines(), start=1):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        m = re.fullmatch(r"\[(.+)\]", ligne)
        if m:
            nom = titre_et_rang(m.group(1).strip(), extension=False)[0]
            courante = sections.setdefault(cle(nom), [nom, []])
            continue
        titre, _, lien = ligne.rpartition("|")
        yt = lien_youtube(lien.strip())
        if not yt:
            avertir(f"youtube.txt, ligne {n} : lien YouTube non reconnu, ignoré")
        elif courante is None:
            avertir(f"youtube.txt, ligne {n} : lien placé avant tout [Cadre], ignoré")
        else:
            courante[1].append((titre.strip() or None, *yt))
    return sections


def infos_youtube(ident):
    """Titre et chaîne d'une vidéo, par l'oEmbed public de YouTube ; None si injoignable."""
    url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": f"https://www.youtube.com/watch?v={ident}", "format": "json"}
    )
    try:
        requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (portfolio VoixOff)"})
        with urllib.request.urlopen(requete, timeout=8) as r:
            d = json.load(r)
        return {"titre": d.get("title") or "", "auteur": d.get("author_name") or ""}
    except Exception:
        return None


def memoire():
    """Titres YouTube du catalogue précédent : on ne redemande que les nouveaux,
    et un catalogue construit hors ligne garde ceux qu'il connaissait."""
    try:
        ancien = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    listes = (ancien.get("cadres") or ancien.get("rubriques") or {}).values()  # « rubriques » : ancien format
    return {
        x["youtube"]: {"titre": x["titreYoutube"], "auteur": x.get("auteur", "")}
        for liste in listes
        for x in liste
        if x.get("youtube") and x.get("titreYoutube")
    }


def generer(bavard=True):
    alertes = []
    CADRES.mkdir(parents=True, exist_ok=True)

    dossiers = []
    for d in CADRES.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            nom, rang = titre_et_rang(d.name, extension=False)
            dossiers.append((ordre(nom, rang), nom, d))

    cadres = {}  # clé de comparaison → [nom du cadre, contenu]
    for _, nom, d in sorted(dossiers, key=lambda t: t[0]):
        k = cle(nom)
        if k in cadres:
            alertes.append(f"cadres/{d.name} : un autre dossier porte déjà le nom « {nom} », leurs contenus sont réunis")
            cadres[k][1].extend(lire_fichiers(d, alertes.append))
        else:
            cadres[k] = [nom, lire_fichiers(d, alertes.append)]

    liens = lire_liens(alertes.append)
    connus = memoire()
    a_demander = sorted({ident for _, entrees in liens.values() for _, ident, _ in entrees} - connus.keys())
    if a_demander:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for ident, infos in zip(a_demander, pool.map(infos_youtube, a_demander)):
                if infos and infos["titre"]:
                    connus[ident] = infos
                else:
                    alertes.append(f"YouTube : titre de la vidéo {ident} introuvable (hors ligne, vidéo privée ou supprimée ?)")

    for k, (nom, entrees) in liens.items():
        if k not in cadres:
            alertes.append(f"youtube.txt : [{nom}] n'a pas de dossier dans cadres/")
            cadres[k] = [nom, []]
        for titre, ident, debut in entrees:
            infos = connus.get(ident, {})
            x = {"titre": titre or infos.get("titre") or "Vidéo YouTube", "type": "youtube", "youtube": ident}
            if debut:
                x["debut"] = debut
            if infos.get("titre"):
                x["titreYoutube"] = infos["titre"]
            if infos.get("auteur"):
                x["auteur"] = infos["auteur"]
            cadres[k][1].append(x)

    catalogue = {"cadres": {nom: liste for nom, liste in cadres.values()}}
    texte = json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n"
    ancien = CATALOGUE.read_text(encoding="utf-8") if CATALOGUE.exists() else ""
    if texte != ancien:  # pas de réécriture inutile : le fichier ne change qu'avec le contenu
        CATALOGUE.write_text(texte, encoding="utf-8")

    if bavard:
        tout = [x for _, liste in cadres.values() for x in liste]
        compte = {g: sum(x["type"] == g for x in tout) for g in ("image", "video", "audio", "youtube")}
        for a in alertes:
            print("  !", a)
        print(f"Catalogue : {compte['image']} image(s), {compte['video']} vidéo(s), {compte['audio']} audio(s), "
              f"{compte['youtube']} vidéo(s) YouTube, {len(cadres)} cadre(s), dans {CATALOGUE.relative_to(ICI)}")
    return catalogue, alertes


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # console Windows sans UTF-8
    generer()
