# Budget Quest 🗡️

Tracker de dépenses et de budgets **en FCFA**, présenté comme un RPG 16 bits de la SNES.
Un seul fichier : `index.html`. Il ne demande ni installation ni serveur.

## Utilisation

- **Sur ordinateur** : ouvre `index.html` dans ton navigateur.
- **Sur téléphone** : active GitHub Pages sur le repo (Settings → Pages → branche `main`, dossier `/root`).
  L'app sera alors à l'adresse `https://<utilisateur>.github.io/43/BudgetQuest/`. Depuis le navigateur du téléphone, choisis « Ajouter à l'écran d'accueil ».

Les données restent dans le navigateur de l'appareil (`localStorage`). Les sauvegardes des versions précédentes sont reprises : dépenses, quêtes, tenues, et l'accessoire de Roré, qui passe dans le bon emplacement.
Pour les sauvegarder ou les passer d'un appareil à l'autre, utilise **Config → Sauvegarde → Exporter (JSON) / Importer**.
**Exporter (CSV)** sort tes dépenses pour Excel, avec `;` comme séparateur.

## Au départ

1. **Choisis ton personnage** parmi 13 robots :
   - l'équipe de l'Open Space : Roré, Nyx, Merlain, Boulon, Margaux, Zaza, Rook, Hares ;
   - les nouveaux venus de la cité : **Kora** (marchande, foulard et collier de perles), **Ama** (pilote de dirigeable, lunettes et écharpe), **Baobab** (jardinier, chapeau de paille et tablier), **Pépin** (cuisinier, toque) et **Lune** (astronome, cape étoilée).
2. Donne-lui un nom, et indique ta **trésorerie de départ** : ce que tu as aujourd'hui.

Si tu choisis un membre de l'équipe qui tient un lieu, Roré prend sa place au comptoir. Tu peux changer de personnage plus tard (Config › Personnage) : ton niveau, tes accessoires et tes tenues te suivent.

## Ce qu'on voit : la cité, depuis le PC de Roré

L'écran est celui du PC de Roré, posé sur son bureau de l'Open Space, avec sa tasse « 43 ».
Sur le moniteur, on observe **la cité suspendue** : un panorama en 2D qu'on fait glisser de gauche à droite.
- Au premier plan, la rue de la cité, sur sa terrasse à balustrade, avec des maisons de ville du XVIIIe siècle.
- Chaque lieu a son allure propre :

| Lieu | Ce qui le distingue |
|---|---|
| **La maison du héros** | Jardinières fleuries, antenne parabolique sur le toit, plaque « 43 » près de la porte |
| **Les Archives** | Haute façade de pierre, horloge dans le toit, perron |
| **Le Marché** | Auvent rayé rouge et blanc, cagettes d'oranges, de légumes et de fruits rouges |
| **Le Tableau des quêtes** | Petit toit, avis épinglés, cloche |
| **La Banque** | Temple de pierre claire, colonnes, fronton à la pièce d'or, porte de bronze cloutée |
| **Le Labo** | Brique rouge, verrière en dents de scie, baie verte lumineuse, cheminée qui fume, bobine qui crépite |
| **Le Belvédère** | Longue-vue de laiton, banc, pots de fleurs |

- Entre les groupes de maisons, des terrasses ouvertes sur **la vallée en contrebas**.

**Pour se promener** : fais glisser le paysage (doigt, souris, molette) ou utilise les flèches ← →.
**Au survol** d'un lieu (souris), sa silhouette s'illumine et un onglet s'affiche au-dessus : le nom du lieu, le robot qui le tient, ce qu'on y fait. Un toucher ou un clic l'ouvre : la caméra y glisse, le reste s'assombrit autour de sa silhouette, et le robot parle.

### La ville en contrebas : elle part de zéro

Au début, la vallée est vide : des champs, des haies, une rivière.
**Chaque jour terminé sous le budget du jour, elle gagne une construction.** Dès que la journée est sur la bonne voie, un échafaudage montre où la ville grandira demain ; il disparaît si la journée déborde.

| Jour tenu | Construction |
|---|---|
| 1, 2, 4 | Les premiers bouts de chemin pavé |
| 3, 5 | Un arbre, une maison |
| 8 | Le puits |
| 10 | Un potager |
| 14 | Le moulin |
| 20 | Le lac |
| 25 | La place pavée |
| 30 | L'église |
| 40 | Le pont sur la rivière |
| 50 | La halle du marché |
| 60 | La tour de guet |
| 75 | La grande coupole |
| 90 | Le château, sur sa colline |
| 100 à 115 | Les remparts, pan par pan |
| 120 | Le palais royal |
| 150 | Les bannières du royaume |

Entre ces étapes : des maisons, des arbres, des chemins et des potagers. La ville est complète au bout de 200 jours tenus.

### L'heure et la météo

| Ce qui change | Ce qui le décide |
|---|---|
| **L'heure** : jour, soir, nuit étoilée, fenêtres et lanternes allumées | L'heure réelle de l'appareil |
| **La météo** : soleil, nuages, pluie, orage avec éclairs | Soleil sous le budget du jour, nuages près de la limite, pluie au-delà, orage si une catégorie dépasse son budget de 25 % ou si les PV tombent sous 25 |

## Les menus, comme dans Final Fantasy

Tout passe par les fenêtres bleues du bas : on choisit avec la main, au doigt, à la souris ou au clavier (↑ ↓, Entrée, Échap).

