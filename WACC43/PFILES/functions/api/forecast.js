/*
 * POST /api/forecast — niveau 2 : l'analyste relit un prévisionnel.
 *
 * La page prépare le dossier (historique normalisé, statistiques du secteur,
 * hypothèses par défaut et par règles, bornes) ; l'analyste renvoie des
 * hypothèses justifiées. Le serveur vérifie la forme, la longueur des
 * tableaux contre l'horizon, puis ramène toute valeur hors bornes à la borne
 * en le signalant dans les alertes. Les bornes appliquées sont l'intersection
 * de celles du dossier et de BORNES_MAX : une page modifiée ne les élargit pas.
 */

import { proteger, lireCorps, reponseJson, reglages } from "../../agent/garde.js";
import { appeler, MODELES_PAR_DEFAUT, ErreurFournisseur } from "../../agent/fournisseurs.js";
import { SYSTEME_ANALYSTE } from "../../agent/instructions.js";
import { DOSSIER, ANALYSE, FORMAT_ANALYSTE, BORNES_MAX } from "../../agent/schemas.js";
import { valider } from "../../agent/schema.js";

const LIBELLES = {
  croissance: "croissance du CA", marge: "marge d'EBITDA", g: "croissance à l'infini",
  capex_sur_da: "CapEx / D&A", bfr_sur_ca: "BFR / CA", da_sur_ca: "D&A / CA",
};

export function bornesEffectives(dossier) {
  const sortie = {};
  for (const [cle, [bas, haut]] of Object.entries(BORNES_MAX)) {
    const demande = (dossier.bornes || {})[cle];
    sortie[cle] = demande
      ? [Math.max(bas, Math.min(demande[0], demande[1])), Math.min(haut, Math.max(demande[0], demande[1]))]
      : [bas, haut];
    if (sortie[cle][0] > sortie[cle][1]) sortie[cle] = [bas, haut];
  }
  return sortie;
}

const pct = (x) => (Math.round(x * 1000) / 10).toString().replace(".", ",") + " %";
const fois = (x) => (Math.round(x * 100) / 100).toString().replace(".", ",") + "×";

// Ramène chaque valeur dans ses bornes ; rend les alertes des corrections.
export function borner(hypotheses, bornes) {
  const alertes = [];
  const format = (cle, x) => (cle === "capex_sur_da" ? fois(x) : pct(x));
  const une = (cle, x, an) => {
    const [bas, haut] = bornes[cle];
    if (x >= bas && x <= haut) return x;
    const y = x < bas ? bas : haut;
    alertes.push(`${LIBELLES[cle]}${an == null ? "" : " (année " + (an + 1) + ")"} : ${format(cle, x)} ramené à ${format(cle, y)}, borne de l'outil`);
    return y;
  };
  const h = {};
  for (const cle of ["croissance", "marge", "capex_sur_da"]) h[cle] = hypotheses[cle].map((x, t) => une(cle, x, t));
  for (const cle of ["g", "bfr_sur_ca", "da_sur_ca"]) h[cle] = une(cle, hypotheses[cle], null);
  return { hypotheses: h, alertes };
}

export async function analyser(env, dossier) {
  const modele = env.MODELE_ANALYSTE || MODELES_PAR_DEFAUT.analyste;
  const horizon = dossier.regles.croissance.length;
  const bornes = bornesEffectives(dossier);
  let dernier = null, neurones = 0, usage = { entree: 0, sortie: 0 }, duree = 0, nom = null;
  for (let essai = 0; essai < 2; essai++) {
    const r = await appeler(env, {
      modele: modele,
      systeme: SYSTEME_ANALYSTE,
      utilisateur: "Dossier :\n" + JSON.stringify(Object.assign({}, dossier, { bornes: bornes })),
      schemaSortie: FORMAT_ANALYSTE,
      maxTokens: 4096,
      temperature: 0.2,
    });
    neurones += r.neurones;
    usage = { entree: usage.entree + r.usage.entree, sortie: usage.sortie + r.usage.sortie };
    duree += r.duree;
    nom = r.modele;
    const v = r.json ? valider(ANALYSE, r.json) : { ok: false, erreurs: ["aucun JSON"] };
    const longueurs = v.ok && ["croissance", "marge", "capex_sur_da"].every((k) => r.json.hypotheses[k].length === horizon);
    if (v.ok && longueurs) {
      const b = borner(r.json.hypotheses, bornes);
      const analyse = Object.assign({}, r.json, {
        hypotheses: b.hypotheses,
        alertes: r.json.alertes.concat(b.alertes).slice(0, 16),
      });
      return { corps: { ok: true, analyse: analyse, bornes: bornes, modele: nom }, neurones, usage, duree, modele: nom };
    }
    dernier = v.ok ? `tableaux de longueur différente de l'horizon (${horizon})` : v.erreurs.slice(0, 4).join(" ; ");
  }
  const err = new ErreurFournisseur("analyse", "L'analyste n'a pas rendu de réponse valide (" + dernier + ").", 502);
  err.neurones = neurones;
  throw err;
}

export async function onRequestPost(contexte) {
  const lu = await lireCorps(contexte.request, 32768);
  if (lu.erreur) return lu.erreur;
  const v = valider(DOSSIER, lu.corps);
  if (!v.ok) {
    return reponseJson({ ok: false, code: "invalide", message: "Dossier invalide : " + v.erreurs.slice(0, 3).join(" ; ") }, 400);
  }
  const dossier = lu.corps;
  const n = dossier.regles.croissance.length;
  if (dossier.regles.marge.length !== n || dossier.regles.capex_sur_da.length !== n) {
    return reponseJson({ ok: false, code: "invalide", message: "Dossier invalide : horizons incohérents dans les règles." }, 400);
  }
  return proteger(contexte, {
    route: "forecast",
    corps: dossier,
    quota: reglages(contexte.env || {}).quotaPrevisions,
    ttlCache: 24 * 3600,
    executer: () => analyser(contexte.env, dossier),
  });
}
