# Prompt de construction — `xlaudit`

> À copier tel quel dans Claude Code (ou tout agent de développement) depuis un dépôt vide.
> Long volontairement : chaque contrainte technique listée correspond à un piège qui coûte plusieurs heures s'il est découvert en cours de route.

---

Construis `xlaudit`, un outil Python en ligne de commande d'aide à l'audit de modèles financiers Excel (`.xlsx` / `.xlsm`).

## Ce que fait l'outil, et ce qu'il ne fait pas

`xlaudit` produit des **signaux** : des faits vérifiables, chiffrés et tracés (telle cellule contient telle erreur ; telle plage balaie 9 lignes alors que le bloc en compte 10 ; l'écart actif/passif vaut 1e-6 ; cette ligne n'a aucun dépendant).

Il ne produit **jamais de constats d'audit**. Le tri des faux positifs, la qualification erreur/convention, l'attribution de criticité et la rédaction restent à l'auditeur ou à un modèle de langage travaillant sur la sortie JSON. Cette frontière est structurante : ne code aucune heuristique qui prétende décider si une anomalie est volontaire. Classe par vraisemblance, expose les éléments de jugement, et arrête-toi là.

Corollaire de conception, à respecter partout : **chaque signal doit contenir tout ce qu'il faut pour être jugé sans rouvrir le classeur.** La formule exacte, la formule majoritaire du voisinage, l'écart chiffré sur toutes les colonnes, la liste des consommateurs de la ligne concernée. Un signal qui oblige à refaire l'analyse à la main n'a aucune valeur.

## Contraintes techniques (issues d'un audit réel sur un classeur de 32 Mo, 34 onglets, 1,26 M de formules)

Ces points ont tous causé des pertes de temps ou des résultats faux. Traite-les dès la conception du socle.

1. **Double chargement obligatoire.** openpyxl ne donne pas formules et valeurs simultanément : deux `load_workbook`, l'un `data_only=False`, l'autre `data_only=True`.

2. **`read_only=True` obligatoire** au-delà de quelques centaines de milliers de formules, sous peine de saturation mémoire.

3. **Piège majeur du mode lecture seule** : les cellules vides sont des `EmptyCell` sans attributs `.row` ni `.column`. Tout code faisant `cell.row` dans une boucle `iter_rows` plante. Utiliser un compteur de lignes et `enumerate(row, start=min_col)`. Encapsule cela **une seule fois** dans une fonction d'itération sûre du socle, et interdis l'accès direct à `iter_rows` ailleurs dans le code.

4. **Formules matricielles** : la valeur est un objet `ArrayFormula`, pas une chaîne. Normaliser systématiquement via `getattr(v, "text", v)`. Sans cela les formules matricielles disparaissent silencieusement des scans.

5. **VBA** : `keep_vba=True` fait échouer le chargement des gros `.xlsm`. Extraire séparément avec `oletools.olevba.VBA_Parser`. Les plages nommées `*Copy` / `*Paste` du code révèlent les boucles de résolution de circularité.

6. **Noms définis à portée feuille** : `wb.defined_names` ne contient que la portée globale. Balayer aussi `ws.defined_names` de chaque onglet, sinon la moitié du gestionnaire est invisible.

7. **Recalcul hors Excel** : LibreOffice headless n'évalue pas fiablement `XLOOKUP`, `LET`, `LAMBDA`, `FILTER`, `UNIQUE`, et ne rejoue pas les macros. Implémente un **testeur de faisabilité** qui compte ces fonctions et rend un verdict *avant* toute tentative de recalcul. Si le verdict est négatif, refuse le recalcul avec un message explicite plutôt que de produire des chiffres faux.

8. **`calcPr` dans `xl/workbook.xml`** : si `calcOnSave="0"`, les valeurs en cache sont celles du dernier calcul de l'utilisateur, pas l'état convergé. Émettre une réserve automatique qui se propage dans tous les rapports.

9. **Écriture de livrables citant des formules** : forcer `cell.data_type = 's'` sur toute valeur commençant par `=`, sinon Excel interprète les formules citées comme réelles.

10. **Performance** : un seul passage de collecte alimentant tous les contrôles, restriction aux plages réellement utilisées, sérialisation JSON des extractions intermédiaires pour éviter de relire le classeur à chaque analyse.

## Architecture

```
xlaudit/
├── cli.py                    # Typer
├── models.py                 # Signal, Finding, Mapping, AuditContext
├── core/
│   ├── loader.py             # double chargement, itération sûre, cache disque
│   ├── refs.py               # parsing de références, ancrages, A1↔R1C1, fonctions
│   ├── graph.py              # graphe cellule / ligne / onglet, cycles, dépendants
│   └── vba.py                # extraction oletools
├── rules/
│   ├── base.py               # classe Rule : id, libellé, phase, run() -> list[Signal]
│   ├── p1_*.py               # cartographie
│   ├── p2_*.py               # R201 à R215
│   ├── p3_*.py               # bouclages, pilotés par mapping
│   ├── p4_*.py               # extraction de chaînes, comparateur de reconstitution
│   └── p5_*.py               # faisabilité, chocs, propagation statique
├── mapping/
│   ├── schema.py             # validation pydantic du YAML
│   ├── discover.py           # localisation par libellé + score de confiance
│   └── validate.py           # confirmation numérique avant usage
├── render/
│   ├── xlsx.py               # classeur de constats
│   ├── markdown.py           # rapport
│   └── graphviz.py           # carte des dépendances (DOT / Mermaid)
└── tests/
```

