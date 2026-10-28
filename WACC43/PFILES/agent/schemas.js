/*
 * Schémas des deux routes.
 *
 * Deux jeux par route : un schéma strict, qui valide ce qui entre et ce qui
 * sort (additionalProperties: false partout), et pour le modèle une forme
 * plus lâche, envoyée en `response_format`. Le décodage contraint de Workers
 * AI ne garantit pas les `oneOf` ; on lui demande donc l'enveloppe, et c'est
 * le schéma strict qui tranche ensuite.
 *
 * Le contrat de requête est le même que celui de la page (`executerRequete`) :
 * le serveur ne l'exécute jamais, il le produit.
 */

export const OPERATEURS = ["=", "!=", ">", ">=", "<", "<=", "contient", "dans"];
export const SOURCES = ["pays", "industries", "societes", "taux", "cmpc"];
const NOMBRE = { type: "number" };
const NOMBRE_NUL = { type: ["number", "null"] };
const TEXTE = (max) => ({ type: "string", maxLength: max });

const FILTRE = {
  type: "object",
  additionalProperties: false,
  required: ["champ", "op", "valeur"],
  properties: {
    champ: TEXTE(40),
    op: { enum: OPERATEURS },
    valeur: {
      type: ["string", "number", "boolean", "array"],
      maxLength: 120,
      maxItems: 40,
      items: { type: ["string", "number"], maxLength: 120 },
    },
  },
};

export const REQUETE = {
  type: "object",
  additionalProperties: false,
  required: ["source"],
  properties: {
    source: { enum: SOURCES },
    filtres: { type: ["array", "null"], items: FILTRE, maxItems: 8 },
    tri: {
      type: ["object", "null"],
      additionalProperties: false,
      required: ["champ", "sens"],
      properties: { champ: TEXTE(40), sens: { enum: ["asc", "desc"] } },
    },
    limite: { type: ["integer", "null"], minimum: 1, maximum: 200 },
    champs: { type: ["array", "null"], items: TEXTE(40), maxItems: 20 },
    agregat: {
      type: ["object", "null"],
      additionalProperties: false,
      required: ["fonction", "champ"],
      properties: {
        fonction: { enum: ["mediane", "moyenne", "min", "max", "compte"] },
        champ: TEXTE(40),
      },
    },
    parametres: {
      type: ["object", "null"],
      additionalProperties: false,
      properties: {
        annee: { type: ["integer", "string"], maxLength: 12 },
        maturite: { enum: ["10Y", "30Y"] },
        referentiel: { enum: ["damodaran", "comparables", "Damodaran", "Comparables"] },
        pays: TEXTE(80),
        industrie: TEXTE(80),
        prime_taille: NOMBRE,
        prime_specifique: NOMBRE,
        inflation_ref: NOMBRE,
        inflation_locale: NOMBRE,
      },
    },
    reformulation: TEXTE(300),
  },
};

// Les trois réponses qui ne sont pas une requête simple.
const COMPARAISON = {
  type: "object",
  additionalProperties: false,
  required: ["source", "requetes"],
  properties: {
    source: { const: "comparaison" },
    requetes: { type: "array", items: REQUETE, minItems: 2, maxItems: 4 },
    reformulation: TEXTE(300),
  },
};
const MESSAGE = (source) => ({
  type: "object",
  additionalProperties: false,
  required: ["source", "reformulation"],
  properties: { source: { const: source }, reformulation: TEXTE(300) },
});

// HARES : des opérations sur l'échantillon de travail de la page, appliquées
// à la suite des précédentes. Même contrat que `executerOperations` côté page.
export const OPERATIONS_ECHANTILLON = ["filtrer", "trier", "limiter", "statistiques", "aberrantes", "retirer", "garder", "selectionner", "repartir"];
export const OPERATEURS_ECHANTILLON = OPERATEURS.concat(["entre", "hors"]);
const OPERATION = {
  type: "object",
  additionalProperties: false,
  required: ["type"],
  properties: {
    type: { enum: OPERATIONS_ECHANTILLON },
    champ: TEXTE(40),
    op: { enum: OPERATEURS_ECHANTILLON },
    valeur: {
      type: ["string", "number", "array"],
      maxLength: 120,
      maxItems: 40,
      items: { type: ["string", "number"], maxLength: 120 },
    },
    sens: { enum: ["asc", "desc"] },
    nombre: { type: "integer", minimum: 1, maximum: 1000 },
    champs: { type: "array", items: TEXTE(40), maxItems: 6 },
    noms: { type: "array", items: TEXTE(120), maxItems: 40 },
    depart: { enum: ["depart", "base", "comparables"] },
  },
};
const ECHANTILLON = {
  type: "object",
  additionalProperties: false,
  required: ["source", "operations"],
  properties: {
    source: { const: "echantillon" },
    operations: { type: "array", items: OPERATION, minItems: 1, maxItems: 8 },
    reformulation: TEXTE(300),
  },
};

