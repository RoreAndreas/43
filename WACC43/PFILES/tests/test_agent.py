"""L'assistant : gabarits, moteur de requêtes et panneau.

Critère d'acceptation du brief : les trente premières questions de
`questions.json` passent au niveau 0, sans serveur. Le reste vérifie le moteur
— résolution des noms, filtres, agrégats, CMPC à la demande — puis le panneau,
hors ligne et face à un serveur simulé. Le modèle de langage n'est jamais
appelé ici : ses réponses sont jouées par `page.route`.
"""

import json
import statistics
from pathlib import Path

import pytest

from conformite import conforme

QUESTIONS = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))["questions"]
NIVEAU0 = [q for q in QUESTIONS if q["niveau"] == 0]
PAGE = Path(__file__).parents[1] / "site" / "index.html"


@pytest.fixture(scope="module")
def page_seule(navigateur):
    """Une seule page pour les trente questions : elles ne la modifient pas."""
    if not PAGE.exists():
        pytest.skip(f"page non construite : {PAGE}")
    onglet = navigateur.new_page(viewport={"width": 1280, "height": 900})
    onglet.goto(PAGE.resolve().as_uri(), timeout=90000)
    onglet.wait_for_selector("#paramsMain .card-block")
    yield onglet
    onglet.close()


def resoudre(page, requete):
    """La requête telle que la page l'exécute, noms résolus."""
    sans = {k: v for k, v in requete.items() if k != "champs_inclus"}
    return page.evaluate("q => { const r = executerReponse(q); return { ok: r.ok, code: r.code || null, message: r.message || null, requete: r.requete || null, n: r.n }; }", sans)


def test_le_jeu_compte_cinquante_questions_dont_trente_de_niveau_0():
    assert len(QUESTIONS) == 50
    assert len(NIVEAU0) == 30
    assert [q["id"] for q in QUESTIONS] == list(range(1, 51))


@pytest.mark.parametrize("q", NIVEAU0, ids=lambda q: f"q{q['id']:02d}")
def test_les_trente_questions_passent_sans_serveur(page_seule, q):
    g = page_seule.evaluate("q => reconnaitreGabarit(q)", q["question"])
    assert g, "aucun gabarit ne reconnaît la question"
    obtenu = resoudre(page_seule, g["requete"])
    assert obtenu["ok"], obtenu["message"]
    attendu = resoudre(page_seule, q["attendu"])
    assert attendu["ok"], "l'attendu lui-même ne s'exécute pas : " + str(attendu["message"])
    ok, raison = conforme(obtenu["requete"], attendu["requete"], q["attendu"].get("champs_inclus"))
    assert ok, raison


# ------------------------------------------------------- résolution des noms

@pytest.mark.parametrize("texte, attendu", [
    ("cote d'ivoire", "Côte d'Ivoire"),     # casse et accents
    ("Maroc", "Morocco"),                   # lexique français
    ("Senegall", "Senegal"),                # distance d'édition
    ("Afrique du Sud", "South Africa"),
])
def test_un_pays_se_resout(page_seule, texte, attendu):
    r = page_seule.evaluate("t => resoudreNom(t, Object.keys(DATA.pays))", texte)
    assert r["ok"] and r["valeur"] == attendu


def test_deux_candidats_font_une_erreur_ambigu(page_seule):
    r = page_seule.evaluate("() => resoudreNom('bank', Object.keys(DATA.industries))")
    assert r["ok"] is False and r["code"] == "ambigu"
    assert set(r["candidats"]) >= {"Bank (Money Center)", "Banks (Regional)"}


def test_un_nom_inconnu_est_signale(page_seule):
    r = page_seule.evaluate("() => resoudreNom('Atlantide', Object.keys(DATA.pays))")
    assert r["ok"] is False and r["code"] == "inconnu"


# ---------------------------------------------------------------- le moteur

def test_un_champ_inconnu_est_refuse(page_seule):
    r = page_seule.evaluate("() => executerRequete({ source: 'pays', filtres: [{ champ: 'pib', op: '>', valeur: 1 }] })")
    assert r["ok"] is False and r["code"] == "invalide"


def test_un_operateur_inconnu_est_refuse(page_seule):
    r = page_seule.evaluate("() => executerRequete({ source: 'pays', filtres: [{ champ: 'crp', op: 'environ', valeur: 1 }] })")
    assert r["ok"] is False and r["code"] == "invalide"


def test_le_nom_damodaran_trouve_les_societes_libellees_usa(page_seule, donnees):
    r = page_seule.evaluate("""() => executerRequete({ source: 'societes',
        filtres: [{ champ: 'pays', op: '=', valeur: 'United States' }, { champ: 'industrie', op: '=', valeur: 'Banks' }] })""")
    assert r["ok"] and r["n"] > 0
    attendu = sum(1 for s in donnees["comparables"]["societes"].values() if s["pays"] == "USA" and s["industrie"] == "Banks")
    assert r["n"] == attendu


