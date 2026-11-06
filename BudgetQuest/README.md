# Budget Quest 🗡️

Tracker de dépenses et de budgets **en FCFA**, présenté comme un RPG 16 bits de la SNES.
Un seul fichier : `index.html`. Il ne demande ni installation ni serveur.

## Utilisation

- **Sur ordinateur** : ouvre `index.html` dans ton navigateur.
- **Sur téléphone** : active GitHub Pages sur le repo (Settings → Pages → branche `main`, dossier `/root`).
  L'app sera alors à l'adresse `https://<utilisateur>.github.io/43/BudgetQuest/`. Depuis le navigateur du téléphone, choisis « Ajouter à l'écran d'accueil ».

Les données restent dans le navigateur de l'appareil (`localStorage`). Les sauvegardes des versions précédentes sont reprises telles quelles.
Pour les sauvegarder ou les passer d'un appareil à l'autre, utilise **Config → Sauvegarde → Exporter (JSON) / Importer**.
**Exporter (CSV)** sort tes dépenses pour Excel, avec `;` comme séparateur.

## Ce qu'on voit : la cité, depuis le PC de Roré

L'écran est celui du PC de Roré, posé sur son bureau de l'Open Space, avec sa tasse « 43 ».
Sur le moniteur, on observe **la cité suspendue** : un panorama en 2D qu'on fait glisser de gauche à droite.
- Au premier plan, la rue de la cité : des maisons de ville du XVIIIe siècle (pierre, toits à la Mansart en ardoise, lucarnes, balcons en fer forgé, volets) bâties sur trois éperons rocheux, reliés par deux ponts de pierre au-dessus du vide.
- Au second plan, d'autres éperons, avec leurs arches et leurs maisons.
- **En contrebas**, au fond de la vallée, une ville en enduit ocre et en tuiles, traversée par une rivière. Elle grandit avec ton trésor, comme le phare de l'Open Space.

Les plans défilent en parallaxe, à des vitesses différentes. Le soir, les façades passent un peu en contre-jour.

**Pour se promener** : fais glisser le paysage (doigt, souris, molette) ou utilise les flèches ← →.
On ne dirige pas Roré : il se promène dans la rue avec Nyx et la famille de l'équipe, et lève les bras quand tu gagnes de l'XP.

### La cité vit avec ton budget

| Ce qui change | Ce qui le décide |
|---|---|
| **L'heure** : jour, soir, nuit étoilée, fenêtres et lanternes allumées | L'heure réelle de l'appareil |
| **La météo** : soleil, nuages, pluie, orage avec éclairs | Soleil sous le budget du jour, nuages près de la limite, pluie au-delà, orage si une catégorie dépasse son budget de 25 % ou si les PV tombent sous 25 |
| **La ville en contrebas** | Le trésor : un clocher (5 000 F), le pont sur la rivière, la grande coupole, un nouveau quartier, le beffroi, une seconde église, les quais, le palais, puis la cité entière (1 000 000 F) |

## Les menus, comme dans Final Fantasy

Tout passe par les fenêtres bleues du bas : on choisit avec la main, au doigt, à la souris ou au clavier (↑ ↓, Entrée, Échap).
Choisir un lieu, dans le menu ou en le touchant dans la scène :
1. la caméra glisse jusqu'au bâtiment, le reste s'assombrit et son contour s'illumine ;
2. le robot qui tient le lieu fait coucou et parle dans une fenêtre de dialogue, en haut (touche-la pour la réplique suivante) ;
3. les fenêtres du bas deviennent celles du lieu. **Retour** revient à la cité.

| Menu | Lieu | Robot | Ce qu'on y fait |
|---|---|---|---|
| **Dépense** | Le Marché | Zaza | Noter une dépense (montant, raccourcis, catégorie, note, date), pointer un jour sans dépense, revoir les dernières |
| **Écarts** | La Banque des Écarts | Hares | Bilan du mois (budget, réel, écart, projection), écarts par catégorie, graphique jour par jour, plus grosses dépenses, mois précédents |
| **Journal** | Les Archives | Margaux | Calendrier du mois coloré selon les dépenses, liste, modification et suppression |
| **Quêtes** | Le Tableau des quêtes | Rook | Habitudes du jour, semaine, trophées, statistiques, nouvelle quête |
| **Suivis** | Le Labo | Boulon | Compteurs personnalisés (sommeil, eau, cafés…) avec un objectif « au moins » ou « au plus », courbe sur 14 jours |
| **Config** | La maison de Roré | Roré | Héros, sons, musique, budgets du mois, catégories, apparence, tenues, sauvegarde, règles |
| — | Le Belvédère (à toucher dans la scène) | Merlain | Des conseils, face à la ville en contrebas |

La barre d'état montre en permanence le trésor, les PV, le niveau et la série.

## Son

- Une petite musique en 8 bits, composée et générée dans le navigateur. Elle est coupée au départ : bouton **♪ MUSIQUE** sous l'écran, ou Config → Héros. La nuit, la mélodie descend d'une octave.
- Un bip à chaque choix de menu et pendant que le texte s'écrit, et une fanfare (originale) aux montées de niveau et quand toutes les quêtes du jour sont faites.

## Personnages : les robots de l'Open Space

Les habitants de la cité viennent de l'[Open Space](https://github.com/RoreAndreas/Openspace43). Ce sont les mêmes robots à tête-cube et à visière, en 20 × 24 pixels, dessinés en code. Le dessin est un portage de `src/engine/robots.ts`, d'après *Le Bureau des agents* de VibesMoney (licence MIT).

**Roré est le héros.** Config → Apparence change la couleur de la visière, de la cape, de la veste et l'accessoire sur la tête.
Les **tenues** se gagnent avec les récompenses, qui s'ouvrent seules quand leur condition est remplie :

| Récompense | Condition | Tenue |
|---|---|---|
| Cadeau de bienvenue | Dès le départ | — |
| Série de 3 jours | Série de 3 jours | Rôdeur des bois |
| 3 jours sans dépense | 3 journées sans dépense | Marin |
| Série de 7 jours | Série de 7 jours | Commandant doré |
| Premier mois réussi | Un mois sous le budget | Ombre |
| 10 jours maîtrisés | 10 jours sous le budget du jour | — |
| Série de 30 jours | Série de 30 jours | Royal |
| Sept trophées | 7 trophées | — |
| Niveau 10 | Niveau 10 | Légende |

Les **catégories** gardent leurs petits monstres, qui s'affichent dans les listes et rougissent quand le budget déborde.

## Règles du jeu

- **Budget du jour** = reste du mois ÷ jours restants.
- **XP** :
  - +5 par dépense notée
  - +20 par jour pointé
  - +25 par jour sous le budget quotidien
  - +15 par journée sans dépense
  - +100 tous les 7 jours de série
  - +15 par quête accomplie
  - +5 par mesure de suivi
  - l'XP de chaque récompense gagnée
- **PV** : ils repartent à 100 chaque mois.
  - Une catégorie qui dépasse son budget fait perdre entre 10 et 40 PV.
  - Une journée au-delà de 150 % du budget moyen fait perdre 5 PV.
  - Chaque quête accomplie rend 1 PV, jusqu'à 30 PV par mois.
- **Trésor** = économies cumulées des mois terminés.
- Un budget modifié s'applique au mois choisi et aux mois suivants. Les mois passés gardent leurs écarts d'origine.
