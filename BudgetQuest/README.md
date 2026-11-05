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
| **Jeu** | Arène animée, budget du jour, saisie rapide d'une dépense, quêtes du jour, monstres (catégories) |
| **Journal** | Calendrier du mois coloré selon les dépenses de chaque jour, détail par jour, modification et suppression |
| **Écarts** | Budget, réel, écart et projection de fin de mois, graphique jour par jour, écarts par catégorie, plus grosses dépenses |
| **Quêtes** | Habitudes quotidiennes avec séries, rattrapage sur 7 jours, trophées, statistiques |
| **Suivis** | Compteurs personnalisés (sommeil, eau, cafés…), avec un objectif « au moins » ou « au plus » |
| **Options** | Nom du héros, son, catégories (monstre, couleur, budget mensuel), sauvegarde |

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
- **PV** : ils repartent à 100 chaque mois.
  - Un monstre déchaîné fait perdre entre 10 et 40 PV.
  - Une journée au-delà de 150 % du budget moyen fait perdre 5 PV.
  - Chaque quête accomplie rend 1 PV, jusqu'à 30 PV par mois.
- **Trésor** = économies cumulées des mois terminés.
- Un budget modifié s'applique au mois choisi et aux mois suivants. Les mois passés gardent leurs écarts d'origine.
