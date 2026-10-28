# wacc43 — Coût moyen pondéré du capital

Calcul du CMPC par la méthode indirecte, à partir des bases Damodaran et de la
courbe des taux US Treasury.

La plateforme est **une page statique** : les données de marché (~21 Ko) sont
embarquées dans le fichier HTML et les formules s'appliquent dans le navigateur.
Aucun serveur à faire tourner, donc aucun coût d'hébergement et rien à
surveiller. Seuls HARES et l'analyste de prévision, facultatifs, passent par
deux fonctions Cloudflare, sur un modèle gratuit : sans elles, la page
fonctionne à l'identique et HARES lit les demandes courantes sur place (voir
« HARES », plus bas).

## Organisation

```
PFILES/
├── moteur/          le code Python : téléchargement, calcul, construction, export
├── presentation/    le gabarit — CSS, markup et formules en JavaScript
├── site/            le livrable publié par Cloudflare Pages (index.html)
├── functions/       les deux routes de HARES et de l'analyste (Cloudflare Pages Functions)
├── agent/           les modules qu'elles importent : garde-fous, modèle, instructions
├── donnees/         le jeu de données extrait, lisible, hors du dossier publié
├── requirements.txt
└── README.md
```

| Fichier | Rôle |
|---|---|
| `moteur/build_static.py` | **Point d'entrée** — construit `site/index.html` |
| `moteur/wacc_core.py` | Téléchargement des sources, condensation, formules Python |
| `moteur/wacc_html.py` | Injecte le jeu de données dans le gabarit |
| `moteur/get_us_bond_rate.py` | Moyenne annuelle des taux US Treasury |
| `moteur/comparables.py` | Lecture et fusion des exports S&P Capital IQ |
| `moteur/zones.py` | Découpage géographique continent / zone |
| `moteur/export_wacc.py` | Génération du classeur Excel |
| `moteur/serve.py` | Aperçu local et export Excel |
| `presentation/wacc_value_tab.html` | Présentation **et** formules en JavaScript |
| `functions/api/ask.js` | HARES, niveau 1 : une demande devient une requête ou des opérations sur l'échantillon |
| `functions/api/forecast.js` | Niveau 2 : l'analyste relit le prévisionnel |
| `agent/` | Garde-fous, adaptateur Workers AI, instructions, schémas — hors de `functions/`, qui ne porte que des routes |

Le dossier `site/` porte ce nom parce qu'il est déclaré tel quel dans Cloudflare
Pages (répertoire de sortie et filtre de reconstruction) : le renommer casse le
déploiement.

## Mettre à jour

Il suffit de pousser :

```powershell
git add .
git commit -m "..."
git pull --rebase
git push
```

Le workflow `.github/workflows/build_wacc.yml` reconstruit la page, la committe
si elle a changé, et Cloudflare redéploie. **L'URL ne change jamais.**

Le workflow se déclenche à chaque push touchant `WACC43/PFILES/` (hors `site/`
et `donnees/`), tous les trimestres pour rafraîchir les données de marché, et à
la demande depuis l'onglet Actions.

Pour construire à la main :

```powershell
pip install -r requirements.txt
python moteur/build_static.py --keep-data
```

Compter environ quatre minutes, l'essentiel étant les taux Treasury (une requête
par année et par maturité). Le script refuse d'écrire si l'extraction descend
sous 100 pays ou 60 industries : une source en panne fait échouer la
construction plutôt que publier une page vide.

## Export Excel

Le bouton flèche, en haut à droite de la page, télécharge le calcul dans le
même gabarit : mêmes sections — Ke, Kd, pondération, transposition de
Fisher, synthèse — mêmes formules, et les valeurs de l'écran là où le modèle les
attend. La colonne des commentaires porte la source de chaque nombre. Le
classeur est écrit dans le navigateur : la page reste autonome, hors ligne
comprise.

## Aperçu local

```powershell
python moteur/serve.py
```

Sert la page avec les données du jour sur <http://localhost:8000>, sans passer
par un build. Il expose aussi `/export.xlsx?country=…&industry=…`, une version
enrichie du classeur : elle embarque les feuilles Damodaran utilisées et les
relie ligne à ligne. Celle-là réclame Python, elle n'existe donc pas dans la
version statique.

## Partager la page