## Modèle de données

```python
@dataclass
class Signal:
    rule_id: str                  # "R205"
    phase: int
    sheet: str
    refs: list[str]               # ["S495", "AG495"] ou ["495:497"]
    label: str                    # libellé de la ligne dans le modèle, si trouvé
    observed: str                 # formule ou valeur telle que relevée
    expected: str | None          # formule majoritaire / cellule jumelle
    evidence: dict                # chiffrage : écart max, colonnes touchées, totaux
    consumers: list[str]          # qui consomme la ligne concernée
    confidence: float             # 0-1, vraisemblance que ce ne soit pas un faux positif
    note: str                     # ce que la règle a détecté, factuellement
```

`Signal` est l'unique interface entre l'outil et l'humain. Toute règle en émet ; rien d'autre ne sort du moteur.

`confidence` est une aide au tri, jamais un verdict : documente dans le code comment chaque règle la calcule, et ne l'utilise jamais pour filtrer silencieusement — expose tout, trie par confiance décroissante.

## Règles de la phase 2 — spécifications de détection

Implémente-les comme modules indépendants. Les quatre règles de plages (R204 à R208) sont **la valeur ajoutée principale de l'outil** : ce sont les erreurs qu'aucune erreur Excel ne signale.

**R201 Erreurs en cache** — Balayer `#REF!`, `#VALUE!`, `#N/A`, `#DIV/0!`, `#NAME?`, `#NUM!`, `#NULL!`. Pour chacune : dépendants via le graphe, et recherche d'une cellule jumelle (même position relative dans un bloc parallèle) dont la formule sert de correction proposée.

**R202 Valeurs en dur** — Constante numérique isolée dans une plage de formules homogène sur une ligne de projection. Exclure colonnes d'unités, de totaux, de sélecteurs de scénario. Marquer `confidence` haute si le libellé de la ligne contient « contrôle », « ctrl », « check ».

**R203 Cohérence horizontale** — Normaliser en R1C1 par ligne, grouper, signaler les variantes minoritaires. Pondérer `confidence` par la position : variante en colonne isolée au milieu d'une chronique = haute ; variante sur colonnes de bord ou de synthèse = basse.

**R204 Glissement de recopie** — Pour chaque groupe de lignes consécutives structurellement identiques, extraire les bornes de chaque plage. Si les bornes progressent de +1 par ligne alors que le bloc source est fixe, émettre un signal. Enrichir avec : quelles lignes de sous-total sont capturées, quels articles sont omis.

**R205 Ancrage asymétrique** — Dans chaque argument de plage, comparer l'ancrage des deux bornes. Le motif `$O488:S491` (coin initial ancré en colonne, coin final relatif) dans une formule recopiée horizontalement neutralise silencieusement le terme entier : Excel redimensionne depuis le coin supérieur gauche et lit toujours la colonne O. Motif symétrique `O488:$S491` également. **Chiffrer systématiquement** : reconstruire la grandeur attendue, comparer au cache ; si l'écart égale exactement le terme neutralisé, `confidence = 1.0`.

**R206 Somme tronquée** — Comparer le nombre de lignes sommées entre colonnes d'une même ligne de total, et comparer la plage sommée à l'étendue réelle du bloc (délimitée par en-tête et sous-total). Signaler l'omission d'une première ou dernière ligne de bloc.

**R207 Plage de somme multi-colonnes** — Dans SOMME.SI / SOMME.SI.ENS, largeur de la plage de somme ≠ largeur de la plage de critères. Excel tronque à la première colonne : indiquer la valeur effectivement sommée et celle qu'un lecteur croirait sommée.

**R208 Somme hétérogène** — Nombre de termes additionnés variable d'une colonne à l'autre sur une même ligne. Signaler le double comptage potentiel en identifiant les blocs sources.

**R215 Lignes orphelines** — Lignes calculées sans aucun dépendant. Distinguer par le libellé : un libellé significatif (« Impasse de trésorerie », « ADSCR », « Contrôle ») signale un **canal débranché** — un mécanisme qui paraît exister mais ne produit aucun effet. C'est un signal de premier ordre, `confidence` haute.

**Chiffreur d'écart** — Composant transverse appelé par R204 à R208 : reconstruit la grandeur sur **toutes** les colonnes de projection, compare au cache, et qualifie `actif` / `latent` / `nul`. Sans ce chiffrage, ces règles ne produisent que du bruit.

