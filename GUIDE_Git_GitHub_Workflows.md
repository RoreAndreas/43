# 📚 Cours : Git, GitHub et les Workflows (adapté à ton projet BRVM × SikaFinance)

Ce document explique **ce qui se passe réellement** quand tu fais "commit" et "push"
dans VS Code, comment ton code local est relié à GitHub, et comment le robot qui met
à jour tes données toutes les 15 minutes fonctionne.

---

## 1. Les trois "endroits" où vit ton code

Il faut d'abord bien distinguer **trois zones différentes**. C'est la clé de tout.

```
   [ Ton PC ]                          [ Internet ]
                                        
   ┌─────────────────────┐             ┌──────────────────────┐
   │  1. Working directory│             │                      │
   │  (tes fichiers)      │             │   3. GitHub          │
   │        ↓ git add     │  git push   │   github.com/        │
   │  2. Staging + Repo   │ ──────────► │   RoreAndreas/43     │
   │     local (.git)     │ ◄────────── │   (le "remote")      │
   └─────────────────────┘  git pull   └──────────────────────┘
```

1. **Working directory** = les fichiers que tu vois et modifies dans VS Code
   (`app.py`, `update_data.yml`, etc.).

2. **Dépôt local** = un dossier caché `.git` **dans ton projet**. Il contient
   TOUT l'historique de ton projet, sur ton PC. C'est lui qui garde la mémoire
   de chaque version.

3. **GitHub (le "remote")** = une copie de ton dépôt hébergée sur les serveurs
   de GitHub, accessible par internet. Dans ton cas :
   `https://github.com/RoreAndreas/43`. On l'appelle `origin`.

> 💡 Point crucial : **modifier un fichier ne l'envoie PAS sur GitHub.**
> Il faut explicitement le "commiter" puis le "pousser". Tant que tu ne fais
> pas ça, tes changements restent uniquement sur ton PC.

---

## 2. Le cycle de base : add → commit → push

### Étape A — `git add` (préparer / "stage")
Tu dis à git : *"ces fichiers-là, je veux les inclure dans ma prochaine sauvegarde."*
Dans VS Code, c'est le petit **`+`** à côté du fichier dans l'onglet **Source Control**.

### Étape B — `git commit` (enregistrer une version)
Un **commit** = une **photo instantanée** de tes fichiers à un moment donné,
avec un **message** qui décrit ce que tu as changé.

- C'est enregistré **dans ton dépôt local** (`.git`), pas encore sur GitHub.
- Chaque commit a un identifiant unique (ex: `18faf7d`) et garde le lien vers
  le commit précédent → cela forme un historique, comme une pile de photos.
- Le message est important : `"Passage du cron à 15 min"` est utile,
  `"maj"` ne l'est pas.

Dans VS Code : tu écris le message dans le champ en haut, puis clic sur **✓ Commit**.

### Étape C — `git push` (envoyer sur GitHub)
Le **push** prend tous les commits locaux que GitHub ne connaît pas encore et les
**envoie sur `origin`** (GitHub). C'est SEULEMENT à ce moment que ton travail
devient visible en ligne et déclenche les workflows.

Dans VS Code : bouton **Sync Changes** (ou "Push") après le commit.

### Résumé imagé
| Action    | Ce que ça fait                         | Où ça va          |
|-----------|----------------------------------------|-------------------|
| `add`     | choisit les fichiers à sauvegarder     | zone de préparation |
| `commit`  | crée une version datée + message       | dépôt local (PC)  |
| `push`    | publie les commits                     | GitHub (internet) |

---

## 3. `git pull` : le sens inverse

`git pull` = **récupérer** sur ton PC les commits qui existent sur GitHub mais
pas encore chez toi.

**Pourquoi c'est important dans TON projet :** ton robot GitHub Actions crée des
commits automatiquement (toutes les 15 min) directement sur GitHub. Donc GitHub a
souvent des commits que ton PC n'a pas.

