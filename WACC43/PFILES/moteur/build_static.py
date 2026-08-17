"""
Construction de la page statique.

    python build_static.py

Télécharge les bases Damodaran et les taux US Treasury, les condense, puis
écrit `site/index.html` : un fichier autonome qui recalcule le CMPC dans le
navigateur, sans serveur. À relancer quand Damodaran publie sa mise à jour
annuelle (janvier), ou trimestriellement pour figer un taux Treasury plus frais
sur l'exercice en cours.
"""

import argparse
import json
import shutil
import time
from pathlib import Path

import brvm_core
import wacc_core
from wacc_html import render_page

RACINE = Path(__file__).parents[1]
SITE = RACINE / "site"          # dossier publié par Cloudflare Pages
DONNEES = RACINE / "donnees"    # jeu de données lisible, hors du dossier publié

# Seuils de vraisemblance du jeu de données extrait (référence : 157 pays,
# 94 industries). En dessous, la source a probablement changé de format.
MIN_COUNTRIES = 100
MIN_INDUSTRIES = 60


def _reclasser_brvm(brvm: dict, univers: dict):
    """Range les sociétés BRVM dans la nomenclature de l'export.

    Rend (industries, sociétés restées hors export). Les industries sont celles
    de l'export qui comptent au moins une société cotée à Abidjan : ce sont les
    seules pour lesquelles un bêta coté est disponible, et donc les seules où le
    coût des fonds propres peut être calculé.
    """
    par_ticker = univers.get("industrie_par_ticker") or {}
    paniers, restants = {}, []
    for ticker in brvm.get("societes", {}):
        nom = par_ticker.get(ticker)
        if nom is None:
            restants.append(ticker)
            continue
        paniers.setdefault(nom, []).append(ticker)
    return (
        [{"nom": nom, "tickers": sorted(t)} for nom, t in sorted(paniers.items())],
        sorted(restants),
    )


def main():
    parser = argparse.ArgumentParser(description="Génère la page statique du CMPC")
    parser.add_argument("--out", default=str(SITE), help="dossier de sortie (défaut : site/)")
    parser.add_argument("--years", type=int, default=10, help="profondeur d'historique des taux")
    parser.add_argument("--keep-data", action="store_true", help="écrit aussi donnees/data.json")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from datetime import datetime

    current = datetime.now().year
    years = list(range(current, current - args.years, -1))

    started = time.time()
    step = {"n": 0}

    def progress(message):
        step["n"] += 1
        print(f"  [{step['n']:>2}] {message}")

    print("Téléchargement des sources...")
    dataset = wacc_core.build_dataset(years=years, progress=progress)

    # Garde-fou : si Damodaran change de format ou renvoie une page d'erreur,
    # l'extraction se vide silencieusement. Mieux vaut échouer que publier
    # automatiquement une page sans données.
    if len(dataset["pays"]) < MIN_COUNTRIES:
        raise SystemExit(f"Seulement {len(dataset['pays'])} pays extraits (minimum {MIN_COUNTRIES}) — page non écrite.")
    if len(dataset["industries"]) < MIN_INDUSTRIES:
        raise SystemExit(f"Seulement {len(dataset['industries'])} industries extraites (minimum {MIN_INDUSTRIES}) — page non écrite.")
    if not dataset["rf"]:
        raise SystemExit("Aucun taux US Treasury récupéré — page non écrite.")

    # Le découpage géographique se rapproche sur le libellé exact. Damodaran
    # republie chaque janvier, et une retouche d'orthographe sortirait un pays du
    # découpage sans erreur visible. On ne bloque pas la publication pour autant :
    # le pays reste sélectionnable, il apparaît seulement sous « Autres ».
    inclassables = dataset.get("inclassables") or []
    if inclassables:
        print(f"  /!\\ {len(inclassables)} pays sans zone, à rattacher dans zones.py :")
        for nom in inclassables:
            print(f"       - {nom}")

    # Volet BRVM : instantané pris au build. La page ne suit jamais la cadence du
    # scraper SIKAPRO, qui tourne toutes les 10 minutes dans son propre projet.
    dataset["brvm"] = brvm_core.build_brvm(progress=progress)

    import comparables as _comparables
    import zones as _zones

    # Univers de comparables : l'export S&P déposé dans le dossier du projet.
    # Il donne la nomenclature d'industries, le gearing sectoriel observé, et
    # une couverture continentale que la seule place d'Abidjan ne permettait pas.
    # L'export est déposé à la racine de WACC43, un niveau au-dessus de PFILES.
    univers = _comparables.construire(RACINE.parent, progress=progress)
    if univers is None:
        # Échec franc plutôt qu'avertissement : la nomenclature d'industries, le
        # gearing sectoriel et les effectifs de la carte en dépendent tous. Sans
        # cet univers, la page se construit sans erreur mais publie une version
        # dégradée — ce qui est arrivé, et n'a été vu qu'en inspectant le site.
        raise SystemExit(
            "Aucun export SPGlobal_Export_*.xlsx trouvé autour de "
            f"{RACINE.parent} — page non écrite."
        )
    else:
        index, orphelins = _comparables.indexer_par_zone(univers, _zones.classer)
        dataset["comparables"] = {
            "source": univers["source"],
            "industries": univers["industries"],
            "zones": index,
        }
        dataset["zones_societes"] = index
        if orphelins:
            print(f"  /!\\ pays de comparables sans zone : {', '.join(orphelins)}")

        # Les bêtas cotés viennent de la BRVM, classés selon ses douze secteurs.
        # On les reclasse dans la nomenclature de l'export pour n'avoir qu'une
        # seule taxonomie ; les sociétés absentes de l'export gardent la leur.
        reclasse, restants = _reclasser_brvm(dataset["brvm"], univers)
        dataset["brvm"]["industries"] = reclasse
        if restants:
            print(f"  /!\\ sociétés BRVM hors export : {', '.join(restants)}")

    page = render_page(dataset)
    target = out / "index.html"
    target.write_text(page, encoding="utf-8")

    if args.keep_data:
        DONNEES.mkdir(parents=True, exist_ok=True)
        (DONNEES / "data.json").write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    payload = len(json.dumps(dataset, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print()
    print(f"  pays        : {len(dataset['pays'])}")
    for continent, membres in dataset["options"]["countries_grouped"]:
        print(f"     {continent:<12}: {len(membres)}")
    print(f"  industries  : {len(dataset['industries'])}")
    print(f"  taux        : {len(dataset['rf'])} couples (année, maturité)")
    print(f"  données     : {payload / 1024:.1f} Ko")
    print(f"  page        : {target} — {target.stat().st_size / 1024:.1f} Ko")
    print(f"  durée       : {time.time() - started:.0f} s")
    print()
    print("Ouvre le fichier dans un navigateur, ou dépose le dossier sur un")
    print("hébergement statique (Cloudflare Pages, GitHub Pages, Netlify).")


if __name__ == "__main__":
    main()