def test_la_mediane_est_celle_des_donnees(page_seule, donnees):
    r = page_seule.evaluate("""() => executerRequete({ source: 'societes',
        filtres: [{ champ: 'industrie', op: '=', valeur: 'Banks' }, { champ: 'continent', op: '=', valeur: 'Afrique' }],
        agregat: { fonction: 'mediane', champ: 'beta_3ans' } })""")
    valeurs = [s["beta_3ans"] for s in donnees["comparables"]["societes"].values()
               if s["industrie"] == "Banks" and s["continent"] == "Afrique" and s["beta_3ans"] is not None]
    assert r["agregat"]["valeur"] == pytest.approx(statistics.median(valeurs))
    assert r["agregat"]["n"] == len(valeurs)


def test_les_champs_de_comptes_se_derivent_par_exercice(page_seule):
    r = page_seule.evaluate("""() => executerRequete({ source: 'societes', filtres: [{ champ: 'industrie', op: '=', valeur: 'Banks' }],
        tri: { champ: 'capitalisation', sens: 'desc' }, limite: 3, champs: ['nom', 'ca_2025', 'ebitda_2025', 'marge_ebitda_2025'] })""")
    assert r["ok"] and len(r["lignes"]) == 3
    assert set(r["champs"]) >= {"ca_2025", "marge_ebitda_2025"}


def test_le_cmpc_a_la_demande_egale_celui_de_l_ecran(page_seule):
    """Mêmes paramètres, même calcul — et la sélection de l'écran intacte."""
    r = page_seule.evaluate("""() => {
        const avant = JSON.stringify(params);
        const r = executerRequete({ source: 'cmpc', parametres: { pays: params.country, industrie: params.industry, referentiel: 'damodaran' } });
        return { r: r, intact: JSON.stringify(params) === avant, ecran: model.brut.waccLocal };
    }""")
    assert r["intact"]
    assert r["r"]["ok"]
    assert r["r"]["cmpc"]["cmpc_local"] == pytest.approx(r["ecran"])


def test_le_spread_des_industries_est_celui_qui_entre_dans_le_kd(page_seule):
    """Damodaran publie un écart-type ; le Kd en tire un spread par la grille."""
    r = page_seule.evaluate("""() => {
        const brut = DATA.industries['Food Processing'].spread;
        const ligne = executerRequete({ source: 'industries', filtres: [{ champ: 'nom', op: '=', valeur: 'Food Processing' }] }).lignes[0];
        return { affiche: ligne.spread, grille: adjustedSpread(brut).value };
    }""")
    assert r["affiche"] == pytest.approx(r["grille"])
    assert r["affiche"] < 0.1


# ---------------------------------------------------------- panneau, hors ligne

def demander(page, question):
    page.fill("#agentQuestion", question)
    page.click("#agentDemander")
    page.wait_for_timeout(250)
    return page.inner_text("#agentReponse")


def test_depuis_un_fichier_le_panneau_annonce_le_mode_hors_ligne(page):
    assert "Mode hors ligne : gabarits seulement" in page.inner_text("#agentPanneau")


def test_une_question_reconnue_s_affiche_avec_sa_reformulation(page):
    texte = demander(page, "Top 5 pays d'Afrique par prime de risque")
    assert "J'ai compris" in texte
    assert len(page.query_selector_all("#agentReponse .agent-table tbody tr")) == 5
    assert "Damodaran" in texte


def test_une_question_inconnue_dit_que_l_assistant_ne_repond_pas(page):
    texte = demander(page, "Quelle est la météo à Abidjan demain ?")
    assert "ne répond pas" in texte


def test_corriger_preremplit_la_saisie(page):
    demander(page, "taux d'IS du Sénégal")
    page.fill("#agentQuestion", "")
    page.click("#agentReponse [data-agent-corriger]")
    assert page.input_value("#agentQuestion") == "taux d'IS du Sénégal"


def test_l_historique_garde_les_dix_dernieres_questions(page):
    for i in range(12):
        demander(page, f"taux d'IS du Sénégal {i}")
    # La dernière est affichée, les neuf précédentes sont listées.
    assert len(page.query_selector_all("#agentHistorique li")) == 9


def test_le_panneau_n_ecrit_rien_dans_le_navigateur(navigateur):
    onglet = navigateur.new_page()
    onglet.add_init_script("""
        window.__ecritures = 0;
        const origine = Storage.prototype.setItem;
        Storage.prototype.setItem = function () { window.__ecritures++; return origine.apply(this, arguments); };
    """)
    onglet.goto(PAGE.resolve().as_uri(), timeout=90000)
    onglet.wait_for_selector("#paramsMain .card-block")
    demander(onglet, "Prime de risque de la Côte d'Ivoire")
    demander(onglet, "question sans gabarit")
    assert onglet.evaluate("window.__ecritures") == 0
    onglet.close()