`site/index.html` est autonome : il s'envoie par e-mail ou Teams et fonctionne
hors ligne. Les paramètres voyagent dans l'URL
(`?country=France&industry=Advertising&year=2026`), donc copier l'URL partage la
configuration. Les noms sans accent ni casse exacte sont résolus
automatiquement.

## Méthode

```
a     = taux US Treasury (moyenne annuelle) + prime de risque pays
a_d   = taux US Treasury (moyenne annuelle) + spread de défaut pays
b     = beta désendetté × (1 + D/E × (1 − t))
Re    = a + b × c + d + e                    coût des fonds propres (MEDAF)
Rd    = (spread + a_d) × (1 − t)             coût de la dette après impôt
WACC  = E/V × Re + D/V × Rd
CMPC  = (1 + WACC) × (1 + infl. locale) / (1 + infl. référence) − 1
local
```

`c` : prime de risque d'un marché mature (Damodaran). `d` et `e` : primes de
taille et spécifique, saisies dans l'interface. `E/V = 1/(1 + D/E)`.

Le pays entre deux fois, par deux colonnes du même fichier Damodaran
(`ctryprem.xlsx`, feuille *ERPs by country*). La prime de risque pays
(*Country Risk Premium*) majore le taux sans risque des fonds propres. Le coût
de la dette prend le spread de défaut fondé sur la notation souveraine
(*Rating-based Default Spread*), parce que la prime pays est ce même spread
multiplié par la volatilité relative des actions, une grandeur propre aux fonds
propres. Sous le référentiel Comparables, aucun spread sectoriel n'est publié :
`Rd = a_d × (1 − t)`.

Sous référentiel BRVM, le taux sans risque vient de la courbe souveraine de
l'État retenu, publiée chaque semaine par UMOA-Titres. Il porte déjà le risque
pays : aucune prime ne s'y ajoute, et le coût du capital qui en découle est
directement en monnaie locale. La profondeur des courbes va de 7 ans (Niger,
Guinée-Bissau) à 15 ans (Côte d'Ivoire, Sénégal, Togo).

Couverture : 157 pays et 94 industries, tous dotés d'un taux d'IS. Le fichier
fiscal de Damodaran suit la nomenclature des Nations unies (« United States of
America ») : `zones.py` ramène ses libellés à ceux du fichier de primes. Il se
termine aussi par une liste qui répète vingt-deux pays à des taux antérieurs ;
seule la première occurrence est retenue. Un pays qui resterait sans taux
prendrait 25 %, signalé à l'écran.

### Référentiel Comparables

L'univers vient des exports S&P Capital IQ déposés à la racine de WACC43 :
`43 AF.xlsx`, `43 EU.xlsx`, `43 ME.xlsx`, `43 US.xlsx` (stockés sur Git LFS).
Les colonnes y sont repérées par leur code S&P, pas par leur position.

```
gearing (société)          = dette totale / fonds propres
βu (société)               = β coté / (1 + (1 − t pays) × gearing)
βu (secteur), gearing      = médianes sur les 20 plus grosses capitalisations
β ré-endetté               = βu × (1 + (1 − t pays valorisé) × gearing retenu)
```

`t pays` est le taux d'IS légal Damodaran du pays de chaque société. Le taux
effectif publié par S&P est conservé dans les données (`is_effectif`) sans
entrer dans le calcul ; le brancher se fait dans
`comparables.taux_desendettement()`. Le bêta coté est le 3 ans ; un export qui
n'en publie pas fait retenir le 1 an pour ses sociétés, et la page le signale.

> Les formules existent en deux exemplaires : en JavaScript dans le gabarit,
> pour la page, et en Python dans `moteur/wacc_core.py`, pour l'export Excel.
> Toute modification de la méthode doit être portée des deux côtés.

## HARES

HARES vit dans son propre onglet, sur toute la zone de contenu, sans panneau
latéral ni filtre classique. Il affine et analyse en langage naturel un
**échantillon de travail** de sociétés cotées :

- **Départ.** L'échantillon des comparables quand le référentiel Comparables en
  définit un — les sociétés retenues du CMPC, annoncées en tête de page —,
  sinon la base complète. Un bouton repart de la base complète. HARES suit
  l'échantillon des comparables tant qu'aucune demande n'a été appliquée ; au
  delà, il signale qu'il a changé sans l'écraser.
- **Demandes cumulatives.** Chaque demande s'applique au résultat de la
  précédente : filtrer (secteur, lieu, statut, seuils sur la marge, le levier,
  les multiples…), classer, garder les N premières, médiane et quartiles,
  valeurs aberrantes (règle de Tukey, chaque retrait expliqué), retirer des
  sociétés nommées. Le fil des étapes permet d'annuler ou de reprendre plus
  haut ; « repars de zéro » revient au départ.
- **Sociétés choisies.** « Utilise Sonatel, ORAC et MTN Nigeria », « calcule
  le CMPC avec BRVM:SNTS et Orange CI » : l'analyste désigne lui-même les
  sociétés, par leur nom ou leur ticker, prises dans toute la base et non
  dans l'échantillon courant. Un ticker que plusieurs places réutilisent (MTN
  est MTN Group à Johannesburg et Vail Resorts à New York) se précise par sa
  place ; HARES propose les candidats plutôt que de deviner, et un nom
  introuvable arrête la demande au lieu d'être écarté en silence. Quand la
  demande vise le CMPC, la confirmation de l'écrasement suit aussitôt.
