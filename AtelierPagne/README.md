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
