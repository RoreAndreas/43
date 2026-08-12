# Guide de lecture des signaux `xlaudit`

Ce document explique comment lire une sortie de `xlaudit` et en tirer des
décisions d'audit. Il ne remplace pas le jugement de l'auditeur : il indique ce
que chaque signal **prouve**, ce qu'il **ne prouve pas**, et comment trancher.

---

## 1. Le principe à ne jamais perdre de vue

Un signal est un **fait**, pas un constat. « La plage s'élargit de colonne en
colonne et l'écart chiffré vaut 5 400 » est un fait. « C'est une erreur » est un
jugement, et il vous appartient.

Conséquence pratique : **aucun signal ne se ferme tout seul**. Chaque signal se
solde par l'une de ces trois décisions, qu'il faut écrire quelque part :

| Décision | Signification |
|---|---|
| **Erreur** | Le modèle est faux, il faut corriger |
| **Convention** | C'est voulu, documenté ou admis — à mentionner sans plus |
| **Faux positif** | La règle s'est trompée, l'outil a mal lu |

Un signal laissé sans décision n'est pas un signal traité.

---

## 2. Ordre de lecture

Lisez dans cet ordre, jamais autrement.

### a. Les réserves (`run.reserves`) — **avant tout chiffre**

Elles disent sur quoi les chiffres reposent. Deux d'entre elles changent la
valeur de tout le reste :

- `CALCPR_*` avec `calcOnSave="0"` → les valeurs en cache ne sont **pas** l'état
  convergé du modèle. Tout chiffrage adossé au cache devient indicatif, y compris
  les verdicts `actif`. Vous devez faire recalculer le classeur dans Excel puis
  relancer avant de citer un montant.
- `VBA_CIRCULARITE` → des macros `Copy`/`Paste` résolvent des circularités. Les
  valeurs dépendent de l'exécution de ces macros et ne sont pas reproductibles.

Si une de ces réserves est présente, **écrivez-la dans votre rapport**. Un
montant cité sans elle est un montant présenté comme plus solide qu'il n'est.

### b. Le journal (`run.rules`) — ce qui n'a pas été regardé

Cherchez les entrées `status: "skipped"` et `status: "error"`. Une règle sautée
faute de mapping signifie qu'un pan entier du contrôle n'a pas eu lieu. Votre
rapport doit dire ce qu'il n'a pas couvert, sans quoi le lecteur suppose une
couverture totale.

### c. Les signaux, triés — mais pas comme vous croyez

Le fichier les trie par `confidence` décroissante. **Ce n'est pas le bon ordre de
travail.** Voir §5.

---

## 3. Anatomie d'un signal

```json
{
  "rule_id": "R205", "phase": 2, "sheet": "Modele",
  "refs": ["D35", "I35"], "label": "Produits (report)",
  "observed": "=SUM($D6:I9)", "expected": "=SUM(I6:I9)",
  "evidence": { "...": "..." },
  "consumers": [], "confidence": 1.0, "note": "..."
}
```

| Champ | Comment le lire |
|---|---|
| `rule_id` / `phase` | Quelle lentille a produit le fait. La phase 1 décrit, elle n'accuse pas |
| `sheet` + `refs` | Où regarder. `["D35","I35"]` = deux cellules ; `["30:33"]` = un groupe de lignes |
| `label` | Le libellé de la ligne dans le modèle. **C'est souvent l'information la plus décisive** : elle dit à quoi sert la ligne |
| `observed` | La formule **exacte** telle qu'elle est écrite. Vous ne devriez jamais avoir à rouvrir le classeur pour la voir |
| `expected` | La correction proposée, déjà transposée à la bonne colonne — copiable telle quelle. `null` quand la règle ne sait pas proposer mieux |
| `evidence` | Le chiffrage et les éléments de jugement. C'est là que se joue la décision |
| `consumers` | Qui consomme la ligne, en `Onglet!ligne`. **Détermine la portée** : une erreur consommée par 40 lignes n'a pas le même poids qu'une erreur terminale |
| `confidence` | Aide au tri. Voir §5 |
| `note` | Le fait, en une phrase, en français |

---

## 4. Lire le chiffrage — le champ le plus décisionnel

Présent dans `evidence` pour R204 à R208. C'est lui, et non la confiance, qui dit
si les chiffres du modèle sont faux **aujourd'hui**.

