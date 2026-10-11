/*
 * Doublures des liaisons Cloudflare pour tester les fonctions sans compte :
 * KV en mémoire, API Cache en mémoire, et un Workers AI dont on écrit les
 * réponses à l'avance. Les fonctions elles-mêmes sont importées telles
 * qu'elles partent en production.
 */

export class KvMemoire {
  constructor() { this.donnees = new Map(); this.ecritures = 0; }
  async get(cle) { return this.donnees.has(cle) ? this.donnees.get(cle) : null; }
  async put(cle, valeur) { this.ecritures++; this.donnees.set(cle, String(valeur)); }
  cles() { return Array.from(this.donnees.keys()); }
}

export class CacheMemoire {
  constructor() { this.donnees = new Map(); }
  async match(requete) {
    const r = this.donnees.get(requete.url);
    return r ? new Response(r) : undefined;
  }
  async put(requete, reponse) { this.donnees.set(requete.url, await reponse.text()); }
}

/**
 * `reponses` : une fonction (modele, corps, n) => réponse ou erreur à lever,
 * ou une liste consommée dans l'ordre (la dernière se répète).
 */
export class AiScripte {
  constructor(reponses) { this.reponses = reponses; this.appels = []; }
  async run(modele, corps) {
    const n = this.appels.length;
    this.appels.push({ modele, corps });
    const r = typeof this.reponses === "function"
      ? this.reponses(modele, corps, n)
      : this.reponses[Math.min(n, this.reponses.length - 1)];
    if (r instanceof Error) throw r;
    return r;
  }
}

export const IP = "196.47.12.34";

export function requete(chemin, corps, ip = IP) {
  return new Request("https://43wacc.pages.dev" + chemin, {
    method: "POST",
    headers: { "content-type": "application/json", "CF-Connecting-IP": ip },
    body: typeof corps === "string" ? corps : JSON.stringify(corps),
  });
}

export function environnement(surcharge = {}) {
  return Object.assign({
    GARDE: new KvMemoire(),
    SEL_IP: "sel-de-test",
    AI: new AiScripte([]),
  }, surcharge);
}

export function contexte(chemin, corps, env, options = {}) {
  return {
    request: requete(chemin, corps, options.ip),
    env: env,
    cache: options.cache === undefined ? new CacheMemoire() : options.cache,
    waitUntil: undefined,
  };
}

// Réponse au format Llama (champ `response`), éventuellement déjà un objet.
export const reponseLlama = (objet, usage = { prompt_tokens: 2000, completion_tokens: 300 }) =>
  ({ response: objet, usage });

// Réponse au format OpenAI (Qwen 3), raisonnement compris.
export const reponseQwen = (texte, usage = { prompt_tokens: 1800, completion_tokens: 120 }) =>
  ({ choices: [{ message: { role: "assistant", content: texte, reasoning_content: "je réfléchis" } }], usage });

export const REQUETE_PAYS = {
  source: "pays",
  filtres: [{ champ: "zone", op: "=", valeur: "Afrique de l'Ouest" }],
  tri: { champ: "crp", sens: "desc" },
  limite: 5,
  champs: ["nom", "crp"],
  agregat: null,
  parametres: null,
  reformulation: "Les 5 pays d'Afrique de l'Ouest à la prime de risque la plus élevée",
};

export function dossier(horizon = 5) {
  const serie = (v) => Array.from({ length: horizon }, () => v);
  return {
    societe: { pays: "Côte d'Ivoire", industrie: "Food Processing", activite: "Transformation de cacao" },
    historique: {
      annees: [2023, 2024, 2025], ca: [100, 110, 121], ebitda: [20, 21, 25], da: [4, 4.2, 4.5],
      capex: [null, 6, 7], bfr: [12, 13, 14], dette_nette: 30,
    },
    normalise: { marge_ebitda_3ans: 0.2, croissance_tcam: 0.1, da_sur_ca: 0.038, bfr_sur_ca: 0.115, anomalies: [] },
    secteur: { nom: "Food Products", n: 18, marge_mediane: 0.15, marge_tendance_pts_an: -0.003, croissance_mediane: 0.05, beta_median: 0.62 },
    macro: { inflation_locale: 0.03, inflation_ref: 0.025, cmpc_local: 0.12, taux_is: 0.25 },
    defauts: { croissance: serie(0.1), marge: 0.207, da: 0.037, capex: serie(5), bfr: 0.116, g: 0.02 },
    regles: { croissance: serie(0.08), marge: serie(0.18), g: 0.03, capex_sur_da: serie(1.3), da_sur_ca: 0.038, bfr_sur_ca: 0.115 },
    bornes: { croissance: [-0.2, 0.3], marge: [0, 0.6], g: [0, 0.04], capex_sur_da: [0.8, 2.5], bfr_sur_ca: [-0.2, 0.5] },
  };
}

export function analyse(horizon = 5, surcharge = {}) {
  const serie = (v) => Array.from({ length: horizon }, () => v);
  return Object.assign({
    hypotheses: { croissance: serie(0.07), marge: serie(0.17), da_sur_ca: 0.04, capex_sur_da: serie(1.2), bfr_sur_ca: 0.12, g: 0.03 },
    justifications: { croissance: "TCAM de 10 %.", marge: "Médiane à 15 %.", capex: "1,2 fois les D&A.", bfr: "11,5 % du CA.", g: "Inflation à 3 %." },
    alertes: [],
    confiance: "bonne",
    resume: "Croissance ramenée vers le secteur.",
  }, surcharge);
}
