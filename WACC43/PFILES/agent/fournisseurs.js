/*
 * Adaptateur des modèles de langage : Cloudflare Workers AI, seul.
 *
 * Le cerveau de l'agent doit rester gratuit. De toutes les offres comparées
 * dans la note du 5 octobre 2026, Workers AI est la seule qui tienne pour un
 * outil public : un plafond journalier prévisible (10 000 neurones offerts
 * par jour), aucune contrepartie sur les données, et l'hébergeur qui sert
 * déjà la page. Sur le plan Workers Free, l'enveloppe épuisée fait échouer
 * l'appel au lieu de le facturer ; `garde.js` s'arrête de toute façon avant.
 *
 * Le nom du modèle se lit dans les variables MODELE_TRADUCTEUR et
 * MODELE_ANALYSTE, sous la forme « workersai:@cf/… ». Un autre préfixe est
 * refusé : brancher un fournisseur payant doit être une décision, pas un
 * changement de variable.
 */

// Neurones par million de tokens, relevés le 2026-10-11 sur
// https://developers.cloudflare.com/workers-ai/platform/pricing/ .
// Un modèle absent de la table est compté au tarif le plus cher : mieux vaut
// surestimer la consommation que franchir l'enveloppe gratuite sans le voir.
export const TARIFS = {
  "@cf/qwen/qwen3-30b-a3b-fp8": { entree: 4625, sortie: 30475 },
  "@cf/meta/llama-3.3-70b-instruct-fp8-fast": { entree: 26668, sortie: 204805 },
  "@cf/meta/llama-3.1-8b-instruct-fp8-fast": { entree: 4119, sortie: 34868 },
  "@cf/openai/gpt-oss-120b": { entree: 31818, sortie: 68182 },
  "@cf/openai/gpt-oss-20b": { entree: 18182, sortie: 27273 },
  "@cf/google/gemma-4-26b-a4b-it": { entree: 9091, sortie: 27273 },
  "@cf/mistralai/mistral-small-3.1-24b-instruct": { entree: 31876, sortie: 50488 },
};
const TARIF_PRUDENT = { entree: 45170, sortie: 443756 };

// Modèles auxquels on passe `response_format` : ceux que la documentation
// « JSON Mode » liste au 2026-09-14, plus Qwen 3, dont le schéma d'entrée
// l'accepte. Pour les autres, on extrait le premier objet JSON de la réponse.
const FORMAT_JSON = new Set([
  "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
  "@cf/meta/llama-3.1-8b-instruct",
  "@cf/meta/llama-3-8b-instruct",
  "@cf/qwen/qwen3-30b-a3b-fp8",
]);

export const MODELES_PAR_DEFAUT = {
  traducteur: "workersai:@cf/qwen/qwen3-30b-a3b-fp8",
  analyste: "workersai:@cf/meta/llama-3.3-70b-instruct-fp8-fast",
};

export class ErreurFournisseur extends Error {
  constructor(code, message, statut) {
    super(message);
    this.code = code;       // configuration | plafond | indisponible | traduction
    this.statut = statut;   // statut HTTP à rendre à la page
  }
}

export function lireModele(valeur) {
  const brut = String(valeur || "").trim();
  const [prefixe, ...reste] = brut.split(":");
  const nom = reste.join(":");
  if (prefixe !== "workersai" || !nom.startsWith("@cf/") && !nom.startsWith("@hf/")) {
    throw new ErreurFournisseur("configuration",
      `Modèle « ${brut} » refusé : seul Workers AI (gratuit) est branché.`, 503);
  }
  return nom;
}

export function neurones(nom, usage) {
  const t = TARIFS[nom] || TARIF_PRUDENT;
  return Math.ceil(((usage.entree || 0) * t.entree + (usage.sortie || 0) * t.sortie) / 1e6);
}

// Le raisonnement de Qwen 3 ou de gpt-oss n'a rien à faire dans la réponse.
export function sansReflexion(texte) {
  return String(texte || "")
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/^[\s\S]*?<\/think>/i, "")
    .trim();
}

