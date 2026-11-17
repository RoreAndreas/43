# Atelier Pagne — structure et plan

Un site de couture : on choisit un **modèle**, on l’habille d’un **pagne**
(catalogue ou photo de son propre tissu) et on voit la tenue en 3D sur un
mannequin, avant de la confier au couturier.

Public visé : 30-40 ans, souvent sur téléphone et parfois avec une connexion
lente ou chère. Le site doit être **simple, lisible et léger**.

---

## 1. Parcours utilisateur

```
Accueil ──► 1. Modèle ──► 2. Pagne ──► 3. Salle d'essayage ──► 4. Récapitulatif
              (coupe)      (catalogue      (3D, poses,            (fiche couturier,
                            ou photo)       mesures, retouches)    partage WhatsApp)
```

Le bouton **« Salle d’essayage »** reste visible à chaque étape : on peut y
entrer directement pour voir le mannequin, puis revenir choisir modèle et pagne.

## 2. Structure du site

| Page | Rôle | État |
|---|---|---|
| `index.html` | Accueil : promesse, 3 étapes, bouton vers la salle d’essayage | ✅ prototype |
| `essayage.html` | Salle d’essayage 3D | ✅ **livrée (étape actuelle)** |
| `modeles.html` | Catalogue de coupes (robe, jupe-haut, boubou, chemise, pantalon…) avec filtres Femme/Homme/Occasion | à faire |
| `pagnes.html` | Catalogue de pagnes + import photo | à faire |
| `recap.html` | Fiche technique : modèle, pagne, mesures, retouches, métrage, partage | à faire |

## 3. Arborescence du code

```
AtelierPagne/
├── index.html               accueil
├── essayage.html            salle d'essayage
├── PLAN.md                  ce document
├── css/
│   ├── tokens.css           couleurs, typo, boutons (partagés)
│   └── essayage.css
├── js/essayage/
│   ├── main.js              scène, caméra, boucle
│   ├── decor.js             showroom clair : lumière, béton, socles, cadres drapés, plantes
│   ├── mannequin.js         chargement du mannequin, squelette, tête ovale, mesures
│   ├── geometry.js          surfaces « loft », tour de mesure (enveloppe convexe)
│   ├── poses.js             bibliothèque de poses (données)
│   ├── garments.js          tenues wax : haut taillé dans le corps, jupe en tissu simulé
│   ├── dress.js             robes importées (Blender) : ajustement, rig, tissu simulé
│   ├── wax.js               six motifs wax originaux + import de la photo d’un pagne
│   ├── rig.js               transitions, IK des bras, contact au sol, tabouret, rubans
│   └── ui.js                panneaux, vues, mesures, mémorisation, clavier
├── assets/mannequin/        femme / homme : maillage + poids (.bin) et repères (.json)
├── assets/garments/        robes importées (.bin + .json)
├── tools/build_mannequin.py fabrique ces fichiers à partir de MakeHuman (CC0)
├── tools/convert_garment.py convertit un vêtement .blend (module Python de Blender)
└── vendor/three/            Three.js r170 (local : pas de dépendance à un CDN)
```

Plus tard : `js/modeles/`, `js/pagnes/`, `js/shared/` (état commun aux pages,
stockage, partage), `assets/modeles/*.glb`, `assets/pagnes/*.webp`.

**Choix techniques**
- HTML/CSS/JS sans étape de build : facile à héberger (GitHub Pages, Netlify).
  On passera à Vite quand le catalogue grossira.
- **Three.js** pour la 3D. Le squelette du mannequin utilise les noms d’os
  standards (`Hips`, `Spine`, `LeftArm`, `LeftForeArm`, `LeftUpLeg`…) : les
  poses resteront valables avec un mannequin GLB rigué plus réaliste, et les
  vêtements 3D pourront être « skinnés » sur le même squelette.
- Tonemapping *neutre* : les couleurs des pagnes seront rendues fidèlement.

## 4. Fonctionnement prévu des étapes à venir

### Modèles préconstruits
- Chaque modèle = un maillage 3D (GLB) dessiné sur le mannequin de base, avec
  des **UV propres** pour poser le motif, et rigué sur le même squelette.
- **Retouches mineures** depuis le site, par curseurs (morph targets ou
  paramètres) : longueur (jupe, robe, manches), ampleur, encolure, type de
  manche (sans / courte / ¾ / longue), fente, ceinture.
  Ces réglages sont **enregistrés comme cotes** dans la fiche technique, pour
  servir de base aux ajustements plus poussés du couturier.

### Import d’un pagne depuis une photo
1. Photo d’un morceau à plat (guide à l’écran : « posez le tissu à plat, bien éclairé »).
2. Recadrage + **redressement de perspective** (4 coins à glisser).
3. Correction de lumière (balance des blancs, ombres atténuées).
4. **Raccord du motif** : génération d’une tuile répétable (décalage + fondu
   des bords) pour couvrir toute la tenue sans couture visible.
5. Réglage de l’**échelle du motif** (curseur « taille du motif »,
   éventuellement à partir d’une référence : une carte bancaire posée à côté).
6. Application en texture sur le modèle. Tout se fait **dans le navigateur**
   (canvas/WebGL) : la photo ne quitte pas le téléphone.

### Récapitulatif
- Image de la tenue (vue face/dos), modèle, pagne, mesures, retouches.
- **Métrage estimé** (en yards / « pièces » de 6 yards, l’unité du marché).
- Export PDF + **partage WhatsApp** vers son couturier.

## 5. Améliorations proposées