- **Industry classification.** La colonne « Industry Classification » des
  exports (`MI_INDUSTRY_CLASSIFICATION`, Sheet1) est une autre nomenclature
  que la Primary Industry de Sheet2 — « Bank » et non « Diversified Banks » —
  et la contredit sur la moitié des sociétés africaines ; le build l'embarque
  à part, dans `classification`. HARES filtre dessus (« isole l'industry
  classification Asset Management », « garde les Oil and Gas Exploration
  and Production au Nigeria ») et
  décompose : « de quoi est composée l'industrie Banks en industry
  classification ? » répond sur toute la base, « décompose l'échantillon par
  industry classification » sur l'échantillon, regroupé par industrie. La
  composition ne filtre rien ; chaque classification s'y clique pour devenir
  un filtre.
- **Cloisonné.** Rien de ce que HARES filtre ne touche les autres onglets. Seul
  « Envoyer vers comparaison » transmet l'échantillon, et seulement aux
  multiples de Valorisation › Comparables — donc à la valorisation par les
  comparables, à la Synthèse et à l'export. Le bêta du CMPC reste celui des
  sociétés retenues.

Deux données manquent aux exports S&P, et HARES le dit quand il s'en sert :

- **Groupe ou filiale.** Aucun export ne le donne en colonne. Le build le lit
  dans la description intégrale (`statut_groupe()` dans `comparables.py`) :
  filiale quand S&P la dit « subsidiary of » une autre société, dont le nom
  est gardé ; groupe quand la description parle de filiales ou d'une activité
  découpée en segments, ou que le nom porte Group ou Holding. Sur 8 118
  sociétés : 3 311 groupes, 828 filiales, 3 979 sans signal.
- **Trésorerie.** Absente des exports : le levier est la dette totale (brute) /
  EBITDA. Ajouter la colonne `IQ_CASH_ST_INVEST` à l'onglet des données de
  marché suffit pour que le build la lise et que HARES passe en dette nette.

HARES suit le brief du 5 octobre 2026 avec une contrainte de plus : **son
cerveau est gratuit**. HARES et l'analyste de prévision tournent sur Cloudflare
Workers AI, dans l'enveloppe offerte de 10 000 neurones par jour, chez
l'hébergeur qui sert déjà la page. Les questions qui ne portent pas sur
l'échantillon — un pays, un taux, le CMPC — gardent leurs réponses, dans le
même onglet.

| Niveau | Où | Rôle | Coût |
|---|---|---|---|
| 0 | navigateur | gabarits de demandes et de questions, exécutés sur `DATA` et `COMPARABLES` | 0 |
| 1 | `/api/ask` | traduit une demande libre en requête ou en opérations sur l'échantillon | ≈ 12 neurones (Qwen 3 30B) |
| 2 | `/api/forecast` | l'analyste relit le prévisionnel, dans des bornes | ≈ 400 neurones (Llama 3.3 70B) |

**Le modèle ne lit jamais les données.** Il traduit une demande en requête ou
en opérations, que la page exécute elle-même — de l'échantillon, il ne reçoit
que l'effectif et les étapes ; ou il juge un dossier de ratios agrégés en
millions de FCFA, jamais la balance. Toute réponse est validée deux fois, par
le serveur puis par la page, et une valeur hors bornes est ramenée à la borne.

