"""Reperage de la structure d'un onglet : colonnes de projection, blocs, totaux.

Les regles de plages ont besoin de savoir ce qu'est « le bloc » avant de pouvoir
dire qu'une somme en omet une ligne. Ce module fournit cette lecture structurelle,
et rien d'autre : il ne juge pas, il decrit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import refs as R
from .loader import SheetSnapshot

# Mots qui marquent une ligne de total dans un modele francophone ou anglophone.
TOTAL_WORDS = ("total", "sous-total", "sous total", "s/total", "cumul", "somme", "subtotal")
CONTROL_WORDS = ("controle", "contrôle", "ctrl", "check", "verif", "vérif", "test", "ecart", "écart")
# Libelles qui font d'une ligne orpheline un canal debranche plutot qu'un reliquat.
SIGNIFICANT_WORDS = (
    "impasse", "tresorerie", "trésorerie", "adscr", "llcr", "dscr", "controle",
    "contrôle", "ctrl", "check", "covenant", "ratio", "couverture", "solde",
    "equilibre", "équilibre", "verif", "vérif", "alerte", "flag", "declencheur",
    "déclencheur", "seuil", "reserve", "réserve", "facilite", "facilité",
)


def label_matches(label: str, words: tuple[str, ...]) -> str | None:
    """Rend le mot trouve dans le libelle, ou None. Comparaison insensible a la casse."""
    if not label:
        return None
    low = label.lower()
    for word in words:
        if word in low:
            return word
    return None


@dataclass
class SheetStructure:
    """Lecture structurelle d'un onglet."""

    sheet: str
    projection_cols: list[int] = field(default_factory=list)
    formula_rows: list[int] = field(default_factory=list)
    total_rows: set[int] = field(default_factory=set)
    per_col_counts: dict[int, int] = field(default_factory=dict)

    @property
    def first_col(self) -> int:
        return self.projection_cols[0] if self.projection_cols else 1

    @property
    def last_col(self) -> int:
        return self.projection_cols[-1] if self.projection_cols else 1

    def is_edge_column(self, col: int) -> bool:
        """Colonne de bord : premiere ou derniere de la chronique.

        Une variante de formule y est frequente et legitime (initialisation,
        colonne de synthese), donc elle abaisse la confiance plutot que de
        declencher un signal fort.
        """
        return col in (self.first_col, self.last_col)

    def is_outside_projection(self, col: int) -> bool:
        return col not in set(self.projection_cols)


def build_structure(sheet: SheetSnapshot, min_density: float = 0.3) -> SheetStructure:
    """Determine les colonnes de projection et les lignes de total d'un onglet.

    Les colonnes de projection sont celles dont la densite de formules atteint une
    fraction du maximum : dans un modele, la chronique concentre les formules,
    tandis que les colonnes de libelles, d'unites ou de commentaires en sont
    depourvues.
    """
    st = SheetStructure(sheet=sheet.name)
    per_col: dict[int, int] = {}
    rows: set[int] = set()
    for (row, col), _f in sheet.formulas.items():
        per_col[col] = per_col.get(col, 0) + 1
        rows.add(row)
    st.per_col_counts = per_col
    st.formula_rows = sorted(rows)
    if per_col:
        peak = max(per_col.values())
        st.projection_cols = sorted(
            c for c, n in per_col.items()
            if n >= min_density * peak and c > sheet.label_max_col
        )
        if not st.projection_cols:
            st.projection_cols = sorted(per_col)

    for row in st.formula_rows:
        if _is_total_row(sheet, row, st.projection_cols):
            st.total_rows.add(row)
    return st


def _is_total_row(sheet: SheetSnapshot, row: int, cols: list[int]) -> bool:
    """Une ligne est un total si son libelle le dit, ou si elle somme verticalement."""
    if label_matches(sheet.row_label(row), TOTAL_WORDS):
        return True
    for col in cols[:4]:
        formula = sheet.formula(row, col)
        if not formula:
            continue
        for call in R.parse_calls(formula, default_sheet=sheet.name):
            if call.name in ("SUM", "SUBTOTAL"):
                for ref in call.arg_refs:
                    if ref is not None and ref.height > 1 and ref.width == 1:
                        return True
    return False