## Phase 3 — Bouclages pilotés par mapping

Fichier `mapping.yaml` par modèle, validé par pydantic :

```yaml
periodes:
  sheet: "Etats fi periode"
  ligne_index: 10          # numéro de période
  ligne_date: 9
  colonnes: "O:HU"
bilan:
  actif_total: {sheet: "Etats fi periode", row: 211}
  passif_total: {sheet: "Etats fi periode", row: 233}
  tresorerie:  {sheet: "Etats fi periode", row: 209}
cascade:
  solde_cloture: {sheet: "Etats fi periode", row: 186}
dettes:
  - {nom: "KfW", sheet: "Financement", crd_debut: 100, tirage: 101, remb: 102, crd_fin: 105, taux_periode: 0.0275}
tolerances:
  bilan: 1e-6
  interets_relatif: 0.005
```

Trois modes : `xlaudit discover` propose un mapping candidat par recherche de libellés avec score ; `xlaudit validate-mapping` confirme chaque localisation par un test numérique et **rejette celles qui échouent** ; `xlaudit ties` exécute les contrôles.

Ne jamais exécuter un contrôle sur une localisation non validée numériquement — une ligne mal identifiée produit un audit faux, et c'est pire que pas d'audit.

Implémente les dix invariants : bilan, trésorerie cascade = bilan, continuité ouverture/clôture, amortissement intégral des dettes, intérêts = CRD × taux, emplois = ressources, cohérence période/annuel (flux et stocks), flags mutuellement exclusifs et contigus, immobilisations bornées, non-négativité.

Ajoute un **analyseur de trésorerie négative** : sur chaque période en écart, décomposer la cascade pour identifier l'étage de bascule, relever l'état des mécanismes de couverture (facilité court terme, réserves), et tracer sur quelle grandeur leur signal de déclenchement est branché.

## Commandes

```
xlaudit scan MODELE.xlsm [--phases 1,2,3] [--mapping m.yaml] [--out signaux.json]
xlaudit discover MODELE.xlsm --out mapping.yaml
xlaudit validate-mapping MODELE.xlsm --mapping mapping.yaml
xlaudit ties MODELE.xlsm --mapping mapping.yaml
xlaudit trace MODELE.xlsm --cell "Onglet!S495" [--depth 3] [--direction up|down]
xlaudit map MODELE.xlsm --out carte.mmd
xlaudit feasibility MODELE.xlsm          # recalcul hors Excel possible ?
xlaudit sensitivity MODELE.xlsm --shock production=-5% --mapping m.yaml
xlaudit report constats.json --xlsx sortie.xlsx --md rapport.md
xlaudit diff v1.xlsm v2.xlsm --mapping m.yaml    # non-régression
```

`trace` est la commande la plus utilisée en pratique : remontée ou descente récursive des dépendances d'une cellule, avec formules et valeurs à chaque niveau. Soigne sa sortie.

## Exigences transverses

- **Python 3.11+**, dépendances : `openpyxl`, `pydantic`, `typer`, `rich`, `oletools`, `pyyaml`, `networkx`. Pas de pandas dans le socle.
- **Barres de progression** (`rich`) : un scan complet dure plusieurs minutes, l'utilisateur doit voir où il en est.
- **Reprise sur cache** : le passage de collecte est sérialisé ; les analyses ultérieures repartent du cache, invalidé par le SHA-256 du classeur.
- **Aucune écriture sur le fichier source**, jamais, sous aucune option.
- **Tests** : construis avec `openpyxl` des classeurs de fixtures contenant chaque anomalie recherchée (un glissement de recopie, un ancrage asymétrique, une somme tronquée, une plage de somme multi-colonnes, un bilan déséquilibré d'un centime, une ligne orpheline). Chaque règle doit détecter son anomalie et **ne pas en détecter dans un classeur sain** — le test de non-détection compte autant que l'autre.
- **Sortie JSON stable et versionnée** (`schema_version`) : c'est le contrat avec les outils en aval.
- **Journal d'exécution** horodaté avec l'empreinte du fichier, listant les règles exécutées et celles qui ont été sautées faute de mapping.

## Ordre de construction

1. Socle : `loader`, `refs`, `graph`, `models`, plus les fixtures de test. **Ne code aucune règle avant que l'itération sûre et le parsing de références ne soient couverts par des tests** — toutes les règles en dépendent, et un bug à ce niveau contamine l'ensemble.
2. Phase 2, règles R201 à R203 (les classiques), pour valider la chaîne de bout en bout sur un vrai classeur.
3. Phase 2, règles R204 à R208 et R215 avec le chiffreur d'écart — le cœur de la valeur.
4. Phase 1 (cartographie) et `trace`.
5. Phase 3 avec mapping, `discover` et `validate-mapping`.
6. Rendu (`report`), puis phases 4 et 5.

Livre à chaque étape quelque chose d'utilisable en l'état.