**Pour la facilité d’usage (30-40 ans)**
1. Textes en français simple, gros boutons (≥ 44 px), une action principale par écran.
2. Mobile d’abord : menus en « feuilles » en bas d’écran, utilisables au pouce.
3. Aide intégrée (« Comment prendre mes mesures ? » avec illustrations).
4. Mesures et créations **mémorisées** sur l’appareil, sans création de compte.
5. Raccourcis clavier sur ordinateur (poses 1-7, flèches pour tourner).

**Pour la couture**
6. Mannequin **à ses propres mesures** (hauteur, poitrine, taille, hanches) — ✅ déjà en place.
7. Mètres rubans affichés sur le mannequin — ✅ déjà en place.
8. Calcul automatique du **métrage de pagne** à acheter selon modèle et mesures.
9. **Comparer** deux pagnes ou deux modèles côte à côte.
10. Palette de couleurs extraite du pagne pour suggérer doublure, fil, accessoires.
11. Choix du **sens et du placement du motif** (centrer un motif sur le buste, dans le dos…).
12. Fiche couturier partageable par WhatsApp (canal naturel avec les couturiers).
13. Plus tard : réservation d’un couturier partenaire, suivi de commande.

**Technique**
14. Images de pagnes en WebP + chargement progressif (connexions lentes).
15. Mode hors ligne léger (PWA) : la salle d’essayage marche sans réseau.
16. Droits : n’utiliser dans le catalogue que des motifs libres ou sous licence
    (les grandes marques de wax protègent leurs dessins). Les imports de
    l’utilisateur restent privés sur son appareil.

## 6. Feuille de route

| Phase | Contenu | Livrable |
|---|---|---|
| **1 — Salle d’essayage** ✅ | Mannequin de vitrine Femme/Homme gris clair, showroom épuré, 7 poses, vues, rotation auto, mesures client, rubans, photo | `essayage.html` |
| 2 — Modèles | 3-4 coupes de base en GLB (robe droite, jupe + haut, boubou, chemise homme), habillage du mannequin, retouches par curseurs | `modeles.html` + vêtements dans la cabine |
| 3 — Pagnes | Catalogue (10-20 motifs libres), application en texture, échelle du motif | `pagnes.html` |
| 4 — Import photo | Recadrage, perspective, raccord de motif | module d’import |
| 5 — Récapitulatif | Fiche couturier, métrage, PDF, partage WhatsApp | `recap.html` |
| 6 — Finitions | PWA hors ligne, mannequin GLB plus réaliste, tests utilisateurs | — |

## 7. Salle d’essayage — ce qui est livré

- **Mannequin de vitrine réaliste**, gris clair, **sans visage** : corps humain
  lisse et élancé (base MakeHuman, domaine public CC0), mains avec doigts, tête
  ovale lisse posée sur le cou. Femme par défaut, Homme au choix. Le maillage
  est préparé par `tools/build_mannequin.py` (silhouette mince et élancée,
  tétons et nombril effacés, visage retiré, 163 os regroupés en 16).
- **Showroom clair** : mur blanc, sol en béton, plaque d’acier sous le mannequin,
  socles cubiques, cadres métalliques drapés de lin, un peu de végétation.
- Interface **plein écran** : le mannequin occupe l’écran ; une seule barre en bas
  (poses en vignettes, vues Face / 3/4 / Profil / Dos, rotation) ; les réglages
  sont rangés dans le tiroir **Mes mesures**, et la caméra recadre le mannequin
  quand il s’ouvre.
- **Parcours clair** : étapes Modèle → Pagne → Essayage affichées en haut, guide
  en 3 étapes à la première visite (rouvrable avec « ? »).
- **7 poses** animées : Debout, Hanchement, Mains sur les hanches, Bras ouverts,
  Défilé, Pose photo, Assise (un socle en béton sort du sol). Transitions en
  chaîne (le bassin part d’abord, le buste suit, puis la tête et les bras).
- **Animation au repos** (activable) : respiration, report du poids d’une jambe
  sur l’autre, regard qui se promène à gauche et à droite.
- **Tenues wax** : robe sirène, robe évasée, ensemble pagne (femme) ; chemise
  wax, tunique & pantalon (homme). Le haut suit exactement chaque pose ; la jupe
  est un tissu simulé qui se balance, s’écarte quand la jambe avance, drape sur
  les cuisses en pose assise et s’évase quand le mannequin tourne (« Rotation »).
- **Robe importée de Blender** (« Robe longue épaules dénudées ») : ajustée
  automatiquement au mannequin et à ses mesures (aisance de 1,2 cm mesurée sur la
  peau), riggée sur son squelette ; le bustier suit le corps, la jupe longue
  fendue est un tissu simulé (8 500 points) qui garde les plis du modèle,
  s'ouvre sur la jambe à la marche et drape sur les cuisses en pose assise.
  Le pagne est posé selon les UV du patron. Pour en ajouter une :
  `python tools/convert_garment.py robe.blend nom`, puis l'ajouter à OUTFITS.
- **Pagnes** : six motifs wax originaux, ou la photo du pagne de la cliente,
  à l’échelle réelle (taille du motif réglable en cm).
- **Silhouette** : les proportions du modèle de référence fourni (hanches et
  fessiers marqués, taille fine) ont été mesurées et reportées sur le corps
  MakeHuman, propre et riggé. Le fichier GLB fourni (généré par Tripo, vêtements
  soudés au corps, sans squelette) n’est pas utilisé tel quel.
- Mains posées par **cinématique inverse** : elles restent sur les hanches même
  quand on change les mesures.
- **Mes mesures** : hauteur, tours de poitrine, taille, hanches → le mannequin se
  déforme en direct ; valeurs mémorisées sur l’appareil.
- **Mètres rubans** et toise affichables, bouton **Photo** (capture PNG).
