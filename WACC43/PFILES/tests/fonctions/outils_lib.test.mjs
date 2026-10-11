/*
 * Briques sans réseau : validation de schéma, extraction du JSON d'une
 * réponse de modèle, normalisation de la clé de cache, décompte des neurones.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { valider } from "../../agent/schema.js";
import { extraireObjet, sansReflexion, neurones, lireModele } from "../../agent/fournisseurs.js";
import { normaliser } from "../../agent/garde.js";
import { REPONSE_TRADUCTEUR, REQUETE } from "../../agent/schemas.js";

test("le schéma strict refuse une propriété non prévue", () => {
  const v = valider(REQUETE, { source: "pays", inconnu: 1 });
  assert.equal(v.ok, false);
  assert.match(v.erreurs[0], /inconnu : propriété non prévue/);
});

test("oneOf ne retient qu'une variante", () => {
  assert.equal(valider(REPONSE_TRADUCTEUR, { source: "pays" }).ok, true);
  assert.equal(valider(REPONSE_TRADUCTEUR, { source: "clarification", reformulation: "A ou B ?" }).ok, true);
  assert.equal(valider(REPONSE_TRADUCTEUR, { source: "meteo" }).ok, false);
});

test("les bornes de valeur et de longueur sont appliquées", () => {
  assert.equal(valider(REQUETE, { source: "pays", limite: 0 }).ok, false);
  assert.equal(valider(REQUETE, { source: "pays", limite: 201 }).ok, false);
  assert.equal(valider(REQUETE, { source: "pays", champs: ["x".repeat(41)] }).ok, false);
});

test("le JSON se retrouve derrière un raisonnement, une clôture ou du texte", () => {
  assert.deepEqual(extraireObjet('<think>long</think>{"a":1}'), { a: 1 });
  assert.deepEqual(extraireObjet('```json\n{"a":2}\n```'), { a: 2 });
  assert.deepEqual(extraireObjet('Voici : {"a":"une } dans la chaîne","b":{"c":3}} et la suite'),
    { a: "une } dans la chaîne", b: { c: 3 } });
  assert.equal(extraireObjet("rien ici"), null);
  assert.equal(sansReflexion("fin de réflexion</think>réponse"), "réponse");
});

test("la clé de cache ignore la casse, les espaces et l'ordre des clés", () => {
  assert.deepEqual(normaliser({ b: " Taux  d'IS ", a: 1 }), normaliser({ a: 1, b: "taux d'is" }));
});

test("les neurones suivent le tarif du modèle, au plus cher s'il est inconnu", () => {
  // 1 800 tokens d'entrée et 120 de sortie sur Qwen 3 30B : 8,33 + 3,66 = 11,99, arrondi à 12.
  assert.equal(neurones("@cf/qwen/qwen3-30b-a3b-fp8", { entree: 1800, sortie: 120 }), 12);
  assert.ok(neurones("@cf/inconnu/modele", { entree: 1800, sortie: 120 }) > 100);
});

test("seul le préfixe workersai est accepté", () => {
  assert.equal(lireModele("workersai:@cf/qwen/qwen3-30b-a3b-fp8"), "@cf/qwen/qwen3-30b-a3b-fp8");
  assert.throws(() => lireModele("openai-compatible:mistral-small"), /seul Workers AI/);
  assert.throws(() => lireModele("workersai:modele-sans-espace"), /seul Workers AI/);
});