| `chiffrage` | Ce que ça veut dire | Ce que vous en faites |
|---|---|---|
| **`actif`** | L'écart est non nul : le modèle produit un chiffre faux maintenant | Priorité 1. Chiffrez l'impact avec `ecart_max_absolu` |
| **`latent`** | L'écart est nul aujourd'hui, mais la zone en cause est peuplée : l'erreur mordra dès que ces cellules cesseront d'être nulles | Priorité 2. À signaler comme fragilité, pas comme erreur de chiffres |
| **`nul`** | La zone en cause est vide : aucun effet possible en l'état | Priorité 3. Souvent une maladresse d'écriture sans conséquence |
| **`indéterminé`** | La formule sort du cadre reconstituable par l'outil | **L'outil refuse d'inventer un chiffre.** À vérifier à la main. Lisez `motif_indetermine` |

Deux champs compagnons décident de la solidité du chiffrage :

- **`cache_confirme_la_formule: true`** — la valeur enregistrée dans le classeur
  correspond exactement à ce que produit la formule telle qu'écrite. Autrement
  dit : l'outil a lu la formule correctement, et l'écart constaté est réel. C'est
  le sceau de fiabilité du chiffrage.
- **`cache_confirme_la_formule: false`** — la valeur en cache ne correspond pas au
  recalcul. Soit le cache est périmé, soit une macro intervient, soit l'outil lit
  mal la formule. **Ne citez pas le montant** avant d'avoir compris pourquoi.

Le tableau `detail_colonnes` donne, colonne par colonne : la valeur en cache, le
recalcul avec la formule écrite, le recalcul avec la formule attendue, et
l'écart. C'est votre papier de travail — il se recopie tel quel dans un dossier.

---

## 5. Lire la confiance — et ses limites

`confidence` répond à une seule question : **« quelle est la vraisemblance que ce
ne soit pas un faux positif ? »** Elle ne dit rien de la gravité, ni du montant,
ni du caractère volontaire.

Trois pièges à connaître :

1. **Elle n'est pas comparable d'une règle à l'autre.** Chaque règle a son propre
   barème, documenté dans sa docstring. Un R203 à 0.85 et un R215 à 0.85 ne
   veulent pas dire la même chose.
2. **Une confiance basse n'est pas « probablement faux ».** Les signaux de
   cartographie (R101) et de cadrage (R501, R502, R503) sortent à 0.10-0.30 parce
   que ce ne sont **pas des anomalies du tout** : ce sont des faits de contexte.
   Filtrez d'abord par phase.
3. **1.00 n'est pas « certainement une erreur ».** C'est « certainement pas un
   artefact de lecture ». Une plage volontairement élargie reste une convention
   possible — que le chiffrage vous aide à discuter, pas à trancher.

### L'ordre de travail recommandé

Triez par **chiffrage d'abord, confiance ensuite** :

```bash
# Les signaux qui faussent les chiffres aujourd'hui, du plus gros au plus petit
jq '[.signals[]
     | select(.evidence.chiffrage == "actif")]
    | sort_by(-.evidence.ecart_max_absolu)
    | .[] | {rule_id, sheet, refs, label,
             ecart: .evidence.ecart_max_absolu,
             confiance: .confidence, note}' signaux.json
```

```bash
# Les canaux débranchés : mécanismes qui paraissent exister sans produire d'effet
jq '[.signals[]
     | select(.rule_id == "R215" and .evidence.canal_debranche == true)]
    | .[] | {sheet, refs, label, note}' signaux.json
```

```bash
# Ce que l'outil a refusé de chiffrer, et pourquoi
jq '[.signals[]
     | select(.evidence.chiffrage == "indetermine")]
    | .[] | {rule_id, sheet, refs, motif: .evidence.motif_indetermine}' signaux.json
```

---

## 6. Règle par règle : ce que le signal prouve, et comment trancher

### R201 — Erreurs en cache

**Prouve** : la cellule contient une erreur Excel enregistrée.
**Ne prouve pas** : que la faute soit dans cette cellule.

Lisez `formule_conforme_a_la_ligne`. Si `true`, la formule est identique à celle
de ses voisines : **la cause est en amont**, et `cellules_amont_en_cause` vous
donne le coupable (`F56 = 0` pour un `#DIV/0!`). Ne corrigez pas la cellule
signalée, remontez.

`#N/A` sort à 0.75 et non 0.95 : c'est fréquemment un résultat de recherche
assumé. Les autres erreurs ne le sont jamais.

### R202 — Valeurs en dur

**Prouve** : une constante numérique dans une ligne majoritairement calculée.
**Ne prouve pas** : que ce soit une erreur.

Le discriminant est `libelle_de_controle`. Une valeur en dur dans une ligne
« Contrôle » **neutralise le contrôle lui-même** — le modèle affiche un contrôle
au vert qui ne vérifie plus rien. C'est un signal de premier ordre.

