/*
 * POST /api/ask — niveau 1 : une question en français devient une requête
 * structurée, que la page exécute sur ses propres données.
 *
 * Le serveur ne voit jamais les données de la page, et n'exécute rien : il
 * traduit. La réponse du modèle est validée contre le contrat de requête
 * avant de partir ; une réponse invalide est redemandée une fois, puis
 * refusée avec le code « traduction ».
 */

import { proteger, lireCorps, reponseJson, reglages } from "../../agent/garde.js";
import { appeler, MODELES_PAR_DEFAUT, ErreurFournisseur } from "../../agent/fournisseurs.js";
import { SYSTEME_TRADUCTEUR } from "../../agent/instructions.js";
import { QUESTION, REPONSE_TRADUCTEUR, FORMAT_TRADUCTEUR } from "../../agent/schemas.js";
import { valider } from "../../agent/schema.js";

// Les champs laissés à null par le modèle sont retirés : le contrat les
// tient pour absents, et le schéma strict n'accepte pas tous les null.
function nettoyer(objet) {
  if (Array.isArray(objet)) return objet.map(nettoyer);
  if (!objet || typeof objet !== "object") return objet;
  const sortie = {};
  for (const [cle, v] of Object.entries(objet)) {
    if (v === null || v === undefined) continue;
    if (Array.isArray(v) && !v.length && cle !== "requetes") continue;
    sortie[cle] = nettoyer(v);
  }
  return sortie;
}

function messageUtilisateur(question, contexte) {
  const lignes = ["Question : " + question];
  if (contexte && Object.keys(contexte).length) {
    lignes.push("Contexte de l'écran : " + JSON.stringify(contexte));
  } else {
    lignes.push("Contexte de l'écran : aucun");
  }
  return lignes.join("\n");
}

export async function traduire(env, question, contexte) {
  const modele = env.MODELE_TRADUCTEUR || MODELES_PAR_DEFAUT.traducteur;
  let dernier = null, neurones = 0, usage = { entree: 0, sortie: 0 }, duree = 0, nom = null;
  for (let essai = 0; essai < 2; essai++) {
    const r = await appeler(env, {
      modele: modele,
      systeme: SYSTEME_TRADUCTEUR,
      utilisateur: messageUtilisateur(question, contexte),
      schemaSortie: FORMAT_TRADUCTEUR,
      maxTokens: 1024,
      temperature: essai ? 0 : 0.1,
    });
    neurones += r.neurones;
    usage = { entree: usage.entree + r.usage.entree, sortie: usage.sortie + r.usage.sortie };
    duree += r.duree;
    nom = r.modele;
    const requete = r.json ? nettoyer(r.json) : null;
    const v = requete ? valider(REPONSE_TRADUCTEUR, requete) : { ok: false, erreurs: ["aucun JSON"] };
    if (v.ok) {
      return { corps: { ok: true, requete: requete, modele: nom }, neurones, usage, duree, modele: nom };
    }
    dernier = v.erreurs.slice(0, 4).join(" ; ");
  }
  const err = new ErreurFournisseur("traduction",
    "Le traducteur n'a pas produit de requête valide (" + dernier + ").", 502);
  err.neurones = neurones;
  throw err;
}

export async function onRequestPost(contexte) {
  const lu = await lireCorps(contexte.request, 4096);
  if (lu.erreur) return lu.erreur;
  const v = valider(QUESTION, lu.corps);
  if (!v.ok) {
    return reponseJson({ ok: false, code: "invalide", message: "Question invalide : " + v.erreurs[0] }, 400);
  }
  const question = lu.corps.question.trim();
  const contexteEcran = lu.corps.contexte || null;
  return proteger(contexte, {
    route: "ask",
    corps: { question: question, contexte: contexteEcran },
    quota: reglages(contexte.env || {}).quotaQuestions,
    ttlCache: 7 * 24 * 3600,
    executer: () => traduire(contexte.env, question, contexteEcran),
  });
}
