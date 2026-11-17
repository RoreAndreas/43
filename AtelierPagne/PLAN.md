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
│   ├── decor.js             salon, lumières, podium, psyché, portant
│   ├── pattern.js           motif wax raccordable (canvas)
│   ├── mannequin.js         mannequin procédural + morphologies Femme/Homme
│   ├── geometry.js          surfaces « loft », tour de mesure (enveloppe convexe)
│   ├── poses.js             bibliothèque de poses (données)
│   ├── rig.js               transitions, IK des bras, contact au sol, tabouret, rubans
│   └── ui.js                panneaux, vues, mesures, mémorisation, clavier
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
| **1 — Salle d’essayage** ✅ | Mannequin 3D Femme/Homme gris silicone, 7 poses, vues, rotation auto, mesures client, rubans, photo | `essayage.html` |
| 2 — Modèles | 3-4 coupes de base en GLB (robe droite, jupe + haut, boubou, chemise homme), habillage du mannequin, retouches par curseurs | `modeles.html` + vêtements dans la cabine |
| 3 — Pagnes | Catalogue (10-20 motifs libres), application en texture, échelle du motif | `pagnes.html` |
| 4 — Import photo | Recadrage, perspective, raccord de motif | module d’import |
| 5 — Récapitulatif | Fiche couturier, métrage, PDF, partage WhatsApp | `recap.html` |
| 6 — Finitions | PWA hors ligne, mannequin GLB plus réaliste, tests utilisateurs | — |

## 7. Salle d’essayage — ce qui est livré

- Mannequin femme (par défaut) ou homme, **silicone gris clair**, tête sans visage façon vitrine.
- Observable **sous tous les angles** : glisser pour tourner, zoom molette/pincement,
  vues prêtes (Face, 3/4, Profil, Dos, Plongée, Gros plan) et rotation automatique.
- **7 poses** animées : Debout, Hanchement, Mains sur les hanches, Bras ouverts,
  Défilé, Pose photo, Assise (un tabouret apparaît).
- Mains posées par **cinématique inverse** : elles restent sur les hanches même
  quand on change les mesures.
- **Mes mesures** : hauteur, tours de poitrine, taille, hanches → le mannequin se
  déforme en direct ; valeurs mémorisées.
- **Mètres rubans** et toise affichables, bouton **Photo** (capture PNG).
- Motion design couture : aiguille qui coud au chargement, surpiqûres qui se
  cousent, rideau de cabine au changement de silhouette.
- **Décor de boutique** : salon tendu de velours indigo, parquet, faisceau de
  lumière où flotte la poussière, podium incrusté d'une frise wax et cerclé de
  laiton, **psyché qui reflète le dos du mannequin**, portant de pagnes.
  Le motif wax est original, dessiné par le code (`pattern.js`) : il servira aussi
  d'exemple de catalogue.