Piège de lecture : une constante en **colonne de bord** (`colonne_de_bord: true`)
est presque toujours une initialisation légitime — le solde d'ouverture de la
première période. L'outil la sort à ~0.35 pour cette raison. Ne la remontez pas.

### R203 — Cohérence horizontale

**Prouve** : une colonne porte une structure de formule différente du reste de sa
ligne.
**Ne prouve pas** : laquelle des deux est bonne.

La formule majoritaire n'a pas toujours raison. Regardez `part_variante` : une
variante sur 1 colonne sur 20 au milieu d'une chronique est une retouche oubliée ;
une variante sur 8 sur 20 est peut-être un changement de régime volontaire
(construction / exploitation).

`colonnes_de_bord: true` abaisse fortement la confiance : première et dernière
colonne diffèrent légitimement.

### R204 — Glissement de recopie

**Prouve** : les bornes de la plage avancent de +1 par ligne alors que le bloc
source est fixe.
**Le champ décisif** : `sous_totaux_captures`. Si la dérive capture une ligne de
total, il y a **double comptage certain** — la même grandeur est additionnée deux
fois. `articles_omis` donne l'autre moitié du dégât.

Ce signal est rarement un faux positif : l'outil a déjà écarté les plages qui
contiennent leur propre ligne (sommes horizontales, moyennes mobiles).

### R205 — Ancrage asymétrique

**Prouve** : `largeur_par_colonne` passe de 1 à 6 le long de la ligne. La plage
s'élargit au lieu de se déplacer.

C'est l'erreur que personne ne voit à la relecture, parce que la formule *a l'air*
juste. Quand `chiffrage: "actif"` et `cache_confirme_la_formule: true`, le fait
est établi de bout en bout : la formule fait bien ce qu'on dit, et le classeur
contient bien le résultat faux. Confiance 1.00.

Le seul contre-argument recevable : l'auteur voulait un **cumul**. Vérifiez le
libellé — s'il porte « cumulé », « depuis l'origine », « à date », c'est une
convention et non une erreur.

### R206 — Somme tronquée

Deux contrôles, distingués par `evidence.controle` :

- `coherence entre colonnes` — une colonne somme moins de lignes que ses voisines.
  `lignes_omises` nomme l'article oublié, avec son libellé.
- `coherence avec l'etendue du bloc` — la plage n'épouse pas le bloc délimité par
  l'en-tête et le sous-total. `bord_omis` dit si c'est la première ou la dernière
  ligne.

L'omission de la **dernière** ligne d'un bloc est le cas le plus fréquent en
pratique : on insère un article en bas du bloc sans étendre la somme.

### R207 — Plage de somme multi-colonnes

**Prouve** : Excel redimensionne la plage de somme à la forme de la plage de
critères. Le signal donne les deux montants :

- `montant_somme` — ce qui est **effectivement** additionné
- `montant_apparent` — ce qu'un lecteur de la formule croirait additionné
- `ecart_de_lecture` — la différence entre les deux

C'est un comportement d'Excel, pas une hypothèse : le fait est certain. Reste à
savoir si l'auteur voulait la colonne unique. Si `zone_ignoree_vide: true`,
l'écriture est trompeuse mais sans conséquence chiffrée.

### R208 — Somme hétérogène

**Prouve** : une colonne additionne plus ou moins de termes que ses voisines.
**Le champ décisif** : `double_comptage`. L'outil interroge le graphe pour savoir
si un terme en trop est **déjà agrégé** par un autre terme de la même formule
(« la ligne 18 agrège déjà la ligne 10 »). Quand ce champ est rempli, le double
comptage est établi, pas supposé.

`blocs_sources` donne les lignes citées avec leurs libellés, pour reconstituer
l'intention de l'auteur.

### R215 — Lignes orphelines

**Prouve** : la ligne est calculée et **aucune formule du classeur ne la lit**.
**Ne prouve pas** : que ce soit anormal.

C'est la règle qui demande le plus de discernement, et elle produira **beaucoup**
de signaux sur un modèle réel. Le tri se fait par `canal_debranche` :

- `canal_debranche: true` (confiance 0.85-0.90) — le libellé annonce un mécanisme
  (« Impasse de trésorerie », « ADSCR », « Contrôle », « Covenant »). Une ligne
  qui *paraît* faire quelque chose sans rien alimenter est un **signal de premier
  ordre** : le modèle affiche une sécurité qui n'est branchée sur rien.
- `canal_debranche: false` (confiance 0.15-0.25) — libellé quelconque. Ce sont le
  plus souvent des lignes de restitution terminales, parfaitement légitimes. **Ne
  les remontez pas une par une.**

Filtrez systématiquement sur `canal_debranche == true` en première passe.

### R301 — Bouclages (phase 3)

