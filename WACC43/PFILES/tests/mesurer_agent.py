"""Mesure de l'agent en ligne : traducteur et analyste, sur le site déployé.

    python tests/mesurer_agent.py --url https://43wacc.pages.dev
    python tests/mesurer_agent.py --aveugle        # prépare la lecture à l'aveugle

Ce script n'entre pas dans la suite de tests : il interroge les vraies
fonctions serveur, donc les vrais modèles Workers AI, et consomme le quota de
l'adresse qui le lance — vingt questions et cinq prévisions, soit la moitié du
quota de questions et tout celui des prévisions d'une journée.

Il note dans `tests/RESULTATS.md`, avec la date et le modèle rapporté par le
serveur :
- traducteur : taux de JSON valide et taux de requête identique à l'attendu,
  sur les vingt questions de niveau 1 de `questions.json` ;
- analyste : taux de réponse valide et nombre de valeurs ramenées aux bornes,
  sur les cinq dossiers de `test_regles.py`.

Pour comparer des modèles, changer MODELE_TRADUCTEUR ou MODELE_ANALYSTE dans
Cloudflare, redéployer, relancer. Les justifications de chaque analyste sont
gardées dans `tests/analyses/<modèle>/` ; `--aveugle` les recopie sous des
lettres A, B, C dans `tests/analyses/aveugle/`, la correspondance dans
`cle.json`, pour qu'Alexandre les note de 1 à 5 sans savoir qui a écrit quoi.
"""

import argparse
import datetime
import json
import random
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ICI = Path(__file__).parent
sys.path.insert(0, str(ICI))

from conformite import conforme  # noqa: E402

PAGE = ICI.parent / "site" / "index.html"
RESULTATS = ICI / "RESULTATS.md"
ANALYSES = ICI / "analyses"


def poster(url, corps, delai=90):
    requete = urllib.request.Request(url, data=json.dumps(corps).encode("utf-8"), method="POST",
                                     headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=delai) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, {"code": "reseau", "message": str(e)}


def ouvrir_page(playwright):
    nav = playwright.chromium.launch()
    page = nav.new_page(viewport={"width": 1280, "height": 900})
    page.goto(PAGE.resolve().as_uri(), timeout=90000)
    page.wait_for_selector("#paramsMain .card-block")
    return nav, page


def resoudre(page, requete):
    sans = {k: v for k, v in requete.items() if k != "champs_inclus"}
    return page.evaluate("q => { const r = executerReponse(q); return r.requete || { source: q.source }; }", sans)


def mesurer_traducteur(base, page):
    questions = [q for q in json.loads((ICI / "questions.json").read_text(encoding="utf-8"))["questions"] if q["niveau"] == 1]
    lignes, valides, identiques, modele = [], 0, 0, None
    for q in questions:
        statut, corps = poster(base + "/api/ask", {"question": q["question"]})
        ok = statut == 200 and corps.get("ok") and corps.get("requete")
        modele = modele or corps.get("modele")
        if not ok:
            lignes.append(f"| {q['id']} | non | non | {corps.get('code', statut)} |")
            continue
        valides += 1
        bon, raison = conforme(resoudre(page, corps["requete"]), resoudre(page, q["attendu"]), q["attendu"].get("champs_inclus"))
        identiques += bon
        lignes.append(f"| {q['id']} | oui | {'oui' if bon else 'non'} | {raison or '—'} |")
    return {"modele": modele, "n": len(questions), "valides": valides, "identiques": identiques, "lignes": lignes}


def dossiers(page, dossier_tmp):
    from test_etats_financiers import balance
    from test_regles import DOSSIERS
    sortie = {}
    for nom, comptes in DOSSIERS.items():
        page.click('.tabs button[data-groupe="valorisation"]')
        page.click('.valo-vues button[data-vue="etats"]')
        page.set_input_files("#valoBgFichier", str(balance(dossier_tmp / f"{nom}.xlsx", comptes=comptes)))
        page.wait_for_selector("#valoEtats .etat-table")
        if not page.evaluate("VALO.prevMode === 'estimation'"):
            page.click('#valoEtats [data-action="mode-prev"]')
        page.wait_for_selector("#valoEtats .traj-enveloppe .hyp-boulon")
        sortie[nom] = page.evaluate("""() => { VALO.jeux.regles = hypothesesParRegles(VALO.bg, 5); return dossierAnalyste(); }""")
    return sortie