| Menu | Lieu | Robot | Ce qu'on y fait |
|---|---|---|---|
| **Dépense** | Le Marché | Zaza | Noter une dépense, noter une **rentrée** d'argent, pointer un jour sans dépense, revoir les dernières |
| **Écarts** | La Banque des Écarts | Hares | Bilan du mois (budget, réel, écart, projection), écarts par catégorie, graphique jour par jour, plus grosses dépenses |
| **Journal** | Les Archives | Margaux | Calendrier du mois, liste, modification et suppression |
| **Quêtes** | Le Tableau des quêtes | Rook | Habitudes du jour, semaine, **progression**, trophées, nouvelle quête |
| **Suivis** | Le Labo | Boulon | Compteurs personnalisés avec un objectif « au moins » ou « au plus » |
| **Config** | La maison du héros | — | Héros, **trésorerie**, personnage, apparence, tenues, budgets, catégories, sauvegarde, règles |
| — | Le Belvédère (à toucher dans la scène) | Merlain | Des conseils, et la prochaine construction de la vallée |

**Changer de mois** (Écarts, Journal, Budgets) : les deux flèches de part et d'autre du mois, en haut de l'écran, ou les touches Page précédente / Page suivante.

La barre d'état montre la trésorerie, les PV, le niveau avec sa jauge d'XP et l'XP gagnée aujourd'hui, la série et son multiplicateur. Touche la trésorerie ou le niveau pour ouvrir l'écran correspondant.

## La trésorerie

**Trésorerie = trésorerie de départ + rentrées − dépenses**, comptées depuis la date de départ.
Config › Trésorerie montre le détail, les dernières rentrées, et ce qui restera à la fin du mois si le budget est tenu.

## L'XP : chaque jour compte

| Ce qui rapporte, chaque jour | XP |
|---|---|
| Journal tenu (au moins une dépense notée, ou un jour sans dépense pointé) | +10 |
| Chaque dépense notée (5 au plus) | +2 |
| Sous le budget du jour (plus tu restes loin de la limite, plus ça rapporte) | +30 à +50 |
| Journée sans dépense | +20 |
| Chaque quête accomplie | +15 |
| Toutes les quêtes du jour | +25 |
| Chaque mesure de suivi (objectif atteint : +10) | +5 |

- **Combo de série** : l'XP du jour est multipliée par la série en cours, +4 % par jour, jusqu'à **×2** au 25e jour.
- **Paliers de série** : +150 XP à 7 et 14 jours, +500 à 30, 60 et 100 jours.
- **Fin de mois** : +300 XP si le mois est sous le budget, +40 par catégorie tenue.
- **Niveaux** : le premier demande 100 XP, chaque suivant 75 XP de plus. Les premiers niveaux tombent vite, les suivants restent à portée.
- Quêtes › Progrès détaille l'XP gagnée aujourd'hui, le combo, le prochain accessoire, le prochain titre et la prochaine construction.

### Les accessoires gagnés avec les niveaux

Chaque personnage commence avec son apparence d'origine. Les accessoires se gagnent en montant de niveau, et le héros les porte aussitôt. Config › Apparence permet de les changer.

| Niveau | Accessoire | Emplacement |
|---|---|---|
| 2 | Écharpe | Cou |
| 3 | Lunettes | Visage |
| 4 | Béret | Tête |
| 5 | Cape | Dos |
| 6 | Casque audio | Tête |
| 7 | Lunettes de soleil | Visage |
| 8 | Chapeau de paille | Tête |
| 9 | Lunettes d'aviateur | Visage |
| 10 | Étoile et épaulettes | Poitrine |
| 11 | Collier de perles | Cou |
| 12 | Chapeau d'explorateur | Tête |
| 14 | Foulard | Tête |
| 15 | Voyant de poitrine | Poitrine |
| 16 | Toque | Tête |
| 18 | Chapeau de mage | Tête |
| 20 | Couronne | Tête |

Les couleurs (visière, cape et écharpe, corps) se choisissent librement. Les **tenues** se gagnent avec les récompenses (séries, jours sans dépense, premier mois réussi, niveau 10).

### Les titres

Apprenti (1), Habitant (2), Écuyer (3), Chevalier (5), Gardien du Trésor (7), Paladin de l'Épargne (10), Bâtisseur de cité (13), Seigneur du FCFA (16), Souverain de la vallée (20), Légende vivante (25).

## Son

- Une petite musique en 8 bits, composée et générée dans le navigateur. Elle est coupée au départ : bouton **♪ MUSIQUE** sous l'écran, ou Config → Héros.
- Un bip à chaque choix de menu et pendant que le texte s'écrit, et une fanfare aux montées de niveau.

## Règles

- **Budget du jour** = reste du mois ÷ jours restants.
- **PV** : ils repartent à 100 chaque mois. Une catégorie qui dépasse son budget fait perdre entre 10 et 40 PV ; une journée au-delà de 150 % du budget moyen, 5 PV. Chaque quête accomplie rend 1 PV, jusqu'à 30 par mois.
- Un budget modifié s'applique au mois choisi et aux mois suivants. Les mois passés gardent leurs écarts d'origine.

## Crédits

Les robots sont un portage de `src/engine/robots.ts` de l'[Open Space](https://github.com/RoreAndreas/Openspace43), d'après *Le Bureau des agents* de VibesMoney (licence MIT).
