/*
 * Garde-fous des routes de l'agent, exécutés dans cet ordre :
 *
 *   1. cache      réponse identique déjà servie : rendue sans appel ni quota ;
 *   2. quota IP   au-delà de N appels par jour et par adresse : 429 ;
 *   3. plafond    au-delà de N neurones consommés aujourd'hui : 503, la page
 *                 repasse sur ses gabarits et le dit ;
 *   4. appel      puis comptabilité et journal, dans une seule écriture ;
 *   5. cache      écriture de la réponse.
 *
 * Deux choix tiennent au plan gratuit de Cloudflare :
 *
 * - Le cache vit dans l'API Cache, pas dans KV. Workers KV n'offre que mille
 *   écritures par jour sur le plan gratuit ; y écrire aussi le cache en
 *   brûlerait une à chaque question. L'API Cache est gratuite et sans quota
 *   d'écriture — en contrepartie, elle est propre à chaque centre de données.
 * - Comptabilité et journal partagent une clé par jour (`compta:AAAA-MM-JJ`) :
 *   deux écritures KV par appel en tout, quota compris, soit cinq cents appels
 *   par jour avant de toucher la limite de KV. L'enveloppe de neurones est
 *   épuisée bien avant.
 *
 * Les compteurs KV sont lus puis réécrits : deux appels simultanés peuvent
 * perdre une incrémentation. Pour un quota et une estimation de dépense, c'est
 * acceptable ; le vrai verrou de dépense reste l'enveloppe de Workers AI.
 *
 * L'adresse IP n'est jamais stockée : seule son empreinte SHA-256, salée par
 * le secret SEL_IP, sert de clé. Sans sel, la route refuse de tourner — une
 * empreinte d'IPv4 non salée se retrouve par force brute en quelques minutes.
 */

const JOUR = 24 * 3600;

export function reponseJson(objet, statut = 200, entetes = {}) {
  return new Response(JSON.stringify(objet), {
    status: statut,
    headers: Object.assign({
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    }, entetes),
  });
}

async function sha256(texte) {
  const octets = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texte));
  return Array.from(new Uint8Array(octets), (b) => b.toString(16).padStart(2, "0")).join("");
}

// Clés triées, chaînes réduites aux espaces simples et en minuscules : « Taux
// d'IS du Sénégal » et « taux d'is du  sénégal » partagent leur réponse.
export function normaliser(valeur) {
  if (Array.isArray(valeur)) return valeur.map(normaliser);
  if (valeur && typeof valeur === "object") {
    const sortie = {};
    for (const cle of Object.keys(valeur).sort()) sortie[cle] = normaliser(valeur[cle]);
    return sortie;
  }
  if (typeof valeur === "string") return valeur.trim().replace(/\s+/g, " ").toLowerCase();
  return valeur;
}

const jourUtc = (d) => d.toISOString().slice(0, 10);
function repriseUtc(d) {
  const demain = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1));
  return demain.toISOString();
}

const entier = (v, defaut) => {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : defaut;
};

export function reglages(env) {
  return {
    quotaQuestions: entier(env.QUOTA_QUESTIONS_IP, 40),
    quotaPrevisions: entier(env.QUOTA_PREVISIONS_IP, 5),
    // 9 000 et non 10 000 : la marge couvre les incrémentations perdues et
    // l'écart entre l'estimation et le décompte réel de Cloudflare.
    plafondJour: entier(env.PLAFOND_NEURONES_JOUR, 9000),
  };
}

async function lireJson(kv, cle, defaut) {
  const brut = await kv.get(cle);
  if (!brut) return defaut;
  try { return JSON.parse(brut); } catch { return defaut; }
}

/**
 * Enveloppe une route. `executer()` fait l'appel au modèle et rend
 * { corps, neurones, modele, usage, duree } ; ce qui en sort est mis en cache.
 * Toute erreur portant `code` et `statut` est rendue telle quelle à la page.
 */
