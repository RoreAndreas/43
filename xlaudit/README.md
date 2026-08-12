# xlaudit

Outil Python en ligne de commande d'aide à l'audit de modèles financiers Excel
(`.xlsx` / `.xlsm`).

## Ce que fait l'outil, et ce qu'il ne fait pas

`xlaudit` produit des **signaux** : des faits vérifiables, chiffrés et tracés.
Telle cellule contient telle erreur ; telle plage balaie 9 lignes alors que le
bloc en compte 10 ; l'écart actif/passif vaut 1e-6 ; cette ligne n'a aucun
dépendant.

Il ne produit **jamais de constats d'audit**. Le tri des faux positifs, la
qualification erreur/convention, l'attribution de criticité et la rédaction
restent à l'auditeur, ou à un modèle de langage travaillant sur la sortie JSON.
Aucune heuristique de l'outil ne prétend décider si une anomalie est volontaire :
il classe par vraisemblance, expose les éléments de jugement, et s'arrête là.

Corollaire appliqué partout : **chaque signal contient tout ce qu'il faut pour
être jugé sans rouvrir le classeur** — la formule exacte, la formule majoritaire
du voisinage, l'écart chiffré sur toutes les colonnes, la liste des
consommateurs de la ligne.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11+. Dépendances : `openpyxl`, `pydantic`, `typer`, `rich`, `oletools`,
`pyyaml`, `networkx`. Pas de pandas dans le socle.

## Commandes

```
xlaudit scan MODELE.xlsm [--phases 1,2,3] [--rules R205,R215] [--mapping m.yaml] [--out signaux.json]
xlaudit discover MODELE.xlsm --out mapping.yaml
xlaudit validate-mapping MODELE.xlsm --mapping mapping.yaml
xlaudit ties MODELE.xlsm --mapping mapping.yaml
xlaudit trace MODELE.xlsm --cell "Onglet!S495" [--depth 3] [--direction up|down]
xlaudit map MODELE.xlsm --out carte.mmd
xlaudit feasibility MODELE.xlsm            # recalcul hors Excel possible ?
xlaudit sensitivity MODELE.xlsm --shock "production=-5%"
xlaudit report signaux.json --xlsx sortie.xlsx --md rapport.md
xlaudit diff v1.xlsm v2.xlsm               # non-régression
```

Toutes les commandes acceptent `--cache-dir`, `--no-cache` et `--refresh`.

### Parcours type

```bash
xlaudit scan modele.xlsm --phases 1,2 --out signaux.json   # sans mapping
xlaudit discover modele.xlsm --out mapping.yaml            # propose
$EDITOR mapping.yaml                                       # relire, corriger
xlaudit validate-mapping modele.xlsm --mapping mapping.yaml
xlaudit ties modele.xlsm --mapping mapping.yaml --out bouclages.json
xlaudit report signaux.json --xlsx constats.xlsx --md rapport.md
```

`trace` est la commande la plus utilisée en pratique :

```
$ xlaudit trace modele.xlsx --cell "Modele!D18" --depth 2
Trace precedents de Modele!D18
Modele!D18  Marge  =D10-D16  = 600
├── Modele!D10  Total produits  =SUM(D6:D9)  = 1 000
│   ├── Modele!D6  Produit A  = 100
│   └── Modele!D9  Produit D  = 400
└── Modele!D16  Total charges  =SUM(D12:D15)  = 400
```

## Les règles

### Phase 1 — cartographie

| Règle | Objet |
|---|---|
| R101 | Inventaire des onglets, fonctions, noms définis (portée globale **et** feuille), VBA, circularités |

### Phase 2 — formules

| Règle | Détection |
|---|---|
| R201 | Erreurs en cache (`#REF!`, `#DIV/0!`…), avec cause amont et cellule jumelle |
| R202 | Valeurs en dur isolées dans une ligne de formules |
| R203 | Variantes minoritaires de formule sur une ligne (normalisation R1C1) |
| R204 | Glissement de recopie : bornes qui avancent de +1 par ligne sur un bloc fixe |
| R205 | Ancrage asymétrique (`$O488:S491`) neutralisant un terme |
| R206 | Somme tronquée : entre colonnes, et contre l'étendue réelle du bloc |
| R207 | Plage de somme de forme différente de la plage de critères (SOMME.SI) |
| R208 | Nombre de termes additionnés variable d'une colonne à l'autre |
| R215 | Lignes calculées sans aucun dépendant — les **canaux débranchés** |

R204 à R208 sont la valeur ajoutée principale : ce sont les erreurs qu'aucune
erreur Excel ne signale.

### Phase 3 — bouclages (pilotés par mapping)

