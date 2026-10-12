/*
 * Route /api/ask et ses garde-fous, avec les critères d'acceptation du
 * brief : la 41e question d'une même adresse reçoit 429, un plafond minuscule
 * déclenche 503 au second appel, une IP n'est jamais stockée en clair.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { onRequestPost } from "../../functions/api/ask.js";
import {
  AiScripte, CacheMemoire, IP, REQUETE_PAYS, contexte, environnement, reponseLlama, reponseQwen,
} from "./outils.mjs";

const QUESTION = { question: "Les 5 pays d'Afrique de l'Ouest à la plus forte prime de risque", contexte: { pays: "Benin" } };
const appel = async (env, corps = QUESTION, options) => {
  const r = await onRequestPost(contexte("/api/ask", corps, env, options));
  return { statut: r.status, corps: await r.json() };
};

test("une réponse Qwen, raisonnement compris, devient une requête validée", async () => {
  const env = environnement({ AI: new AiScripte([reponseQwen("<think>hmm</think>\n" + JSON.stringify(REQUETE_PAYS))]) });
  const r = await appel(env);
  assert.equal(r.statut, 200);
  assert.equal(r.corps.ok, true);
  assert.equal(r.corps.requete.source, "pays");
  // Les champs nuls sont retirés : le contrat les tient pour absents.
  assert.equal("agregat" in r.corps.requete, false);
  assert.equal(r.corps.modele, "@cf/qwen/qwen3-30b-a3b-fp8");
});

test("Qwen reçoit /no_think et le schéma de sortie", async () => {
  const ai = new AiScripte([reponseQwen(JSON.stringify(REQUETE_PAYS))]);
  await appel(environnement({ AI: ai }));
  const corps = ai.appels[0].corps;
  assert.match(corps.messages[1].content, /\/no_think$/);
  assert.equal(corps.response_format.type, "json_schema");
});

test("une réponse Llama en mode JSON, déjà un objet, est acceptée", async () => {
  const env = environnement({
    MODELE_TRADUCTEUR: "workersai:@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    AI: new AiScripte([reponseLlama(REQUETE_PAYS)]),
  });
  const r = await appel(env);
  assert.equal(r.corps.ok, true);
  assert.equal(r.corps.modele, "@cf/meta/llama-3.3-70b-instruct-fp8-fast");
});

test("une comparaison et un hors-périmètre passent le schéma strict", async () => {
  const comparaison = {
    source: "comparaison",
    requetes: [
      { source: "pays", filtres: [{ champ: "nom", op: "=", valeur: "Ghana" }] },
      { source: "pays", filtres: [{ champ: "nom", op: "=", valeur: "Togo" }] },
    ],
    reformulation: "Ghana et Togo",
  };
  let r = await appel(environnement({ AI: new AiScripte([reponseQwen(JSON.stringify(comparaison))]) }));
  assert.equal(r.corps.requete.source, "comparaison");
  r = await appel(environnement({ AI: new AiScripte([reponseQwen('{"source":"hors_perimetre","reformulation":"Hors sujet."}')]) }));
  assert.equal(r.corps.requete.source, "hors_perimetre");
});

const ECHANTILLON = {
  source: "echantillon",
  operations: [
    { type: "filtrer", champ: "marge_ebitda", op: "entre", valeur: [0.2, 0.35] },
    { type: "trier", champ: "ca", sens: "desc" },
    { type: "statistiques", champs: ["ve_ebitda", "ve_ca", "pe"] },
  ],
  reformulation: "Marge entre 20 et 35 %, classées par CA, statistiques des multiples",
};
const CONTEXTE_HARES = { pays: "Benin", echantillon: { n: 23, depart: "23 sociétés — Telecommunication Services, Afrique", etapes: ["Groupes"] } };

test("HARES : des opérations sur l'échantillon passent le schéma strict", async () => {
  const ai = new AiScripte([reponseQwen(JSON.stringify(ECHANTILLON))]);
  const r = await appel(environnement({ AI: ai }), { question: "garde la marge entre 20 et 35 %", contexte: CONTEXTE_HARES });
  assert.equal(r.statut, 200);
  assert.equal(r.corps.requete.source, "echantillon");
  assert.deepEqual(r.corps.requete.operations[0].valeur, [0.2, 0.35]);
  // Le modèle reçoit l'état de l'échantillon, jamais ses sociétés.
  assert.match(ai.appels[0].corps.messages[1].content, /"echantillon":\{"n":23/);
});

test("HARES : une opération inventée est refusée", async () => {
  const fautive = Object.assign({}, ECHANTILLON, { operations: [{ type: "deviner", champ: "ca" }] });
  const ai = new AiScripte([reponseQwen(JSON.stringify(fautive))]);
  const r = await appel(environnement({ AI: ai }), { question: "fais quelque chose", contexte: CONTEXTE_HARES });
  assert.equal(r.statut, 502);
  assert.equal(r.corps.code, "traduction");
  assert.equal(ai.appels.length, 2);
});

test("HARES : un contexte d'échantillon mal formé est refusé avant tout appel", async () => {
  const ai = new AiScripte([]);
  const r = await appel(environnement({ AI: ai }), { question: "groupes", contexte: { echantillon: { n: 3, societes: ["Sonatel"] } } });
  assert.equal(r.statut, 400);
  assert.equal(ai.appels.length, 0);
});

test("une requête invalide est redemandée une fois, puis refusée", async () => {
  // Un opérateur inventé : le schéma strict doit le refuser.
  const fautive = Object.assign({}, REQUETE_PAYS, { filtres: [{ champ: "crp", op: "environ", valeur: 0.05 }] });
  const ai = new AiScripte([reponseQwen(JSON.stringify(fautive))]);
  const env = environnement({ AI: ai });
  const r = await appel(env);
  assert.equal(r.statut, 502);
  assert.equal(r.corps.code, "traduction");
  assert.equal(ai.appels.length, 2, "une seconde tentative, pas plus");
  // Les neurones des deux tentatives sont comptés malgré l'échec.
  const compta = JSON.parse(await env.GARDE.get(env.GARDE.cles().find((k) => k.startsWith("compta:"))));
  assert.ok(compta.neurones > 0);
});

test("un texte sans JSON est refusé avec le code « traduction »", async () => {
  const r = await appel(environnement({ AI: new AiScripte([reponseQwen("Désolé, je ne sais pas.")]) }));
  assert.equal(r.corps.code, "traduction");
});

test("la même question, autrement écrite, sort du cache sans appel ni quota", async () => {
  const ai = new AiScripte([reponseQwen(JSON.stringify(REQUETE_PAYS))]);
  const env = environnement({ AI: ai });
  const cache = new CacheMemoire();
  await appel(env, QUESTION, { cache });
  const r = await appel(env, { question: "  LES 5 pays d'Afrique   de l'Ouest à la plus forte prime de risque ", contexte: { pays: "benin" } }, { cache });
  assert.equal(r.corps.cache, true);
  assert.equal(ai.appels.length, 1);
  const quota = env.GARDE.cles().find((k) => k.startsWith("ip:"));
  assert.equal(await env.GARDE.get(quota), "1");
});

test("la 41e question d'une même adresse reçoit 429", async () => {
  const env = environnement({ AI: new AiScripte([reponseQwen(JSON.stringify(REQUETE_PAYS))]) });
  const statuts = [];
  for (let i = 1; i <= 45; i++) {
    const r = await appel(env, { question: "question numéro " + i }, { cache: null });
    statuts.push(r.statut);
    if (i === 41) {
      assert.equal(r.corps.code, "quota");
      assert.match(r.corps.reprise, /T00:00:00\.000Z$/);
    }
  }
  assert.deepEqual(statuts.slice(0, 40), Array(40).fill(200));
  assert.deepEqual(statuts.slice(40), Array(5).fill(429));
  // Une autre adresse n'est pas touchée.
  const autre = await appel(env, { question: "autre adresse" }, { cache: null, ip: "41.202.1.1" });
  assert.equal(autre.statut, 200);
});

test("un plafond minuscule déclenche 503 au second appel", async () => {
  const env = environnement({ PLAFOND_NEURONES_JOUR: "1", AI: new AiScripte([reponseQwen(JSON.stringify(REQUETE_PAYS))]) });
  const premier = await appel(env, { question: "première" }, { cache: null });
  const second = await appel(env, { question: "seconde" }, { cache: null });
  assert.equal(premier.statut, 200);
  assert.equal(second.statut, 503);
  assert.equal(second.corps.code, "plafond");
});

test("l'enveloppe gratuite épuisée chez Cloudflare rend 503 « plafond »", async () => {
  const env = environnement({ AI: new AiScripte([new Error("4006: you have used up your daily free allocation of 10,000 neurons")]) });
  const r = await appel(env);
  assert.equal(r.statut, 503);
  assert.equal(r.corps.code, "plafond");
  // Le plafond local s'aligne : l'appel suivant ne tente même plus Cloudflare.
  const suivant = await appel(env, { question: "encore une" }, { cache: null });
  assert.equal(suivant.corps.code, "plafond");
  assert.equal(env.AI.appels.length, 1);
});

test("une saturation passagère est réessayée une fois", async () => {
  const ai = new AiScripte((m, c, n) => (n === 0 ? new Error("3040: Capacity temporarily exceeded") : reponseQwen(JSON.stringify(REQUETE_PAYS))));
  const r = await appel(environnement({ AI: ai }));
  assert.equal(r.corps.ok, true);
  assert.equal(ai.appels.length, 2);
});

test("l'adresse IP n'est jamais stockée en clair", async () => {
  const env = environnement({ AI: new AiScripte([reponseQwen(JSON.stringify(REQUETE_PAYS))]) });
  await appel(env);
  for (const cle of env.GARDE.cles()) {
    assert.equal(cle.includes(IP), false, cle);
    assert.equal((await env.GARDE.get(cle)).includes(IP), false, cle);
  }
});

test("sans sel, sans KV ou sans Workers AI, la route refuse proprement", async () => {
  let r = await appel(environnement({ SEL_IP: "" }));
  assert.equal(r.statut, 503);
  assert.equal(r.corps.code, "configuration");
  r = await appel(environnement({ GARDE: undefined }));
  assert.equal(r.corps.code, "configuration");
  r = await appel(environnement({ AI: undefined }), { question: "sans liaison" }, { cache: null });
  assert.equal(r.corps.code, "configuration");
});

test("un modèle payant ne se branche pas par une variable", async () => {
  const r = await appel(environnement({ MODELE_TRADUCTEUR: "anthropic:claude-haiku-4-5" }));
  assert.equal(r.statut, 503);
  assert.equal(r.corps.code, "configuration");
});

test("une question vide ou trop longue est refusée avant tout appel", async () => {
  const ai = new AiScripte([]);
  let r = await appel(environnement({ AI: ai }), { question: "" });
  assert.equal(r.statut, 400);
  r = await appel(environnement({ AI: ai }), { question: "x".repeat(401) });
  assert.equal(r.statut, 400);
  r = await appel(environnement({ AI: ai }), "pas du json");
  assert.equal(r.statut, 400);
  assert.equal(ai.appels.length, 0);
});

test("quota et comptabilité tiennent en deux écritures KV par appel", async () => {
  const env = environnement({ AI: new AiScripte([reponseQwen(JSON.stringify(REQUETE_PAYS))]) });
  await appel(env, QUESTION, { cache: null });
  assert.equal(env.GARDE.ecritures, 2);
});
