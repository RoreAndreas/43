# Atelier Pagne

Prototype d’un site de couture : choisir un modèle, l’habiller d’un pagne et
voir le résultat en 3D. Le plan complet est dans [PLAN.md](PLAN.md).

## Lancer en local

Les modules JavaScript exigent un petit serveur (ouvrir le fichier directement
ne marche pas) :

```bash
cd AtelierPagne
python3 -m http.server 8000
```

Puis ouvrir <http://localhost:8000/> (accueil) ou
<http://localhost:8000/essayage.html> (salle d’essayage).

Three.js r170 est fourni dans `vendor/three/` (licence MIT) : aucune connexion
n’est nécessaire, à part les polices Google Fonts (avec repli système).

## Mannequin

Le corps du mannequin vient du maillage de base **MakeHuman** (cibles de
morphologie et poids du squelette compris), publié sous licence **CC0**
(domaine public) par la communauté MakeHuman. Pour régénérer les fichiers de
`assets/mannequin/` (télécharge les données sources dans `tools/.cache/`) :

```bash
python3 tools/build_mannequin.py
```

