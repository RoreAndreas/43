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

## Le monde : le village, la suite du jardin de l'Open Space

Le monde est **le village**, une carte autonome de 64 × 30 cases. Elle prolonge vers la droite le jardin et le pavillon 43 de l'[Open Space](https://github.com/RoreAndreas/Openspace43) :
- à gauche, le terrain remonte encore vers l'horizon, comme derrière le pavillon ;
- le chemin de gravier arrive du jardin, et un panneau indique « ← l'Open Space ».

Le jardin lui-même n'est pas dans l'app : le village fonctionne seul.

Le dessin reprend le moteur du jardin (portage de `src/engine/outside.ts` et `outsideDraw.ts`) :
- le sol est vu de dessus en 3/4 : prairie au vent, falaise, pins parasols ;
- la **mer** est peinte en perspective jusqu'à l'horizon : houle, écume, reflet du soleil, voiliers, phare ;
- la lumière suit l'heure de l'appareil, et Nessie nage au large la nuit ;
- la caméra suit Roré dans les deux sens.

| Quartier | Ce qu'on y trouve |
|---|---|
| **L'entrée**, à gauche | La maison de Roré (apparence, tenues, options) et le chemin qui vient du jardin |
| **La place** | Zaza au marché (noter une dépense), Hares à la Banque des Écarts, Margaux aux Archives, Rook au tableau des quêtes |
| **Le belvédère**, au bord de la falaise | Le banc face au large, pour pointer une journée sans dépense, et Merlain qui donne des conseils |
| **Le quartier sud** | Le labo de Boulon (les suivis) et les 9 terrains que le trésor fait construire, du puits au château |
| **La prairie des monstres**, à droite | Les repaires des catégories du budget |

**Pour se déplacer** :
- touche le sol, un bâtiment ou un robot ;
- ou utilise la croix directionnelle et le bouton A ;
- ou les flèches (ZQSD) et Entrée.

Le bouton CARTE montre tout le village et permet le voyage rapide vers les lieux déjà découverts. Les 9 coffres sont cachés dans tout le village, dont un tout en haut à gauche, du côté de l'Open Space.

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
