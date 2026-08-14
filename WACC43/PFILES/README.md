# wacc43 — Coût moyen pondéré du capital

Calcul du CMPC par la méthode indirecte, à partir des bases Damodaran et de la
courbe des taux US Treasury.

La plateforme est **une page statique** : les données de marché (~21 Ko) sont
embarquées dans le fichier HTML et les formules s'appliquent dans le navigateur.
Aucun serveur à faire tourner, donc aucun coût d'hébergement et rien à
surveiller.

## Construire la page

```powershell
pip install -r requirements.txt
python build_static.py
```

Le script télécharge les sources, les condense et écrit `site/index.html`
(~60 Ko, autonome). Compter environ deux minutes, l'essentiel étant les taux
Treasury (une requête par année et par maturité).

À relancer quand Damodaran publie sa mise à jour annuelle, en janvier. Un
rebuild trimestriel est préférable si l'exercice en cours vous intéresse : son
taux Treasury est figé à la date de construction.

## Mettre en ligne

Le fichier `site/index.html` se dépose tel quel sur n'importe quel hébergement
statique gratuit : Cloudflare Pages, GitHub Pages, Netlify. Pour restreindre
l'accès, Cloudflare Access ajoute un écran de connexion par e-mail, gratuit
jusqu'à 50 utilisateurs.

Il s'envoie aussi par e-mail ou Teams : le destinataire l'ouvre dans son
navigateur, sans installation, et peut changer les paramètres — la page
fonctionne hors ligne.

Les paramètres voyagent dans l'URL
(`?country=France&industry=Advertising&year=2026`) : copier l'URL partage la
configuration. Les noms sans accent ni casse exacte sont résolus
automatiquement.

## Serveur local

```powershell
python serve.py
```

Sert la page avec les données du jour sur <http://localhost:8000>, sans passer
par un build. Il expose aussi `/export.xlsx?country=…&industry=…`, le classeur
Excel, qui réclame Python et n'existe donc pas dans la version statique.

## Organisation

| Fichier | Rôle |
|---|---|
| `build_static.py` | Construit `site/index.html` — le livrable |
| `templates/wacc_value_tab.html` | Présentation **et** formules en JavaScript |
| `wacc_core.py` | Téléchargement des sources, condensation, formules Python |
| `wacc_html.py` | Injecte le jeu de données dans le gabarit |
| `serve.py` | Prévisualisation locale et export Excel |
| `get_us_bond_rate.py` | Moyenne annuelle des taux US Treasury |
| `export_wacc.py` | Génération du classeur Excel |
| `archive/` | Scripts antérieurs, hors application |

> Les formules existent en deux exemplaires : en JavaScript dans le gabarit,
> pour la page, et en Python dans `wacc_core.py`, pour l'export Excel. Toute
> modification de la méthode doit être portée des deux côtés. Le script de test
> compare les deux implémentations sur plusieurs jeux de paramètres.

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

Couverture des données : 157 pays et 94 industries. 23 pays n'ont pas de taux
d'IS dans la base Damodaran — le calcul retient alors 25 %, et la page l'indique
sous les tuiles de marché.
