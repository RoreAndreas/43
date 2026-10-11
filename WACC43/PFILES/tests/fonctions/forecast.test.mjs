/*
 * Route /api/forecast : forme, horizon, bornes. L'analyste peut se tromper ;
 * ce qui sort du serveur, lui, tient toujours dans les bornes de l'outil.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { onRequestPost, bornesEffectives, borner } from "../../functions/api/forecast.js";
import { AiScripte, analyse, contexte, dossier, environnement, reponseLlama } from "./outils.mjs";

const appel = async (env, corps = dossier(), options) => {
  const r = await onRequestPost(contexte("/api/forecast", corps, env, options));
  return { statut: r.status, corps: await r.json() };
};

test("une analyse valide est rendue telle quelle", async () => {
  const ai = new AiScripte([reponseLlama(analyse())]);
  const r = await appel(environnement({ AI: ai }));
  assert.equal(r.statut, 200);
  assert.equal(r.corps.ok, true);
  assert.deepEqual(r.corps.analyse.hypotheses.croissance, [0.07, 0.07, 0.07, 0.07, 0.07]);
  assert.equal(r.corps.analyse.alertes.length, 0);
  assert.equal(ai.appels[0].modele, "@cf/meta/llama-3.3-70b-instruct-fp8-fast");
  assert.equal(ai.appels[0].corps.response_format.type, "json_schema");
});

test("une valeur hors bornes est ramenée à la borne et signalée", async () => {
  const fautive = analyse(5);
  fautive.hypotheses.g = 0.08;
  fautive.hypotheses.capex_sur_da = [3, 1.2, 1.2, 0.5, 1.2];
  const r = await appel(environnement({ AI: new AiScripte([reponseLlama(fautive)]) }));
  const h = r.corps.analyse.hypotheses;
  assert.equal(h.g, 0.04);
  assert.deepEqual(h.capex_sur_da, [2.5, 1.2, 1.2, 0.8, 1.2]);
  assert.equal(r.corps.analyse.alertes.length, 3);
  assert.match(r.corps.analyse.alertes.join(" "), /croissance à l'infini : 8 % ramené à 4 %/);
});

test("le dossier ne peut pas élargir les bornes du serveur", async () => {
  const d = dossier();
  d.bornes.g = [0, 0.2];
  d.bornes.marge = [-1, 2];
  const b = bornesEffectives(d);
  assert.deepEqual(b.g, [0, 0.04]);
  assert.deepEqual(b.marge, [0, 0.6]);
});

test("des tableaux à la mauvaise longueur sont redemandés, puis refusés", async () => {
  const courte = analyse(3);
  const ai = new AiScripte([reponseLlama(courte)]);
  const r = await appel(environnement({ AI: ai }), dossier(5));
  assert.equal(r.statut, 502);
  assert.equal(r.corps.code, "analyse");
  assert.equal(ai.appels.length, 2);
});

test("une réponse sans JSON, puis une valide : la seconde l'emporte", async () => {
  const ai = new AiScripte([{ response: "Voici mon analyse : la marge baisse." }, reponseLlama(analyse())]);
  const r = await appel(environnement({ AI: ai }));
  assert.equal(r.corps.ok, true);
  assert.equal(ai.appels.length, 2);
});

test("un dossier invalide est refusé avant tout appel", async () => {
  const ai = new AiScripte([]);
  const d = dossier();
  delete d.regles;
  let r = await appel(environnement({ AI: ai }), d);
  assert.equal(r.statut, 400);
  const incoherent = dossier(5);
  incoherent.regles.marge = [0.1, 0.1, 0.1];
  r = await appel(environnement({ AI: ai }), incoherent);
  assert.equal(r.statut, 400);
  const bavard = dossier();
  bavard.societe.activite = "x".repeat(301);
  r = await appel(environnement({ AI: ai }), bavard);
  assert.equal(r.statut, 400);
  assert.equal(ai.appels.length, 0);
});

test("la sixième prévision d'une même adresse reçoit 429", async () => {
  const env = environnement({ AI: new AiScripte([reponseLlama(analyse())]) });
  const statuts = [];
  for (let i = 0; i < 6; i++) {
    const d = dossier();
    d.historique.dette_nette = i;   // six dossiers distincts : pas de cache
    statuts.push((await appel(env, d, { cache: null })).statut);
  }
  assert.deepEqual(statuts, [200, 200, 200, 200, 200, 429]);
});

test("borner laisse intactes les valeurs dans les bornes", () => {
  const h = analyse().hypotheses;
  const b = borner(h, bornesEffectives(dossier()));
  assert.deepEqual(b.hypotheses, h);
  assert.equal(b.alertes.length, 0);
});