// Premier objet JSON équilibré du texte, chaînes comprises.
export function extraireObjet(texte) {
  const s = sansReflexion(texte).replace(/^```(?:json)?\s*|\s*```$/g, "");
  try { return JSON.parse(s); } catch { /* on cherche un bloc */ }
  const debut = s.indexOf("{");
  if (debut < 0) return null;
  let profondeur = 0, chaine = false, echappe = false;
  for (let i = debut; i < s.length; i++) {
    const c = s[i];
    if (chaine) {
      if (echappe) echappe = false;
      else if (c === "\\") echappe = true;
      else if (c === '"') chaine = false;
      continue;
    }
    if (c === '"') chaine = true;
    else if (c === "{") profondeur++;
    else if (c === "}" && --profondeur === 0) {
      try { return JSON.parse(s.slice(debut, i + 1)); } catch { return null; }
    }
  }
  return null;
}

// Deux formes de réponse coexistent : `response` (Llama), éventuellement déjà
// un objet en mode JSON ; `choices` à la OpenAI (Qwen 3, gpt-oss, Gemma).
function lireReponse(r) {
  if (r && r.response != null) {
    return typeof r.response === "string"
      ? { texte: r.response, json: null }
      : { texte: JSON.stringify(r.response), json: r.response };
  }
  const message = r && r.choices && r.choices[0] && r.choices[0].message;
  return { texte: message && typeof message.content === "string" ? message.content : "", json: null };
}

function lireUsage(r) {
  const u = (r && r.usage) || {};
  return { entree: u.prompt_tokens || 0, sortie: u.completion_tokens || 0 };
}

const attendre = (ms) => new Promise((ok) => setTimeout(ok, ms));

// Erreurs de la liaison Workers AI : « 4006 » et consorts signalent
// l'enveloppe gratuite épuisée ; « 3040 », « 3007 », un 5xx, une saturation
// passagère qu'un second essai suffit souvent à passer.
function classer(err) {
  const m = String((err && err.message) || err);
  if (/4006|neuron|allocation|daily limit|quota/i.test(m)) return "plafond";
  if (/3040|3007|capacity|timeout|timed out|overloaded|\b5\d\d\b|network/i.test(m)) return "passager";
  if (/json mode|response_format|5006|schema/i.test(m)) return "format";
  return "autre";
}

/**
 * Un appel au modèle. Rend { texte, json, usage, neurones, modele, duree }.
 * `json` est l'objet extrait de la réponse, ou null s'il n'y en a pas : la
 * validation contre le schéma appartient à l'appelant.
 */
export async function appeler(env, { modele, systeme, utilisateur, schemaSortie, maxTokens, temperature }) {
  if (!env || !env.AI || typeof env.AI.run !== "function") {
    throw new ErreurFournisseur("configuration", "Liaison Workers AI absente (binding AI).", 503);
  }
  const nom = lireModele(modele);
  const qwen = /qwen3/i.test(nom);
  const corps = {
    messages: [
      { role: "system", content: systeme },
      // « /no_think » coupe le raisonnement de Qwen 3 : il ne sert pas à
      // traduire une question, et ses tokens se paient en neurones.
      { role: "user", content: qwen ? utilisateur + "\n/no_think" : utilisateur },
    ],
    max_tokens: maxTokens,
    temperature: temperature == null ? 0.1 : temperature,
  };
  let avecFormat = Boolean(schemaSortie) && FORMAT_JSON.has(nom);
  if (avecFormat) corps.response_format = { type: "json_schema", json_schema: schemaSortie };

  const debut = Date.now();
  let r = null;
  for (let essai = 0; essai < 3 && r == null; essai++) {
    try {
      r = await env.AI.run(nom, corps);
    } catch (err) {
      const nature = classer(err);
      if (nature === "plafond") {
        throw new ErreurFournisseur("plafond", "Enveloppe gratuite Workers AI épuisée pour aujourd'hui.", 503);
      }
      if (nature === "format" && avecFormat) {
        // Le décodage contraint n'a pas tenu : on redemande en texte libre.
        avecFormat = false;
        delete corps.response_format;
        continue;
      }
      if (nature === "passager" && essai === 0) { await attendre(1500); continue; }
      throw new ErreurFournisseur("indisponible", "Workers AI ne répond pas : " + String(err && err.message || err).slice(0, 160), 502);
    }
  }
  if (r == null) throw new ErreurFournisseur("indisponible", "Workers AI ne répond pas.", 502);

  const { texte, json } = lireReponse(r);
  const usage = lireUsage(r);
  return {
    texte: sansReflexion(texte),
    json: json || extraireObjet(texte),
    usage: usage,
    neurones: neurones(nom, usage),
    modele: nom,
    duree: Date.now() - debut,
  };
}
