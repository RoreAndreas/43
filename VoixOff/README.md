# VoixOff — portfolio

Site vitrine d'un comédien voix off : vidéos YouTube lues directement sur la
page, fichiers vidéo, extraits audio avec leur forme d'onde.

C'est **une page statique** (HTML, CSS, JavaScript), sans étape de
construction : on dépose le dossier `site/` chez un hébergeur et c'est en
ligne. Le projet est indépendant de WACC43 et du reste du dépôt.

```
VoixOff/
├── site/                le dossier publié, tel quel
│   ├── contenu.js       ← le seul fichier à modifier
│   ├── medias/          vos fichiers audio, vidéo et images
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── favicon.svg
└── README.md
```

## Ajouter un travail

Tout se passe dans `site/contenu.js`. Chaque travail est un bloc de la liste
`travaux`, affichés dans l'ordre :

```js
{
  titre: "Spot radio — été",
  client: "Marque",
  categorie: "Publicité",          // crée le filtre du même nom
  annee: 2026,
  lien: "https://youtu.be/XXXXXXXXXXX",
},
```

Le type de média se déduit du lien :

| Lien | Affichage |
|---|---|
| `https://www.youtube.com/watch?v=…`, `https://youtu.be/…`, `…/shorts/…` | la vignette s'agrandit en plein écran et la vidéo s'y lit |
| `medias/film.mp4` (ou `.webm`, `.mov`) | même lecture plein écran, sans passer par YouTube |
| `medias/demo.mp3` (ou `.wav`, `.m4a`, `.ogg`) | lecture sur place, forme d'onde cliquable |

Champs facultatifs : `description` (affichée pendant la lecture), `image`
(vignette personnalisée, conseillée pour les fichiers vidéo), `duree`
(`"0:30"`, affichée sur la vignette), `vedette: true` (le travail passe en grand
en tête de page — une bande démo, par exemple).

En haut du fichier : nom, métier, accroche, paragraphe « À propos », courriel,
téléphone, liens (LinkedIn, Instagram…) et thème (`"auto"`, `"clair"` ou
`"sombre"`).

Les liens fournis sont des **exemples** (courts métrages libres de la Blender
Foundation) et `medias/exemple-audio.mp3` est un murmure de synthèse : à
remplacer par vos travaux, puis à supprimer.

**YouTube.** La vidéo doit autoriser l'intégration (réglage par défaut). Une
vidéo « non répertoriée » fonctionne, une vidéo « privée » non.

## Voir le site en local

Ouvrir `index.html` par double-clic affiche la page, mais les navigateurs y
bloquent une partie des lecteurs : YouTube refuse de démarrer et la forme
d'onde ne se dessine pas. Mieux vaut un petit serveur :

```powershell
cd VoixOff/site
python -m http.server 8000
```

puis <http://localhost:8000>. Le serveur de Python ne permet pas d'avancer
dans un audio en cliquant sur la forme d'onde ; en ligne, cela fonctionne.

## Mettre en ligne (Cloudflare Pages)

Même hébergeur que la page WACC43 : gratuit, et chaque `git push` met le site
à jour.

1. Cloudflare → *Workers & Pages* → *Create* → *Pages* → connecter le dépôt
   GitHub `RoreAndreas/43`.
2. Réglages de construction :
   - *Framework preset* : **None**
   - *Build command* : laisser vide
   - *Build output directory* : **`VoixOff/site`**
3. Une fois le projet créé : *Settings* → *Builds & deployments* → *Build
   watch paths* → *Include paths* : **`VoixOff/*`**.

   Ce dernier réglage compte : les robots du dépôt poussent des données de
   marché plusieurs fois par heure. Sans ce filtre, chacun de ces commits
   relancerait un déploiement du portfolio et épuiserait vite le quota
   mensuel de constructions.
4. *Custom domains* pour brancher votre nom de domaine.

Cloudflare Pages refuse les fichiers de plus de 25 Mo : les vidéos longues
vont sur YouTube (en « non répertoriée » si besoin), les extraits audio en MP3
restent bien en dessous.

Pour le partage sur les réseaux sociaux et les moteurs de recherche, les
balises `<title>`, `description` et `og:` en tête de `index.html` sont à
personnaliser : elles sont lues avant que la page ne charge `contenu.js`.

## Comportement

- **Théâtre.** Au clic, la vignette s'envole et devient le lecteur ; à la
  fermeture, elle revient se poser à sa place. Flèches ← → (ou glisser sur
  mobile) pour passer d'une vidéo à l'autre, Échap ou le bouton retour du
  téléphone pour fermer. Chaque vidéo a son adresse (`…/#/titre-du-travail`),
  à envoyer directement à un client.
- **Un seul son à la fois.** Lancer un extrait ou une vidéo éteint le
  précédent en fondu.
- **Lecteur flottant.** Si l'on fait défiler la page pendant l'écoute d'un
  extrait, une pastille reste en bas de l'écran pour le mettre en pause ou y
  revenir.
- **Filtres.** Les catégories des travaux deviennent des filtres ; les cartes
  glissent vers leur nouvelle place.
- Thème clair ou sombre selon l'appareil, animations coupées pour les
  visiteurs qui limitent les mouvements, navigation complète au clavier.