export async function proteger(contexte, { route, corps, quota, ttlCache, executer, maintenant }) {
  const { request, env } = contexte;
  const date = maintenant || new Date();
  if (!env || !env.GARDE || !env.SEL_IP) {
    return reponseJson({ ok: false, code: "configuration",
      message: "Assistant en ligne non configuré : liaison KV GARDE ou secret SEL_IP absent." }, 503);
  }

  // 1. Cache
  const empreinte = await sha256(route + "\n" + JSON.stringify(normaliser(corps)));
  const cache = contexte.cache !== undefined ? contexte.cache
    : (typeof caches !== "undefined" ? caches.default : null);
  const cleCache = new Request(new URL("/__cache/" + route + "/" + empreinte, request.url).toString());
  if (cache) {
    const garde = await cache.match(cleCache);
    if (garde) {
      const objet = await garde.json();
      return reponseJson(Object.assign(objet, { cache: true }));
    }
  }

  // 2. Quota par IP
  const ip = request.headers.get("CF-Connecting-IP") || request.headers.get("x-forwarded-for") || "inconnue";
  const cleIp = "ip:" + (await sha256(env.SEL_IP + "|" + ip)).slice(0, 32) + ":" + route + ":" + jourUtc(date);
  const deja = entier(await env.GARDE.get(cleIp), 0);
  if (deja >= quota) {
    return reponseJson({ ok: false, code: "quota", reprise: repriseUtc(date),
      message: `Quota de ${quota} appels par jour atteint pour cette adresse.` }, 429);
  }

  // 3. Plafond global
  const cleCompta = "compta:" + jourUtc(date);
  const compta = await lireJson(env.GARDE, cleCompta, { neurones: 0, appels: {}, journal: [] });
  const { plafondJour } = reglages(env);
  if (compta.neurones >= plafondJour) {
    return reponseJson({ ok: false, code: "plafond",
      message: "Enveloppe gratuite du jour consommée : l'assistant répond par ses gabarits jusqu'à minuit UTC." }, 503);
  }

  // Le quota compte la tentative, réussie ou non : sans quoi des requêtes qui
  // échouent exprès consommeraient des neurones sans jamais être limitées.
  await env.GARDE.put(cleIp, String(deja + 1), { expirationTtl: 2 * JOUR });

  // 4. Appel, comptabilité et journal
  let resultat;
  try {
    resultat = await executer();
  } catch (err) {
    // Un échec du modèle a pu consommer des neurones : ils se comptent aussi.
    const consommes = (err && err.neurones) || 0;
    if (consommes || (err && err.code === "plafond")) {
      compta.neurones += consommes;
      // Cloudflare a dit stop avant notre propre plafond : on s'aligne.
      if (err.code === "plafond") compta.neurones = Math.max(compta.neurones, plafondJour);
      compta.appels[route] = (compta.appels[route] || 0) + 1;
      compta.journal = compta.journal.concat([{ t: date.toISOString(), route: route, erreur: err.code, neurones: consommes }]).slice(-200);
      await env.GARDE.put(cleCompta, JSON.stringify(compta), { expirationTtl: 40 * JOUR });
    }
    if (err && err.code && err.statut) {
      return reponseJson({ ok: false, code: err.code, message: err.message }, err.statut);
    }
    return reponseJson({ ok: false, code: "interne", message: "Erreur interne de l'assistant." }, 500);
  }

  compta.neurones += resultat.neurones || 0;
  compta.appels[route] = (compta.appels[route] || 0) + 1;
  compta.journal.push({
    t: date.toISOString(), route: route, modele: resultat.modele,
    entree: (resultat.usage || {}).entree || 0, sortie: (resultat.usage || {}).sortie || 0,
    neurones: resultat.neurones || 0, duree: resultat.duree || 0,
  });
  compta.journal = compta.journal.slice(-200);
  await env.GARDE.put(cleCompta, JSON.stringify(compta), { expirationTtl: 40 * JOUR });

  // 5. Cache : seules les réponses abouties y entrent.
  if (cache && resultat.corps && resultat.corps.ok) {
    const aGarder = new Response(JSON.stringify(resultat.corps), {
      headers: { "content-type": "application/json", "cache-control": "max-age=" + ttlCache },
    });
    const ecriture = cache.put(cleCache, aGarder);
    if (contexte.waitUntil) contexte.waitUntil(ecriture); else await ecriture;
  }
  return reponseJson(resultat.corps, resultat.statut || 200);
}

// Corps JSON borné : au-delà de `max` octets, la requête est refusée avant
// toute lecture coûteuse.
export async function lireCorps(request, max) {
  const longueur = Number(request.headers.get("content-length") || 0);
  if (longueur > max) return { erreur: reponseJson({ ok: false, code: "invalide", message: "Requête trop volumineuse." }, 413) };
  const texte = await request.text();
  if (texte.length > max) return { erreur: reponseJson({ ok: false, code: "invalide", message: "Requête trop volumineuse." }, 413) };
  try {
    return { corps: JSON.parse(texte) };
  } catch {
    return { erreur: reponseJson({ ok: false, code: "invalide", message: "Corps JSON illisible." }, 400) };
  }
}
