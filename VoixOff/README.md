# VoixOff — portfolio

Portfolio voix off d'Anne-Katy MILIDJI. L'accueil montre une photo par
rubrique (Corporate, Documentaire, Piste audio) ; au clic, la photo
s'installe dans le lecteur et la liste des réalisations apparaît à côté,
sur la même ligne. Le bouton « Retour », en haut à gauche, ramène aux trois
photos.

Page statique, projet indépendant de WACC43.

```
VoixOff/
├── site/                     le dossier publié, tel quel
│   ├── realisations/         ← vos réalisations
│   │   ├── Corporate/        ← déposez-y vidéos et audios
│   │   ├── Documentaire/
│   │   ├── Piste audio/
│   │   └── youtube.txt       ← vos liens YouTube
│   ├── catalogue.json        la liste des réalisations, écrite par inventaire.py
│   ├── contenu.js            réglages : nom, réseaux, rubriques
│   ├── medias/               photos des rubriques
│   └── index.html, style.css, app.js, favicon.svg
├── inventaire.py             dresse le catalogue
└── serve.py                  aperçu local
```

## Ajouter une réalisation

Deux sources, rien d'autre à modifier.

**Un fichier.** Déposez la vidéo ou l'audio dans le dossier de sa rubrique,
sous `site/realisations/`. Le nom du fichier devient le titre :
« Film institutionnel.mp4 » s'affiche « Film institutionnel ». Un numéro en
tête fixe l'ordre et ne s'affiche pas : « 01 - Film institutionnel.mp4 ».
Formats : `.mp4` conseillé (aussi `.webm`, `.mov`) ; `.mp3` conseillé (aussi
`.wav`, `.m4a`). 25 Mo au plus par fichier, limite de l'hébergeur.

**Un lien YouTube.** Ajoutez-le à `site/realisations/youtube.txt`, sous le
nom de sa rubrique entre crochets :

```
[Corporate]
https://www.youtube.com/watch?v=XXXXXXXXXXX
Mon titre | https://youtu.be/XXXXXXXXXXX
```

Le titre affiché est celui de la vidéo sur YouTube ; pour en choisir un
autre, écrivez-le avant le lien, séparé par `|`. La vidéo doit autoriser
l'intégration (réglage par défaut) : « non répertoriée » fonctionne,
« privée » non.

Dans chaque rubrique, les fichiers viennent d'abord, puis les vidéos
YouTube dans l'ordre du fichier.

Les liens actuels de `youtube.txt` (films libres de la Blender Foundation)
et les trois audios « (exemple) », murmures de synthèse, ne sont là que pour
montrer le lecteur : remplacez-les par vos réalisations.

## Le catalogue

Un site hébergé ne peut pas lister le contenu d'un dossier : `inventaire.py`
le fait pour lui et écrit `site/catalogue.json`, à ne pas modifier à la main.
Il se relance tout seul :

- en local, à chaque chargement de la page servie par `serve.py` : un
  fichier déposé apparaît au simple rechargement ;
- en ligne, à chaque mise en ligne, avec la commande de construction de
  Cloudflare Pages ci-dessous.

Il garde les titres YouTube déjà obtenus : une construction hors ligne ne
les perd pas. Pour le relancer à la main : `python VoixOff/inventaire.py`,
qui signale aussi les liens illisibles et les fichiers trop lourds.

## Réglages

`site/contenu.js` : nom, titre, courriel, réseaux, et pour chaque rubrique
son titre, son dossier, sa phrase d'introduction, sa photo et son cadrage.
La même photo est recadrée en hauteur sur l'accueil et en largeur dans la
rubrique : `cadrage` indique le point à garder visible, position horizontale
puis verticale (`"38% 30%"` ; `"50% 50%"` par défaut, le centre).

Les photos se préparent pour le web avant d'être déposées dans
`site/medias/` : environ 2 500 px de côté, en JPEG, sans métadonnées (les
photos d'appareil peuvent contenir la position GPS).

Les couleurs se règlent en tête de `site/style.css` : fond noir (`--fond`),
cadres (`--surface`, `--tuile`), accent bleu (`--bleu`), arrondi des photos
et des cadres (`--rayon`).

## Aperçu local

```powershell
python VoixOff/serve.py
```

puis <http://localhost:8000> (dans VS Code : `Ctrl+Shift+P` → *Simple
Browser: Show*). Ouvrir `index.html` par double-clic ne suffit pas : le
navigateur y refuse de lire le catalogue.

## Mise en ligne (Cloudflare Pages)

Projet Pages relié au dépôt 43 :

- *Framework preset* : **None**
- *Build command* : **`python3 VoixOff/inventaire.py`**
- *Build output directory* : **`VoixOff/site`**
- *Build watch paths* : **`VoixOff/*`** — sans ce filtre, les commits
  automatiques des données de marché redéploieraient le portfolio en boucle.

Cloudflare Pages refuse les fichiers de plus de 25 Mo : les vidéos longues
vont sur YouTube, en « non répertoriée » si besoin, et `youtube.txt` les
présente au même titre que les fichiers.