> ⚠️ Situation actuelle : ton dépôt local est **"behind origin/main by 1 commit"**
> (en retard d'un commit). Avant de pousser tes changements, fais un **`git pull`**
> (bouton Sync dans VS Code) pour récupérer d'abord ce commit du robot, sinon le
> push sera refusé. Règle d'or : **pull avant push** quand un robot travaille aussi.

---

## 4. Le lien PC ↔ GitHub : le "remote"

Ce lien est configuré une seule fois (déjà fait pour toi). On peut le voir avec :

```
git remote -v
→ origin  https://github.com/RoreAndreas/43 (fetch)
  origin  https://github.com/RoreAndreas/43 (push)
```

- `origin` = le surnom de ton GitHub.
- `main` = le nom de ta **branche** principale (la ligne de développement).
- Quand tu push, tu envoies `main` (local) vers `origin/main` (GitHub).

---

## 5. Les Workflows GitHub Actions (le robot automatique)

C'est la partie "magique" de ton projet. GitHub peut **exécuter du code tout seul**
sur ses propres serveurs, sans que ton PC soit allumé. C'est ce qu'on appelle
**GitHub Actions**, et ça se configure avec un fichier **workflow**.

### Où ?
Le fichier : `.github/workflows/update_data.yml`
GitHub détecte automatiquement tout fichier `.yml` dans ce dossier spécial.

### Décryptage de TON workflow, ligne par ligne

```yaml
name: Update market data          # Nom affiché dans l'onglet "Actions" de GitHub

on:                               # QUAND déclencher le robot ?
  schedule:
    - cron: '*/15 * * * *'        #   → automatiquement toutes les 15 minutes
  workflow_dispatch:              #   → + un bouton pour le lancer à la main

jobs:
  scrape:                         # Un "job" = une tâche à exécuter
    runs-on: ubuntu-latest        # Sur quelle machine ? Un PC Linux loué par GitHub

    steps:                        # La liste des étapes, dans l'ordre :
      - uses: actions/checkout@v3          # 1. Télécharge ton code sur la machine
      - uses: actions/setup-python@v4      # 2. Installe Python 3.11
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt   # 3. Installe les librairies
      - run: python BRVM/brvm_scraper.py       # 4. Lance le scraper BRVM
      - run: python RICHBOURSE/richbourse_scraper.py  # 5. Scraper RichBourse
      - run: python SIKAPRO/sikapro_scraper.py        # 6. Scraper SikaFinance
      - run: |                             # 7. Le robot COMMIT et PUSH les données
          git add BRVM/*.json RICHBOURSE/*.json SIKAPRO/*.json
          git commit -m "🔄 Update market data (automated)"
          git push
```

### Le point le plus important à comprendre
Le robot fait **exactement le même cycle que toi** : il lance tes scrapers, ce qui
régénère les fichiers `.json`, puis il fait `git add` → `git commit` → `git push`.
**C'est pour ça que des commits apparaissent tout seuls sur GitHub.** Le robot est,
en pratique, un "collègue" qui commit à ta place toutes les 15 minutes.

### Le format `cron` (la fréquence)
`'*/15 * * * *'` — cinq champs séparés par des espaces :

```
 *      *      *      *      *
minute heure  jour   mois  jour-semaine
```

- `*/15 * * * *` = toutes les 15 minutes
- `0 * * * *`    = toutes les heures pile
- `0 9 * * *`    = tous les jours à 9h (heure **UTC**, donc ~10h/11h en France)
- `0 9 * * 1-5`  = du lundi au vendredi à 9h

> ⏰ Attention : GitHub utilise l'heure **UTC**, pas l'heure française.

---

## 6. Le flux complet de TON projet, de bout en bout

```
  ┌────────────────────────────────────────────────────────────┐
  │  Toutes les 15 min, sur les serveurs de GitHub :            │
  │                                                             │
  │   Scrapers ──► fichiers .json ──► git commit ──► git push   │
  │   (BRVM,        (données          (le robot      (sur       │
  │    Sika,         fraîches)         enregistre)    GitHub)   │
  └───────────────────────────┬────────────────────────────────┘
                              │ push met à jour le repo
                              ▼
  ┌────────────────────────────────────────────────────────────┐
  │  Streamlit Cloud surveille ton repo GitHub :                │
  │   dès qu'il change, il relance ton app.py, qui relit les    │
  │   .json ──► le tableau BRVM × SikaFinance est à jour.       │
  └────────────────────────────────────────────────────────────┘
```

Donc : **le robot met à jour les données sur GitHub → Streamlit lit ces données
depuis GitHub → ton site affiche des chiffres frais**, sans que tu touches à rien.

Toi, de ton côté, tu n'interviens que pour modifier le **code** (`app.py`, le cron,
un scraper) : tu édites → tu commit → tu push, et Streamlit se met à jour.

---

## 7. Aide-mémoire (à garder sous la main)

| Je veux...                                  | Action dans VS Code                    |
|---------------------------------------------|----------------------------------------|
| Sauvegarder mon fichier                     | `Ctrl+S`                               |
| Voir ce que j'ai changé                     | Onglet **Source Control** (les "M")    |
| Préparer un fichier                         | `+` à côté du fichier                   |
| Créer une version                           | Message + bouton **✓ Commit**          |
| Envoyer sur GitHub                          | **Sync Changes** / Push                 |
| Récupérer les commits du robot              | **Sync** / Pull (à faire AVANT de push)|
| Changer la fréquence du robot               | Éditer la ligne `cron` du `.yml`       |
| Voir les exécutions du robot                | GitHub → onglet **Actions**            |

### Le réflexe qui évite 90 % des problèmes
> **Pull → (modifier) → Save → Commit → Push.**
> Toujours *pull* d'abord quand un robot commit en parallèle du tien.

---

*Document généré pour le projet Analyse BRVM × SikaFinance PRO.*