**La page reste autonome.** Ouverte depuis un fichier, déployée sans
`functions/`, ou quand l'enveloppe du jour est consommée, elle calcule, exporte
et HARES lit les demandes courantes sur place ; l'onglet dit qu'il est hors ligne.

**Rien ne part sans le dire.** La demande quitte le navigateur au niveau 1 ;
les chiffres de la société au niveau 2, et seulement une fois cochée la case
« Les chiffres de la société seront envoyés à un service externe pour analyse ».

### Règles de prévision, sans IA

Le panneau d'hypothèses porte trois onglets — Défaut, Règles, Analyste — et un
tableau qui compare les trois jeux, valeur d'entreprise comprise. Les règles :
normalisation sur trois exercices (l'exercice atypique écarté), croissance et
marge qui convergent vers le secteur, CapEx lié à la croissance, g plafonné par
l'inflation locale, alerte sur un compte mal classé. Pour tous les jeux :
report des déficits (`calculDcf` accepte un `f.impots` optionnel, seule
modification d'une fonction de calcul, sans effet quand il est absent) et
passage de la VE aux fonds propres, ligne à ligne par classe SYSCOHADA, dans la
Synthèse. L'export joint une feuille « Hypothèses » dès que les règles ou
l'analyste ont servi.

### Déployer les fonctions

Cloudflare Pages cherche `functions/` dans le **répertoire racine du projet**,
pas dans le répertoire de sortie. Pour que celui-ci soit trouvé, le projet doit
avoir pour répertoire racine `WACC43/PFILES` et pour répertoire de sortie
`site` (Settings › Builds). Sans cela, la page se déploie comme avant et
HARES reste en mode gabarits.

Puis, dans Settings › Functions et Settings › Variables :

| Élément | Type | Valeur |
|---|---|---|
| `AI` | liaison Workers AI | — |
| `GARDE` | liaison KV | un espace de noms créé pour l'occasion |
| `SEL_IP` | secret | une chaîne aléatoire longue ; sans elle, les routes refusent de tourner |
| `MODELE_TRADUCTEUR` | variable, facultative | `workersai:@cf/qwen/qwen3-30b-a3b-fp8` |
| `MODELE_ANALYSTE` | variable, facultative | `workersai:@cf/meta/llama-3.3-70b-instruct-fp8-fast` |
| `QUOTA_QUESTIONS_IP` | variable, facultative | 40 par jour |
| `QUOTA_PREVISIONS_IP` | variable, facultative | 5 par jour |
| `PLAFOND_NEURONES_JOUR` | variable, facultative | 9 000 |

`wrangler.toml.exemple` donne la même configuration pour `wrangler pages dev`.
Il n'est pas versionné sous son vrai nom : un `wrangler.toml` présent dans le
dépôt devient la source de vérité de Cloudflare, et un identifiant KV laissé à
remplir y ferait échouer le déploiement de la page.

### Pourquoi c'est gratuit, et le reste

Deux verrous. Sur le plan Workers Free, Cloudflare refuse l'appel au-delà de
10 000 neurones par jour au lieu de le facturer. Et la fonction s'arrête
d'elle-même à 9 000, comptés appel par appel aux tarifs relevés le
2026-10-11 (`agent/fournisseurs.js`). Un autre fournisseur que Workers
AI est refusé : brancher un modèle payant doit être une décision, pas une
variable.

KV n'écrit que deux fois par appel — quota et comptabilité, journal compris —
parce que le plan gratuit plafonne à mille écritures par jour ; le cache des
réponses vit dans l'API Cache, gratuite et sans quota d'écriture. L'adresse IP
n'est jamais stockée, seulement son empreinte salée.

### Tests

`tests/test_agent.py` vérifie les trente questions de niveau 0, le moteur et le
panneau, en ligne compris face à un serveur simulé ; `tests/test_regles.py`
les règles, le report déficitaire et le passage VE → fonds propres ;
`tests/test_fonctions.py` lance les tests Node des fonctions serveur — le Node
embarqué par Playwright suffit. La mesure des modèles réels se fait sur le site
déployé : `python tests/mesurer_agent.py`, résultats dans `tests/RESULTATS.md`.
