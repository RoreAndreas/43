# Foulée — trace tes runs sur Google Maps

Planificateur de parcours de course à pied, design sombre. On pose un
**départ**, des **étapes** et une **arrivée** sur la carte (ou on part de sa
position), Foulée calcule l'itinéraire piéton, la distance, le dénivelé, et
l'**allure** à tenir pour finir dans le temps visé. Le parcours s'exporte en
**affiche PNG** prête à partager, ou en **GPX** pour la montre.

Page statique, projet indépendant des autres dossiers du dépôt.

```
Foulee/
├── site/              le dossier publié, tel quel
│   ├── index.html
│   ├── style.css
│   ├── app.js         carte, points, itinéraire, allure, GPX
│   ├── poster.js      l'affiche PNG (1080 × 1350)
│   ├── config.js      ← réglages : clé Google Maps, centre par défaut
│   └── favicon.svg
└── serve.py           aperçu local
```

## Lancer

```bash
cd Foulee
python serve.py
```

puis ouvrir <http://localhost:8000>. La géolocalisation n'est permise par
les navigateurs que sur `https://` ou `localhost` : ouvrir `index.html`
directement (`file://`) ne la donnerait pas.

Pour publier (Cloudflare Pages, GitHub Pages, Netlify…), servir le dossier
`site/` tel quel, en https.

## La clé Google Maps

Foulée appelle Google directement depuis le navigateur, avec ta clé.

1. [Console Google Cloud](https://console.cloud.google.com/google/maps-apis/credentials) → créer une clé API (un compte de facturation est exigé ; le crédit mensuel gratuit couvre largement un usage perso).
2. Activer les API :

   | API | Sert à | Sans elle |
   |---|---|---|
   | Maps JavaScript API | la carte | rien ne marche |
   | Routes API | l'itinéraire piéton | repli sur Directions API, sinon ligne droite |
   | Geocoding API | le nom des points, la recherche | coordonnées à la place des adresses |
   | Places API (New) | la recherche de lieux | repli sur Geocoding |
   | Elevation API | le D+ et le profil | pas de dénivelé |
   | Maps Static API | le fond de carte de l'affiche | affiche stylisée sans carte |

3. **Restreindre la clé** : *Restrictions d'application → Sites web*, avec
   `http://localhost:8000/*` et l'adresse du site publié.

Deux façons de la donner à Foulée :

- la saisir au premier lancement (bouton ⚙) : elle est gardée dans le
  navigateur, rien dans le dépôt ;
- ou l'écrire dans `site/config.js` (`googleMapsApiKey`) : pratique pour un
  site publié, mais le fichier est public — d'où la restriction par site.

## Utilisation

- **Tape sur la carte** : le premier point est le départ 🟢, le dernier
  l'arrivée 🏁, ceux du milieu les étapes. Les repères se **glissent** pour
  ajuster ; la liste permet de les renommer, réordonner, supprimer.
- **📍 Partir d'ici** place le départ sur ta position. Ta position est
  suivie en direct (point bleu).
- **Boucle** : l'arrivée revient au départ.
- **Chemins / Ligne droite** : itinéraire piéton de Google, ou tracé direct
  entre les points (piste, sentier non cartographié).
- **Allure** : saisir le temps visé calcule l'allure /km, et inversement ;
  les pastilles donnent des allures types. Vitesse, temps à mi-parcours,
  heure d'arrivée et temps de passage à chaque km suivent.
- **Exporter en PNG** : affiche avec le tracé, distance, temps visé, allure,
  vitesse, dénivelé et profil. Quatre ambiances de couleurs, fond de carte
  Google ou version stylisée. Sur mobile, bouton *Partager*.
- **GPX** : le tracé et les points, à importer dans Garmin Connect, Strava,
  Coros, Suunto…

Le parcours en cours est gardé dans le navigateur (localStorage) : il est
là au retour. ↶ (ou Ctrl+Z) annule la dernière modification.

Limite : 27 points par parcours (départ, arrivée et 25 étapes, le maximum
de Google pour un trajet à pied).
