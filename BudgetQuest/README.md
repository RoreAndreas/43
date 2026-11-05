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

## Personnages : les robots de l'Open Space

Les habitants du village viennent de l'[Open Space](https://github.com/RoreAndreas/Openspace43). Ce sont les mêmes robots à tête-cube et à visière, en 20 × 24 pixels, dessinés en code. Le dessin est un portage de `src/engine/robots.ts`, d'après *Le Bureau des agents* de VibesMoney (licence MIT).

**Roré, le chef de projet, est le héros.**
- Il porte sa veste blanche, ses épaulettes, son étoile et sa cape.
- On le voit de face, de dos ou de profil, il marche dans les 4 directions et regarde son équipe quand il attend.
- Il lève les bras quand tu réussis quelque chose.
- **Apparence** (Maison → Apparence, ou Options) : couleur des yeux de la visière, de la cape et de l'antenne, de la veste, et un accessoire sur la tête (béret, chapeau d'explorateur, casque audio, lunettes…).
- **Tenues des coffres** :

| Tenue | Ce qu'elle ajoute |
|---|---|
| Rôdeur des bois | Chapeau d'explorateur, cape verte |
| Marin | Lunettes d'aviateur, cape bleue |
| Commandant doré | Veste et cape dorées |
| Ombre | Capuche, tête sombre |
| Royal | Couronne, cape rouge |
| Légende | Couronne, visière cyan, voyant sur la poitrine |

**L'équipe tient les lieux du village.** Chacun te répond avec ses propres répliques, puis te parle de tes chiffres. Ils font coucou quand tu leur parles et ont leur façon d'attendre.

| Robot | Lieu |
|---|---|
| Zaza, la styliste | Marché |
| Hares, le spartiate de la finance | Banque des Écarts |
| Margaux, l'analyste | Archives |
| Boulon, le robot ingénieur | Labo |
| Rook, l'explorateur | Tableau des quêtes |
| Merlain, le mage du code | Conseils |

Nyx, la hacker, se promène dans le village.

**Leur famille vit dans le monde** : cousins, frères et sœurs, apprentis, et d'autres robots de la même espèce. Chacun reste dans sa zone et a ses propres répliques.

| Robot | Lien | Zone |
|---|---|---|
| Byte | Cousine de Nyx | Plaines de l'est |
| Merlot | Apprenti de Merlain | Lisière de la forêt |
| Écrou | Frère de Boulon | Village |
| Rivet | Cousine de Boulon | Lac |
| Margot | Sœur jumelle de Margaux | Village |
| Zouzou | Cousine de Zaza | Lac |
| Rooky | Petit frère de Rook | Pied du col |
| Ajax | Cousin de Hares | Plaines de l'est |
| Pixel, Plume, Mosaïque | Robots du village, de la même espèce que les robots de métier de l'Open Space | Village, sud, forêt |

**Monstres** : ils sont en 20 × 20 pixels, avec 4 humeurs selon le budget de leur catégorie.

| Budget consommé | Humeur du monstre |
|---|---|
| Moins de 50 % | Dort (Zzz) |
| De 50 à 80 % | Éveillé |
| De 80 à 100 % | Inquiet (sourcils froncés, « ! ») |
| Plus de 100 % | Déchaîné (teinte rouge, yeux brillants, crocs, vapeur) |

**Décor** :
- profondeur : on passe derrière les arbres et les maisons ;
- ombres au sol ;
- eau animée avec écume ;
- maisons aux toits en tuiles ;
- fenêtres éclairées la nuit.

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