def test_appliquer_un_cmpc_le_porte_a_l_ecran(page):
    demander(page, "CMPC d'une cimenterie au Sénégal en 2026")
    page.click("#agentReponse [data-agent-appliquer]")
    assert page.evaluate("[params.country, params.industry]") == ["Senegal", "Construction Supplies"]


# ------------------------------------------------- en ligne, serveur simulé

REQUETE_SERVEUR = {"source": "pays", "filtres": [{"champ": "zone", "op": "=", "valeur": "Afrique de l'Est"}],
                   "tri": {"champ": "tax", "sens": "asc"}, "limite": 3, "champs": ["nom", "tax"],
                   "reformulation": "Les 3 pays d'Afrique de l'Est au taux d'IS le plus bas"}


def jouer(page, statut, corps, appels):
    def repondre(route):
        appels.append(json.loads(route.request.post_data))
        route.fulfill(status=statut, content_type="application/json", body=json.dumps(corps))
    page.route("**/api/ask", repondre)


def test_une_question_reconnue_ne_sollicite_pas_le_serveur(page_http):
    appels = []
    jouer(page_http, 200, {"ok": True, "requete": REQUETE_SERVEUR}, appels)
    demander(page_http, "Prime de risque de la Côte d'Ivoire")
    assert appels == []


def test_le_serveur_traduit_la_page_execute(page_http):
    appels = []
    jouer(page_http, 200, {"ok": True, "requete": REQUETE_SERVEUR, "modele": "@cf/qwen/qwen3-30b-a3b-fp8"}, appels)
    demander(page_http, "Quels marchés de l'est du continent sont les plus avantageux ?")
    page_http.wait_for_selector("#agentReponse .agent-table")
    texte = page_http.inner_text("#agentReponse")
    assert len(appels) == 1
    # Le contexte de l'écran part avec la question, jamais les données.
    assert set(appels[0]) == {"question", "contexte"}
    assert appels[0]["contexte"]["pays"] == page_http.evaluate("params.country")
    assert "assistant en ligne" in texte
    assert len(page_http.query_selector_all("#agentReponse .agent-table tbody tr")) == 3


def test_une_requete_serveur_invalide_est_refusee_par_la_page(page_http):
    appels = []
    jouer(page_http, 200, {"ok": True, "requete": {"source": "pays", "filtres": [{"champ": "pib", "op": ">", "valeur": 1}]}}, appels)
    page_http.fill("#agentQuestion", "question exotique")
    page_http.click("#agentDemander")
    page_http.wait_for_selector("#agentReponse .agent-erreur")
    assert "Champ inconnu" in page_http.inner_text("#agentReponse")


def test_le_quota_atteint_bascule_sur_les_gabarits(page_http):
    appels = []
    jouer(page_http, 429, {"ok": False, "code": "quota", "reprise": "2026-10-12T00:00:00.000Z"}, appels)
    page_http.fill("#agentQuestion", "question exotique")
    page_http.click("#agentDemander")
    page_http.wait_for_selector("#agentReponse .agent-erreur")
    assert "Quota" in page_http.inner_text("#agentReponse")
    assert "Quota du jour atteint" in page_http.inner_text('[data-o="agent-etat"]')
    # Les gabarits restent servis.
    assert "J'ai compris" in demander(page_http, "taux d'IS du Sénégal")


def test_le_plafond_gratuit_epuise_passe_hors_ligne(page_http):
    appels = []
    jouer(page_http, 503, {"ok": False, "code": "plafond"}, appels)
    page_http.fill("#agentQuestion", "question exotique")
    page_http.click("#agentDemander")
    page_http.wait_for_selector("#agentReponse .agent-erreur")
    assert "Mode hors ligne" in page_http.inner_text('[data-o="agent-etat"]')
    # Hors ligne, la question suivante ne tente plus le serveur.
    page_http.fill("#agentQuestion", "autre question exotique")
    page_http.click("#agentDemander")
    page_http.wait_for_timeout(300)
    assert len(appels) == 1


def test_une_page_sans_fonction_serveur_reste_utilisable(page_http):
    """Déploiement sans `functions/` : la route renvoie 404 ou 405."""
    page_http.route("**/api/ask", lambda route: route.fulfill(status=405, body="Method Not Allowed"))
    page_http.fill("#agentQuestion", "question exotique")
    page_http.click("#agentDemander")
    page_http.wait_for_selector("#agentReponse .agent-erreur")
    assert "non déployé" in page_http.inner_text("#agentReponse")
    assert "J'ai compris" in demander(page_http, "taux d'IS du Sénégal")