def row_variants(
    sheet: SheetSnapshot, row: int, cols: list[int]
) -> dict[str, list[int]]:
    """Formules de la ligne normalisees en R1C1, groupees.

    Deux colonnes portant la meme formule recopiee tombent dans le meme groupe.
    Une entree unique signifie une ligne homogene ; plusieurs entrees signalent
    des variantes, dont R203 isole les minoritaires.
    """
    groups: dict[str, list[int]] = {}
    for col in cols:
        formula = sheet.formula(row, col)
        if not formula:
            continue
        key = R.to_r1c1(formula, row, col)
        groups.setdefault(key, []).append(col)
    return groups


def row_signature(sheet: SheetSnapshot, row: int, cols: list[int]) -> str | None:
    """Signature structurelle d'une ligne : sa forme R1C1 majoritaire.

    Rend None si la ligne ne porte pas de formule sur les colonnes de projection.
    """
    groups = row_variants(sheet, row, cols)
    if not groups:
        return None
    return max(groups.items(), key=lambda kv: len(kv[1]))[0]


def contiguous_data_run(
    sheet: SheetSnapshot, st: SheetStructure, lo: int, hi: int, max_span: int = 400
) -> tuple[int, int]:
    """Etend lo..hi tant que les lignes restent des lignes de donnees contigues.

    S'arrete sur une ligne vide (sur les colonnes de projection) ou sur une ligne
    de total : ce sont les delimiteurs naturels d'un bloc. Sert a R204 pour
    determiner si une plage qui glisse sort du bloc qu'elle est censee couvrir.
    """
    cols = st.projection_cols
    if not cols:
        return lo, hi

    def is_data(row: int) -> bool:
        if row in st.total_rows:
            return False
        return any(sheet.has_content(row, c) for c in cols)

    top = lo
    while top - 1 >= 1 and lo - (top - 1) <= max_span and is_data(top - 1):
        top -= 1
    bottom = hi
    while bottom + 1 <= sheet.max_row and (bottom + 1) - hi <= max_span and is_data(bottom + 1):
        bottom += 1
    return top, bottom


@dataclass
class RowBlock:
    """Groupe de lignes consecutives structurellement identiques."""

    sheet: str
    first_row: int
    last_row: int
    signature: str

    @property
    def rows(self) -> range:
        return range(self.first_row, self.last_row + 1)

    @property
    def height(self) -> int:
        return self.last_row - self.first_row + 1

    def __repr__(self) -> str:  # pragma: no cover - confort de debug
        return f"RowBlock({self.sheet}!{self.first_row}:{self.last_row}, h={self.height})"


def find_row_blocks(
    sheet: SheetSnapshot, st: SheetStructure, min_height: int = 2
) -> list[RowBlock]:
    """Groupes de lignes consecutives portant la meme structure de formule."""
    blocks: list[RowBlock] = []
    current: RowBlock | None = None
    for row in st.formula_rows:
        sig = row_signature(sheet, row, st.projection_cols)
        if sig is None:
            current = None
            continue
        if current is not None and row == current.last_row + 1 and sig == current.signature:
            current.last_row = row
            continue
        if current is not None and current.height >= min_height:
            blocks.append(current)
        current = RowBlock(sheet.name, row, row, sig)
    if current is not None and current.height >= min_height:
        blocks.append(current)
    return blocks


def data_block_above(
    sheet: SheetSnapshot, total_row: int, st: SheetStructure, max_span: int = 200
) -> tuple[int, int] | None:
    """Etendue reelle du bloc de donnees situe juste au-dessus d'une ligne de total.

    Le bloc est delimite vers le haut par la premiere ligne rencontree qui est
    vide sur toutes les colonnes de projection, ou par une autre ligne de total,
    ou par une ligne d'en-tete (libelle sans valeur). C'est cette etendue que la
    plage sommee est censee couvrir.
    """
    cols = st.projection_cols
    if not cols:
        return None
    rows: list[int] = []
    row = total_row - 1
    while row >= 1 and total_row - row <= max_span:
        if row in st.total_rows:
            break
        if not any(sheet.has_content(row, c) for c in cols):
            break
        rows.append(row)
        row -= 1
    if not rows:
        return None
    return min(rows), max(rows)
