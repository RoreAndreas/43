# VoixOff — portfolio

Portfolio d'Anne-Katy MILIDJI, responsable marketing & communication et voix
off professionnel. L'accueil montre trois cadres :

1. **Présentation** — un carrousel : les images défilent seules sur l'accueil,
   puis en grand quand on ouvre le cadre, avec leur sommaire à côté ;
2. **Expériences et réalisations** — vidéos, audios, images, liens YouTube ;
3. **Voix off** — audios, vidéos, liens YouTube.

Au clic, le visuel du cadre s'installe dans le lecteur et la liste apparaît
à côté, sur la même ligne. Le bouton « Retour », en haut à gauche, ramène aux
trois cadres.

Page statique, projet indépendant de WACC43.

```
VoixOff/
├── site/                                    le dossier publié, tel quel
│   ├── cadres/                              ← le contenu, un dossier par cadre
│   │   ├── 1 - Présentation/                ← les images du carrousel
│   │   ├── 2 - Expériences et réalisations/ ← vidéos, audios, images
│   │   ├── 3 - Voix off/                    ← audios, vidéos
│   │   └── youtube.txt                      ← les liens YouTube
│   ├── catalogue.json     la liste du contenu, écrite par inventaire.py
│   ├── contenu.js         réglages : nom, titre, réseaux, cadres
│   ├── medias/            photos des cadres 2 et 3
│   └── index.html, style.css, app.js, favicon.svg
├── inventaire.py          dresse le catalogue
└── serve.py               aperçu local
```

## Ajouter du contenu

Deux sources, rien d'autre à modifier.

**Un fichier.** Déposez-le dans le dossier de son cadre, sous `site/cadres/`.
Le nom du fichier devient le titre : « Film institutionnel.mp4 » s'affiche
« Film institutionnel ». Un numéro en tête fixe l'ordre et ne s'affiche pas :
« 01 - Film institutionnel.mp4 ». Sans numéro, les noms sont triés comme on
les lit : « Diapositive2 » avant « Diapositive10 ».

- Présentation : des images, une par diapositive (`.png`, `.jpg`, `.webp`).
  Depuis PowerPoint : *Fichier › Exporter › Changer le type de fichier ›
  PNG*, « Toutes les diapositives » ; depuis Canva : *Partager › Télécharger
  › PNG*. L'image s'affiche en entier, sur un fond flou tiré d'elle-même
  quand elle ne remplit pas le cadre.
- Expériences et réalisations, Voix off : vidéos (`.mp4` conseillé, aussi
  `.webm`, `.mov`), audios (`.mp3` conseillé, aussi `.wav`, `.m4a`),
  images.

25 Mo au plus par fichier, limite de l'hébergeur.

**Un lien YouTube.** Ajoutez-le à `site/cadres/youtube.txt`, sous le nom de
son cadre entre crochets :

```
[Voix off]
https://www.youtube.com/watch?v=XXXXXXXXXXX
Mon titre | https://youtu.be/XXXXXXXXXXX
```

Le titre affiché est celui de la vidéo sur YouTube ; pour en choisir un
autre, écrivez-le avant le lien, séparé par `|`. La vidéo doit autoriser
l'intégration (réglage par défaut) : « non répertoriée » fonctionne,
« privée » non. Dans chaque cadre, les fichiers viennent d'abord, puis les
vidéos YouTube dans l'ordre du fichier.

Les liens actuels de `youtube.txt` (films libres de la Blender Foundation),
les trois diapositives « (exemple) » et les trois audios « (exemple) »,
murmures de synthèse, ne sont là que pour montrer les lecteurs : remplacez-les
par votre contenu.

## Le catalogue

Un site hébergé ne peut pas lister le contenu d'un dossier : `inventaire.py`
le fait pour lui et écrit `site/catalogue.json`, à ne pas modifier à la main.

- En local, `serve.py` le refait à chaque chargement de la page : un fichier
  déposé apparaît au simple rechargement.
- En ligne, le site sert le `catalogue.json` du dépôt : il doit avoir été
  refait après tout ajout, ce que fait l'aperçu local, ou `python
  VoixOff/inventaire.py`. Pour que Cloudflare le refasse lui-même à chaque
  mise en ligne, voir la commande de construction ci-dessous.

Il garde les titres YouTube déjà obtenus, pour qu'une construction hors
ligne ne les perde pas, et signale les liens illisibles, les fichiers trop
lourds et les dossiers mal nommés.

## Réglages

`site/contenu.js` : nom, titre (deux métiers séparés par « / », chacun sur sa
ligne sous le nom), courriel, réseaux, et pour chaque cadre son titre, son
dossier, son affichage (`"carrousel"` ou liste), sa phrase d'introduction,
sa photo et son cadrage. Un carrousel dont les images sont des photos plutôt
que des diapositives peut les recadrer pour remplir le cadre :
`ajustement: "couvrir"`.

La même photo est recadrée en hauteur sur l'accueil et en largeur dans le
cadre ouvert : `cadrage` indique le point à garder visible, position
horizontale puis verticale (`"50% 72%"` ; `"50% 50%"` par défaut, le centre).
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
navigateur y refuse de lire le catalogue. Après une modification d'`inventaire.py`
ou de `serve.py`, relancez le serveur : il garde l'ancienne version en mémoire.

## Mise en ligne (Cloudflare Workers)

Le site est un Worker Cloudflare (`annekatysportfolio`), relié au dépôt 43
avec `VoixOff` pour dossier racine : chaque `git push` sur `main` qui touche
`VoixOff/` le redéploie. Cloudflare y a détecté seul le dossier `site/`,
servi à la racine de l'adresse.

Pour que le catalogue soit refait à chaque mise en ligne, sans dépendre de
l'aperçu local : *Workers & Pages › annekatysportfolio › Settings › Build ›
Build command* : **`python3 inventaire.py`** (Python 3.13 est installé dans
l'environnement de construction).

Cloudflare refuse les fichiers de plus de 25 Mo : les vidéos longues vont
sur YouTube, en « non répertoriée » si besoin, et `youtube.txt` les présente
au même titre que les fichiers.

Constaté sur le site en ligne : Cloudflare répond à une demande partielle
(`Range`) par le fichier entier. Chrome et Firefox lisent quand même les
audios et vidéos déposés ; Safari (iPhone, Mac) exige ces réponses
partielles et risque de refuser de les lire. Les vidéos YouTube ne sont pas
concernées.
