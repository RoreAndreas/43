/*
 * Validation de schéma JSON, sans dépendance.
 *
 * Le modèle de langage n'est jamais cru sur parole : tout ce qu'il renvoie
 * passe par ici avant de quitter le serveur, et la page revalide à l'arrivée.
 * Ce validateur couvre le sous-ensemble de JSON Schema dont les routes ont
 * besoin — type, enum, const, properties, required, additionalProperties,
 * items, bornes de longueur et de valeur, oneOf — et rien d'autre : une
 * bibliothèque complète pèserait plus lourd que tout le reste de la fonction.
 */

const TYPES = {
  string: (v) => typeof v === "string",
  number: (v) => typeof v === "number" && Number.isFinite(v),
  integer: (v) => Number.isInteger(v),
  boolean: (v) => typeof v === "boolean",
  object: (v) => v !== null && typeof v === "object" && !Array.isArray(v),
  array: (v) => Array.isArray(v),
  null: (v) => v === null,
};

function verifier(schema, valeur, chemin, erreurs) {
  if (schema === true || schema == null) return;
  if (schema === false) { erreurs.push(`${chemin} : valeur interdite`); return; }

  if (schema.oneOf) {
    const passent = schema.oneOf.filter((s) => {
      const e = [];
      verifier(s, valeur, chemin, e);
      return e.length === 0;
    });
    if (passent.length !== 1) {
      erreurs.push(`${chemin} : ${passent.length ? "plusieurs" : "aucune"} des variantes attendues`);
    }
    return;
  }

  if (schema.type !== undefined) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some((t) => TYPES[t] && TYPES[t](valeur))) {
      erreurs.push(`${chemin} : ${types.join(" ou ")} attendu`);
      return;
    }
  }
  if (schema.const !== undefined && valeur !== schema.const) {
    erreurs.push(`${chemin} : ${JSON.stringify(schema.const)} attendu`);
  }
  if (schema.enum && !schema.enum.includes(valeur)) {
    erreurs.push(`${chemin} : valeur hors liste (${JSON.stringify(valeur)})`);
  }

  if (typeof valeur === "string") {
    if (schema.minLength != null && valeur.length < schema.minLength) erreurs.push(`${chemin} : trop court`);
    if (schema.maxLength != null && valeur.length > schema.maxLength) erreurs.push(`${chemin} : trop long`);
  }
  if (typeof valeur === "number") {
    if (schema.minimum != null && valeur < schema.minimum) erreurs.push(`${chemin} : inférieur à ${schema.minimum}`);
    if (schema.maximum != null && valeur > schema.maximum) erreurs.push(`${chemin} : supérieur à ${schema.maximum}`);
  }

  if (Array.isArray(valeur)) {
    if (schema.minItems != null && valeur.length < schema.minItems) erreurs.push(`${chemin} : au moins ${schema.minItems} éléments`);
    if (schema.maxItems != null && valeur.length > schema.maxItems) erreurs.push(`${chemin} : au plus ${schema.maxItems} éléments`);
    if (schema.items) valeur.forEach((v, i) => verifier(schema.items, v, `${chemin}[${i}]`, erreurs));
  }

  if (TYPES.object(valeur)) {
    const proprietes = schema.properties || {};
    for (const cle of schema.required || []) {
      if (!(cle in valeur)) erreurs.push(`${chemin}.${cle} : manquant`);
    }
    for (const [cle, v] of Object.entries(valeur)) {
      if (cle in proprietes) verifier(proprietes[cle], v, `${chemin}.${cle}`, erreurs);
      else if (schema.additionalProperties === false) erreurs.push(`${chemin}.${cle} : propriété non prévue`);
      else if (typeof schema.additionalProperties === "object") {
        verifier(schema.additionalProperties, v, `${chemin}.${cle}`, erreurs);
      }
    }
  }
}

/** Rend { ok, erreurs } ; `erreurs` liste les écarts avec leur chemin. */
export function valider(schema, valeur) {
  const erreurs = [];
  verifier(schema, valeur, "$", erreurs);
  return { ok: erreurs.length === 0, erreurs };
}