def mesurer_analyste(base, page):
    lignes, valides, bornees, modele = [], 0, 0, None
    with tempfile.TemporaryDirectory() as tmp:
        lots = dossiers(page, Path(tmp))
    for nom, dossier in lots.items():
        statut, corps = poster(base + "/api/forecast", dossier, delai=120)
        modele = modele or corps.get("modele")
        if not (statut == 200 and corps.get("ok")):
            lignes.append(f"| {nom} | non | — | {corps.get('code', statut)} |")
            continue
        valides += 1
        a = corps["analyse"]
        ramenees = sum(1 for x in a["alertes"] if "borne de l'outil" in x)
        bornees += ramenees
        lignes.append(f"| {nom} | oui | {ramenees} | confiance {a['confiance']} |")
        dossier_modele = ANALYSES / (modele or "inconnu").replace("@cf/", "").replace("/", "_")
        dossier_modele.mkdir(parents=True, exist_ok=True)
        (dossier_modele / f"{nom}.json").write_text(json.dumps({"dossier": dossier, "analyse": a}, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
    return {"modele": modele, "n": len(lots), "valides": valides, "bornees": bornees, "lignes": lignes}


def ecrire(traducteur, analyste, base):
    date = datetime.date.today().isoformat()
    bloc = [f"\n## Mesure du {date} — {base}\n"]
    if traducteur:
        t = traducteur
        bloc += [f"### Traducteur : `{t['modele']}`\n",
                 f"JSON valide : {t['valides']}/{t['n']} ; requête identique à l'attendu : **{t['identiques']}/{t['n']}** "
                 f"({100 * t['identiques'] / t['n']:.0f} %).\n",
                 "| Question | JSON valide | Identique | Écart |", "|---|---|---|---|", *t["lignes"], ""]
    if analyste:
        a = analyste
        bloc += [f"### Analyste : `{a['modele']}`\n",
                 f"Réponses valides : **{a['valides']}/{a['n']}** ; valeurs ramenées aux bornes par le serveur : {a['bornees']}.\n",
                 "| Dossier | Valide | Valeurs bornées | Remarque |", "|---|---|---|---|", *a["lignes"], ""]
    texte = RESULTATS.read_text(encoding="utf-8") if RESULTATS.exists() else "# Résultats de l'agent\n"
    RESULTATS.write_text(texte.rstrip() + "\n" + "\n".join(bloc), encoding="utf-8")


def aveugle():
    modeles = sorted(p for p in ANALYSES.iterdir() if p.is_dir() and p.name != "aveugle") if ANALYSES.exists() else []
    if len(modeles) < 2:
        sys.exit("Il faut les analyses d'au moins deux modèles dans tests/analyses/.")
    lettres = list("ABCDEFGH")[:len(modeles)]
    random.shuffle(lettres)
    cible = ANALYSES / "aveugle"
    cible.mkdir(exist_ok=True)
    cle = {}
    for lettre, dossier_modele in zip(lettres, modeles):
        cle[lettre] = dossier_modele.name
        for f in dossier_modele.glob("*.json"):
            a = json.loads(f.read_text(encoding="utf-8"))["analyse"]
            j = a["justifications"]
            texte = [f"# Analyste {lettre} — dossier {f.stem}", "", a["resume"], "",
                     *[f"- **{k}** : {v}" for k, v in j.items()], "", "Alertes :", *[f"- {x}" for x in a["alertes"]],
                     "", "Note de 1 à 5 : ___"]
            (cible / f"{lettre}_{f.stem}.md").write_text("\n".join(texte), encoding="utf-8")
    (cible / "cle.json").write_text(json.dumps(cle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(modeles)} analystes anonymisés dans {cible} ; ne pas ouvrir cle.json avant d'avoir noté.")


def main():
    parser = argparse.ArgumentParser(description="Mesure le traducteur et l'analyste en ligne")
    parser.add_argument("--url", default="https://43wacc.pages.dev", help="site déployé")
    parser.add_argument("--sans-traducteur", action="store_true")
    parser.add_argument("--sans-analyste", action="store_true")
    parser.add_argument("--aveugle", action="store_true", help="anonymise les analyses déjà recueillies")
    args = parser.parse_args()
    if args.aveugle:
        aveugle()
        return
    from playwright.sync_api import sync_playwright
    base = args.url.rstrip("/")
    with sync_playwright() as p:
        nav, page = ouvrir_page(p)
        traducteur = None if args.sans_traducteur else mesurer_traducteur(base, page)
        analyste = None if args.sans_analyste else mesurer_analyste(base, page)
        nav.close()
    ecrire(traducteur, analyste, base)
    print("Résultats ajoutés à", RESULTATS)


if __name__ == "__main__":
    main()