R301 implémente les dix invariants : bilan, cascade contre bilan, continuité
ouverture/clôture, amortissement intégral des dettes, intérêts = CRD × taux,
emplois = ressources, cohérence période/annuel (flux **et** stocks, règles
distinctes), drapeaux mutuellement exclusifs et contigus, immobilisations
bornées, non-négativité. S'y ajoute l'**analyseur de trésorerie négative** :
étage de bascule, état des mécanismes de couverture, et grandeur sur laquelle
leur signal de déclenchement est branché.

### Phases 4 et 5

| Règle | Objet |
|---|---|
| R401 | Comparateur de reconstitution : cache contre recalcul local |
| R402 | Extraction des chaînes de calcul menant aux sorties |
| R501 | Testeur de faisabilité du recalcul hors Excel |
| R502 | `calcPr` et fiabilité des valeurs en cache |
| R503 | Propagation statique d'un choc (étendue, sans chiffrage inventé) |

## Le chiffreur d'écart

Composant transverse appelé par R204 à R208. Sans lui, ces règles ne
produiraient que du bruit. Il reconstruit la grandeur sur **toutes** les
colonnes de projection en remplaçant la plage fautive par la plage attendue,
compare au cache, et rend un verdict :

- **actif** — l'écart est non nul aujourd'hui, le résultat est faux ;
- **latent** — l'écart est nul mais la zone en cause est peuplée : l'erreur
  mordra dès que ces cellules bougeront ;
- **nul** — la zone en cause est vide, aucun effet possible en l'état ;
- **indéterminé** — la formule sort du cadre reconstituable ; aucun chiffre
  n'est avancé.

L'évaluateur est volontairement restreint aux sommes algébriques de termes
(nombres, références, agrégats simples). Toute formule qui en sort rend
`indéterminé` plutôt qu'un chiffre faux — même principe que le testeur de
faisabilité.

Quand le chiffrage est `actif` **et** que la valeur en cache correspond
exactement à ce que produit la formule telle qu'écrite, R205 conclut à une
confiance de 1.0 : le cache confirme alors que l'écart constaté est bien le
terme neutralisé.

## La confiance

`confidence` est une aide au tri, jamais un verdict. Chaque règle documente son
calcul dans sa docstring. Rien n'est jamais filtré silencieusement : tous les
signaux sortent, triés par confiance décroissante.

## Pièges techniques traités dans le socle

Chacun a coûté des heures sur un audit réel (32 Mo, 34 onglets, 1,26 M de
formules), ou produit des résultats faux.

1. **Double chargement.** openpyxl ne rend jamais formules et valeurs ensemble :
   deux `load_workbook`, l'un `data_only=False`, l'autre `data_only=True`.
2. **`read_only=True`** dans les deux cas, sous peine de saturation mémoire.
3. **Cellules vides.** En lecture seule, ce sont des `EmptyCell` sans `.row` ni
   `.column`. Vérifié empiriquement en plus : `iter_rows()` sans bornes commence
   **ligne 1, colonne 1**, et non à `ws.min_row` / `ws.min_column` — un
   `enumerate(row, start=ws.min_column)` décalerait donc toutes les colonnes. La
   parade est de toujours passer des bornes explicites. Le tout est encapsulé
   une seule fois dans `core.loader.iter_cells`, et un test AST
   (`tests/test_no_direct_iter_rows.py`) interdit tout autre appel à `iter_rows`
   dans le paquet.
4. **Formules matricielles.** La valeur est un objet `ArrayFormula`, pas une
   chaîne : normalisée via `getattr(v, "text", v)`, sinon elles disparaissent
   silencieusement des scans.
5. **VBA.** `keep_vba=True` fait échouer les gros `.xlsm` : extraction séparée
   par `oletools.olevba`. Les plages nommées `*Copy` / `*Paste` révèlent les
   boucles de résolution de circularité et déclenchent une réserve.
6. **Noms définis à portée feuille.** `wb.defined_names` n'expose que la portée
   globale ; le XML est lu directement pour récupérer les noms à `localSheetId`.
7. **Recalcul hors Excel.** LibreOffice headless n'évalue pas fiablement
   `XLOOKUP`, `LET`, `LAMBDA`, `FILTER`, `UNIQUE`, et ne rejoue pas les macros.
   `xlaudit feasibility` rend un verdict *avant* toute tentative et refuse le
   recalcul plutôt que de produire des chiffres faux.
8. **`calcPr`.** Si `calcOnSave="0"`, les valeurs en cache ne sont pas l'état
   convergé du modèle. Une réserve automatique est émise et propagée dans tous
   les rapports.
9. **Livrables citant des formules.** Toute valeur commençant par `=` est écrite
   avec `cell.data_type = "s"`, sinon Excel réinterprète les formules citées
   comme réelles. Un test vérifie qu'aucune balise `<f>` ne subsiste dans le
   classeur de constats.