export const REPONSE_TRADUCTEUR = {
  oneOf: [REQUETE, COMPARAISON, ECHANTILLON, MESSAGE("hors_perimetre"), MESSAGE("clarification")],
};

// Forme demandée au modèle : l'enveloppe seulement, sans oneOf.
export const FORMAT_TRADUCTEUR = {
  type: "object",
  properties: {
    source: { type: "string", enum: SOURCES.concat(["comparaison", "echantillon", "hors_perimetre", "clarification"]) },
    operations: { type: "array", items: { type: "object" } },
    filtres: { type: "array", items: { type: "object" } },
    tri: { type: "object" },
    limite: { type: "integer" },
    champs: { type: "array", items: { type: "string" } },
    agregat: { type: "object" },
    parametres: { type: "object" },
    requetes: { type: "array", items: { type: "object" } },
    reformulation: { type: "string" },
  },
  required: ["source", "reformulation"],
};

export const QUESTION = {
  type: "object",
  additionalProperties: false,
  required: ["question"],
  properties: {
    question: { type: "string", minLength: 2, maxLength: 400 },
    contexte: {
      type: ["object", "null"],
      additionalProperties: false,
      properties: {
        annee: { type: ["integer", "string"], maxLength: 12 },
        maturite: { enum: ["10Y", "30Y"] },
        referentiel: { enum: ["damodaran", "comparables"] },
        pays: TEXTE(80),
        industrie: TEXTE(80),
        secteur: TEXTE(80),
        continent: TEXTE(40),
        zone: { type: ["string", "null"], maxLength: 60 },
        // L'état de l'échantillon de HARES, jamais ses sociétés.
        echantillon: {
          type: ["object", "null"],
          additionalProperties: false,
          properties: {
            n: { type: "integer", minimum: 0 },
            depart: TEXTE(160),
            etapes: { type: "array", items: TEXTE(160), maxItems: 12 },
          },
        },
      },
    },
  },
};

/* ---- Prévision ---- */

const SERIE = (max) => ({ type: "array", items: NOMBRE_NUL, maxItems: max });
const BORNE = { type: "array", items: NOMBRE, minItems: 2, maxItems: 2 };

export const DOSSIER = {
  type: "object",
  additionalProperties: false,
  required: ["societe", "historique", "normalise", "macro", "defauts", "regles", "bornes"],
  properties: {
    societe: {
      type: "object",
      additionalProperties: false,
      required: ["pays", "industrie"],
      properties: { pays: TEXTE(80), industrie: TEXTE(80), activite: TEXTE(300) },
    },
    historique: {
      type: "object",
      additionalProperties: false,
      required: ["annees", "ca", "ebitda"],
      properties: {
        annees: { type: "array", items: { type: "integer" }, maxItems: 12 },
        ca: SERIE(12), ebitda: SERIE(12), da: SERIE(12), capex: SERIE(12), bfr: SERIE(12),
        dette_nette: NOMBRE_NUL,
      },
    },
    normalise: {
      type: "object",
      additionalProperties: false,
      properties: {
        marge_ebitda_3ans: NOMBRE_NUL, croissance_tcam: NOMBRE_NUL,
        da_sur_ca: NOMBRE_NUL, bfr_sur_ca: NOMBRE_NUL,
        anomalies: { type: "array", items: TEXTE(240), maxItems: 12 },
      },
    },
    secteur: {
      type: ["object", "null"],
      additionalProperties: false,
      properties: {
        nom: TEXTE(80), n: { type: "integer", minimum: 0 },
        marge_mediane: NOMBRE_NUL, marge_tendance_pts_an: NOMBRE_NUL,
        croissance_mediane: NOMBRE_NUL, beta_median: NOMBRE_NUL,
      },
    },
    macro: {
      type: "object",
      additionalProperties: false,
      required: ["inflation_locale", "taux_is"],
      properties: { inflation_locale: NOMBRE, inflation_ref: NOMBRE, cmpc_local: NOMBRE_NUL, taux_is: NOMBRE },
    },
    defauts: {
      type: "object",
      additionalProperties: false,
      properties: {
        croissance: SERIE(10), marge: NOMBRE, da: NOMBRE, capex: SERIE(10), bfr: NOMBRE, g: NOMBRE,
      },
    },
    regles: {
      type: "object",
      additionalProperties: false,
      required: ["croissance", "marge", "g", "capex_sur_da"],
      properties: {
        croissance: { type: "array", items: NOMBRE, minItems: 3, maxItems: 10 },
        marge: { type: "array", items: NOMBRE, minItems: 3, maxItems: 10 },
        g: NOMBRE,
        capex_sur_da: { type: "array", items: NOMBRE, minItems: 3, maxItems: 10 },
        da_sur_ca: NOMBRE,
        bfr_sur_ca: NOMBRE,
      },
    },
    bornes: {
      type: "object",
      additionalProperties: false,
      properties: {
        croissance: BORNE, marge: BORNE, g: BORNE, capex_sur_da: BORNE, bfr_sur_ca: BORNE, da_sur_ca: BORNE,
      },
    },
  },
};