`evidence.controle` nomme l'invariant. Deux champs pilotent la lecture :

- `ecart_maximal` rapporté à `tolerance` — la confiance suit ce rapport. Un écart
  100 fois supérieur à la tolérance ne peut pas être un arrondi (0.95) ; un écart
  qui l'effleure, si (0.55).
- `premiere_periode_en_ecart` — **c'est par là qu'il faut commencer**. Un bilan
  qui se déséquilibre à partir de la période 12 et jamais avant désigne un
  mécanisme qui s'active à cette période.

Le `detail` donne le tableau période par période, prêt à coller dans un dossier.

Pour `tresorerie_negative`, trois informations à lire ensemble :
`etage_de_bascule` (quel poste fait plonger), `mecanismes_de_couverture` (leur
état à cette période) et `signal_de_declenchement` (**sur quelle grandeur leur
déclenchement est branché**). C'est ce dernier qui distingue une facilité qui ne
s'active pas d'une facilité branchée sur la mauvaise grandeur.

### R401 — Reconstitution du cache

**Prouve** : des cellules ne redonnent pas leur valeur enregistrée quand on les
recalcule à partir de leurs précédents.

`part_en_ecart` est la mesure à regarder. Au-delà de 1 %, le cache n'est
vraisemblablement pas l'état convergé du modèle, et **tous les autres chiffrages
en héritent**. C'est un signal sur la fiabilité de la sortie entière, pas sur une
cellule.

`cellules_hors_perimetre` dit combien de cellules l'évaluateur n'a pas su
reconstituer : elles ne prouvent rien, ni dans un sens ni dans l'autre.

### R101, R501, R502, R503 — cadrage

Ce ne sont pas des anomalies. Ils servent à écrire la section « périmètre et
méthode » de votre rapport : inventaire, faisabilité du recalcul, propriétés de
calcul, étendue de propagation d'un choc.

Pour `R503`, retenez que l'**amplitude n'est jamais chiffrée** : l'outil donne
`lignes_atteintes` et `onglets_atteints`, c'est-à-dire la portée. Chiffrer un
choc exige un recalcul par Excel, que l'outil refuse de simuler.

---

## 7. Angles morts — ce que l'outil ne voit pas

À connaître avant de conclure qu'un modèle est propre.

- **Les erreurs de logique métier.** Un taux d'actualisation faux, une formule de
  TRI mal posée, une hypothèse absurde : tout cela est structurellement invisible.
  L'outil vérifie la mécanique, jamais la pertinence.
- **Ce que le mapping ne couvre pas.** La phase 3 ne contrôle que les grandeurs
  déclarées **et validées**. Le journal liste le reste.
- **Les formules hors périmètre du chiffreur.** Les verdicts `indéterminé` sont
  des trous dans la couverture, pas des feux verts.
- **Les valeurs en cache périmées.** Sans recalcul dans Excel, tout chiffrage est
  adossé à un état que l'outil ne peut pas garantir.
- **Le grain de la ligne.** `consumers` raisonne par ligne : une ligne peut être
  consommée sur certaines colonnes seulement. Pour la précision cellule, utilisez
  `xlaudit trace`.

---

## 8. Le réflexe : `trace`

Devant un signal dont vous ne comprenez pas la portée, la question n'est jamais
« que dit l'outil ? » mais « d'où vient ce chiffre et qui s'en sert ? ».

```bash
xlaudit trace modele.xlsm --cell "Modele!D35" --direction up    # d'où ça vient
xlaudit trace modele.xlsm --cell "Modele!D35" --direction down  # qui s'en sert
```

La sortie porte la formule **et** la valeur à chaque niveau. C'est la commande la
plus utilisée en pratique, et elle tranche la plupart des hésitations plus vite
que la lecture du signal lui-même.

---

## 9. Exploitation par un modèle de langage

La sortie JSON est conçue pour être relue par un LLM chargé de la rédaction. Le
prompt qui fonctionne tient en quelques contraintes :

1. Donnez-lui les **réserves en premier**, et exigez qu'elles apparaissent dans
   tout paragraphe citant un montant.
2. Exigez que chaque affirmation cite `sheet`, `refs` et le montant tiré de
   `evidence` — jamais un chiffre reformulé de mémoire.
3. Interdisez-lui de trancher « erreur » ou « volontaire » : il doit exposer les
   deux lectures quand `label` ou le contexte laissent place au doute.
4. Faites-lui traiter les `chiffrage: "actif"` d'abord, et regrouper les R215 à
   `canal_debranche: false` en une seule mention agrégée.

Le champ `note` de chaque signal est déjà rédigé factuellement en français : il
sert de base sûre, à condition de ne pas lui ajouter d'adjectifs.