10. **Performance.** Un seul passage de collecte alimente tous les contrôles ;
    le snapshot est sérialisé en JSON gzip, invalidé par le SHA-256 du classeur.

**Le fichier source n'est jamais ouvert en écriture, sous aucune option.**

### Grain du graphe

Le graphe principal est construit au grain de la **ligne** : au grain de la
cellule, un modèle réel produirait des centaines de millions d'arêtes. Le grain
cellule reste disponible à la demande pour `trace`.

Conséquence traitée explicitement : au grain de la ligne, « solde d'ouverture =
solde de clôture de la période précédente » ressemble à un cycle. Les arêtes qui
ne lisent que des colonnes strictement à gauche sont marquées comme décalées, et
les composantes qui se dissolvent sans elles sont classées en **récurrences
temporelles** plutôt qu'en circularités — sans quoi tout modèle financier
apparaîtrait circulaire de bout en bout.

## Sortie JSON

Contrat avec les outils en aval, versionné par `schema_version` :

```json
{
  "schema_version": "1.0",
  "signal_count": 37,
  "signals": [
    {
      "rule_id": "R205", "phase": 2, "sheet": "Modele",
      "refs": ["D35", "I35"], "label": "Produits (report)",
      "observed": "=SUM($D6:I9)", "expected": "=SUM(I6:I9)",
      "evidence": { "chiffrage": "actif", "ecart_max_absolu": 5400.0, "...": "..." },
      "consumers": ["Modele!41"], "confidence": 1.0,
      "note": "Bornes ancrees de facon asymetrique..."
    }
  ],
  "run": { "sha256": "...", "rules": [...], "reserves": [...] }
}
```

Le journal d'exécution est horodaté, porte l'empreinte du fichier, et liste les
règles exécutées **et celles qui ont été sautées faute de mapping** : un rapport
doit dire ce qu'il n'a pas regardé.

## Mapping

```yaml
periodes:
  sheet: "Etats fi periode"
  ligne_index: 10
  ligne_date: 9
  colonnes: "O:HU"
bilan:
  actif_total: {sheet: "Etats fi periode", row: 211}
  passif_total: {sheet: "Etats fi periode", row: 233}
  tresorerie:  {sheet: "Etats fi periode", row: 209}
cascade:
  solde_cloture: {sheet: "Etats fi periode", row: 186}
dettes:
  - {nom: "KfW", sheet: "Financement", crd_debut: 100, tirage: 101,
     remb: 102, crd_fin: 105, taux_periode: 0.0275}
tolerances:
  bilan: 1.0e-6
  interets_relatif: 0.005
```

`validate-mapping` confirme chaque localisation par un test numérique et
**rejette celles qui échouent**. Un contrôle ne s'exécute jamais sur une
localisation non validée : une ligne mal identifiée produit un audit faux, et
c'est pire que pas d'audit.

La validation confirme l'**identité** d'une ligne, pas l'invariant qu'on lui
fera subir : valider « total actif » en vérifiant qu'il égale le total passif
serait circulaire. Elle teste donc des propriétés de forme — la ligne est
renseignée, elle varie, elle est calculée là où un total doit l'être, ses signes
sont ceux de sa nature.

## Tests

```bash
pytest
```

235 tests. Deux classeurs de fixtures de même mise en page sont construits par
`openpyxl` : un sain et un portant une anomalie de chaque type recherché. Chaque
règle doit détecter son anomalie **et ne rien détecter dans le classeur sain** —
le test de non-détection compte autant que l'autre.

Les fixtures injectent les valeurs en cache directement dans le XML après
écriture : openpyxl écrit les formules sans valeur, ce qui rendrait R201 et le
chiffreur d'écart intestables.

## Architecture

```
xlaudit/
├── cli.py                    # Typer
├── models.py                 # Signal, Finding, Reserve, RunLog, AuditContext
├── core/
│   ├── loader.py             # double chargement, itération sûre, cache disque
│   ├── refs.py               # références, ancrages, A1↔R1C1, fonctions
│   ├── graph.py              # graphe cellule / ligne / onglet, cycles, dépendants
│   ├── blocks.py             # colonnes de projection, blocs, lignes de total
│   ├── quantifier.py         # chiffreur d'écart
│   └── vba.py                # extraction oletools
├── rules/
│   ├── base.py               # classe Rule, registre, journalisation
│   ├── p1_cartography.py
│   ├── p2_r201…r215
│   ├── p3_ties.py
│   ├── p4_chains.py
│   └── p5_feasibility.py
├── mapping/
│   ├── schema.py             # validation pydantic
│   ├── discover.py           # localisation par libellé + score
│   └── validate.py           # confirmation numérique
└── render/
    ├── xlsx.py               # classeur de constats
    ├── markdown.py           # rapport
    └── graphviz.py           # carte des dépendances (DOT / Mermaid)
```