// Ce que l'analyste doit rendre. Les longueurs de tableaux sont contrôlées
// à part, contre l'horizon du dossier.
export const ANALYSE = {
  type: "object",
  additionalProperties: false,
  required: ["hypotheses", "justifications", "alertes", "confiance", "resume"],
  properties: {
    hypotheses: {
      type: "object",
      additionalProperties: false,
      required: ["croissance", "marge", "da_sur_ca", "capex_sur_da", "bfr_sur_ca", "g"],
      properties: {
        croissance: { type: "array", items: NOMBRE, minItems: 3, maxItems: 10 },
        marge: { type: "array", items: NOMBRE, minItems: 3, maxItems: 10 },
        da_sur_ca: NOMBRE,
        capex_sur_da: { type: "array", items: NOMBRE, minItems: 3, maxItems: 10 },
        bfr_sur_ca: NOMBRE,
        g: NOMBRE,
      },
    },
    justifications: {
      type: "object",
      additionalProperties: false,
      required: ["croissance", "marge", "capex", "bfr", "g"],
      properties: {
        croissance: TEXTE(600), marge: TEXTE(600), capex: TEXTE(600), bfr: TEXTE(600), g: TEXTE(600),
      },
    },
    alertes: { type: "array", items: TEXTE(300), maxItems: 12 },
    confiance: { enum: ["faible", "moyenne", "bonne"] },
    resume: TEXTE(700),
  },
};

export const FORMAT_ANALYSTE = {
  type: "object",
  properties: {
    hypotheses: {
      type: "object",
      properties: {
        croissance: { type: "array", items: { type: "number" } },
        marge: { type: "array", items: { type: "number" } },
        da_sur_ca: { type: "number" },
        capex_sur_da: { type: "array", items: { type: "number" } },
        bfr_sur_ca: { type: "number" },
        g: { type: "number" },
      },
      required: ["croissance", "marge", "da_sur_ca", "capex_sur_da", "bfr_sur_ca", "g"],
    },
    justifications: {
      type: "object",
      properties: {
        croissance: { type: "string" }, marge: { type: "string" }, capex: { type: "string" },
        bfr: { type: "string" }, g: { type: "string" },
      },
      required: ["croissance", "marge", "capex", "bfr", "g"],
    },
    alertes: { type: "array", items: { type: "string" } },
    confiance: { type: "string", enum: ["faible", "moyenne", "bonne"] },
    resume: { type: "string" },
  },
  required: ["hypotheses", "justifications", "alertes", "confiance", "resume"],
};

// Bornes appliquées par le serveur quoi que le dossier annonce : une page
// modifiée ne doit pas pouvoir élargir ce que l'analyste a le droit de rendre.
export const BORNES_MAX = {
  croissance: [-0.2, 0.3],
  marge: [0, 0.6],
  g: [0, 0.04],
  capex_sur_da: [0.8, 2.5],
  bfr_sur_ca: [-0.2, 0.5],
  da_sur_ca: [0, 0.3],
};
