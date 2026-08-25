# wacc43 — Coût moyen pondéré du capital

Calcul du CMPC par la méthode indirecte, à partir des bases Damodaran et de la
courbe des taux US Treasury.

La plateforme est **une page statique** : les données de marché (~21 Ko) sont
embarquées dans le fichier HTML et les formules s'appliquent dans le navigateur.
Aucun serveur à faire tourner, donc aucun coût d'hébergement et rien à
surveiller.

## Organisation

```
PFILES/
├── moteur/          le code Python : téléchargement, calcul, construction, export
├── presentation/    le gabarit — CSS, markup et formules en JavaScript
├── site/            le livrable publié par Cloudflare Pages (index.html)
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

## Aperçu local et export Excel

```powershell
python moteur/serve.py
```

Sert la page avec les données du jour sur <http://localhost:8000>, sans passer
par un build. Il expose aussi `/export.xlsx?country=…&industry=…`, le classeur
Excel, qui réclame Python et n'existe donc pas dans la version statique.

## Partager la page

`site/index.html` est autonome : il s'envoie par e-mail ou Teams et fonctionne
hors ligne. Les paramètres voyagent dans l'URL
(`?country=France&industry=Advertising&year=2026`), donc copier l'URL partage la
configuration. Les noms sans accent ni casse exacte sont résolus
automatiquement.

## Méthode

```
a     = taux US Treasury (moyenne annuelle) + prime de risque pays
b     = beta désendetté × (1 + D/E × (1 − t))
Re    = a + b × c + d + e                    coût des fonds propres (MEDAF)
Rd    = (spread + a) × (1 − t)               coût de la dette après impôt
WACC  = E/V × Re + D/V × Rd
CMPC  = (1 + WACC) × (1 + infl. locale) / (1 + infl. référence) − 1
local
```

`c` : prime de risque d'un marché mature (Damodaran). `d` et `e` : primes de
taille et spécifique, saisies dans l'interface. `E/V = 1/(1 + D/E)`.

Sous référentiel BRVM, le taux sans risque vient de la courbe souveraine de
l'État retenu, publiée chaque semaine par UMOA-Titres. Il porte déjà le risque
pays : aucune prime ne s'y ajoute, et le coût du capital qui en découle est
directement en monnaie locale. La profondeur des courbes va de 7 ans (Niger,
Guinée-Bissau) à 15 ans (Côte d'Ivoire, Sénégal, Togo).

Couverture : 157 pays et 94 industries. 23 pays n'ont pas de taux d'IS dans la
base Damodaran — le calcul retient alors 25 %, et la page l'indique sous les
tuiles de marché.

> Les formules existent en deux exemplaires : en JavaScript dans le gabarit,
> pour la page, et en Python dans `moteur/wacc_core.py`, pour l'export Excel.
> Toute modification de la méthode doit être portée des deux côtés.
