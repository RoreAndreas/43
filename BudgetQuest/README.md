# Budget Quest 🗡️

Tracker de dépenses et de budgets **en FCFA**, façon RPG pixel art.
Un seul fichier : `index.html`. Il ne demande ni installation ni serveur.

## Utilisation

- **Sur ordinateur** : ouvre `index.html` dans ton navigateur.
- **Sur téléphone** : active GitHub Pages sur le repo (Settings → Pages → branche `main`, dossier `/root`).
  L'app sera alors à l'adresse `https://<utilisateur>.github.io/43/BudgetQuest/`. Depuis le navigateur du téléphone, choisis « Ajouter à l'écran d'accueil ».

Les données restent dans le navigateur de l'appareil (`localStorage`).
Pour les sauvegarder ou les passer d'un appareil à l'autre, utilise **Options → Export JSON / Importer**.
**Export CSV** sort tes dépenses pour Excel, avec `;` comme séparateur.

## Onglets

| Onglet | Contenu |
|---|---|
| **Monde** | Carte en monde ouvert à explorer, budget du jour, saisie rapide d'une dépense, quêtes du jour, monstres (catégories) |
| **Journal** | Calendrier du mois coloré selon les dépenses de chaque jour, détail par jour, modification et suppression |
| **Écarts** | Budget, réel, écart et projection de fin de mois, graphique jour par jour, écarts par catégorie, plus grosses dépenses |
| **Quêtes** | Habitudes quotidiennes avec séries, rattrapage sur 7 jours, trophées, statistiques |
| **Suivis** | Compteurs personnalisés (sommeil, eau, cafés…), avec un objectif « au moins » ou « au plus » |
| **Options** | Nom du héros, son, catégories (monstre, couleur, budget mensuel), sauvegarde |

## Le monde ouvert

Ton héros se déplace sur une carte de 48 × 36 cases vue de dessus.
- **Sur téléphone** : touche une case pour y aller, ou utilise la croix directionnelle et le bouton A.
- **Sur ordinateur** : clique, ou utilise les flèches (ou ZQSD/WASD) et Entrée.

Les onglets restent là comme raccourcis.

| Lieu | Ce qu'il fait |
|---|---|
| Marché (place du village) | Noter une dépense |
| Banque des Écarts | Écarts et projection |
| Archives | Journal et calendrier |
| Tableau des quêtes | Habitudes et trophées. Un « ! » s'affiche s'il reste des quêtes à faire aujourd'hui |
| Labo de l'alchimiste | Suivis personnalisés |
| Maison du héros | Tenues, budgets et options, règles |
| Feu de camp | Pointer une journée sans dépense. Le feu est allumé quand c'est fait |
| Vieux sage | Conseils |
| Repaires des monstres | Un monstre par catégorie. Il dort, s'agite ou se déchaîne selon ce que tu as dépensé dans sa catégorie |

**Coffres** : 9 coffres sont répartis dans le monde. Ils s'ouvrent selon des conditions :
- séries de 3, 7 ou 30 jours ;
- journées sans dépense ;
- jours sous le budget du jour ;
- trophées ;
- niveau.

Ils donnent de l'XP et des tenues. Certains sont cachés dans la forêt, sur une île ou au sommet du col.

**Village** : 9 terrains à bâtir. Ton trésor (économies des mois terminés) y construit dans l'ordre :
- Puits (5 000 F)
- Potager (15 000 F)
- Maison du fermier (30 000 F)
- Boulangerie (60 000 F)
- Forge (100 000 F)
- Fontaine (175 000 F)
- Moulin (300 000 F)
- Tour de guet (500 000 F)
- Château (1 000 000 F)

Un bâtiment construit reste en place même si le trésor baisse ensuite.

**Exploration** : chaque lieu découvert rapporte 10 XP. Le bouton CARTE affiche la carte (les zones non explorées restent noires) et permet le voyage rapide vers les lieux déjà découverts.

## Règles du jeu

- Chaque **catégorie** est un monstre. Plus tu dépenses, plus il enrage. À 100 % du budget, il se **déchaîne** et blesse ton héros.
- **Budget du jour** = reste du mois ÷ jours restants.
- **XP** :
  - +5 par dépense notée
  - +20 par jour pointé
  - +25 par jour sous le budget quotidien
  - +15 par journée sans dépense
  - +100 tous les 7 jours de série
  - +15 par quête accomplie
  - +5 par mesure de suivi
  - +10 par lieu découvert, et l'XP de chaque coffre ouvert
- **PV** : ils repartent à 100 chaque mois.
  - Un monstre déchaîné fait perdre entre 10 et 40 PV.
  - Une journée au-delà de 150 % du budget moyen fait perdre 5 PV.
  - Chaque quête accomplie rend 1 PV, jusqu'à 30 PV par mois.
- **Trésor** = économies cumulées des mois terminés.
- Un budget modifié s'applique au mois choisi et aux mois suivants. Les mois passés gardent leurs écarts d'origine.
