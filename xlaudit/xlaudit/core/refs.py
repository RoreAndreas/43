"""Parsing de references, ancrages, conversion A1 <-> R1C1, inventaire de fonctions.

Ce module ne lit jamais un classeur : il travaille sur des chaines de formules.
Toutes les regles en dependent, donc il est couvert par des tests avant qu'une
seule regle ne soit ecrite.

Le decoupage s'appuie sur le tokenizer d'openpyxl plutot que sur des expressions
regulieres appliquees a la formule entiere : une chaine litterale contenant
`"tot(al"` ou `"a:b"` casse toute approche naive. Le tokenizer restitue la formule
a l'identique quand on rejoint les valeurs de ses tokens, ce qui permet de
reconstruire une formule apres substitution sans en alterer le reste.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from openpyxl.formula.tokenizer import Tokenizer, Token

MAX_COL = 16384  # XFD
MAX_ROW = 1048576

# Fonctions dont le nom francais peut apparaitre dans une formule saisie hors Excel
# (Excel stocke l'anglais dans le XML, mais les fixtures, les exports LibreOffice et
# les formules recopiees depuis une documentation ne respectent pas toujours cela).
FR_TO_EN = {
    "SOMME": "SUM",
    "SOMME.SI": "SUMIF",
    "SOMME.SI.ENS": "SUMIFS",
    "SOMMEPROD": "SUMPRODUCT",
    "SI": "IF",
    "SIERREUR": "IFERROR",
    "SI.CONDITIONS": "IFS",
    "ET": "AND",
    "OU": "OR",
    "NON": "NOT",
    "MOYENNE": "AVERAGE",
    "MOYENNE.SI": "AVERAGEIF",
    "MOYENNE.SI.ENS": "AVERAGEIFS",
    "NB": "COUNT",
    "NBVAL": "COUNTA",
    "NB.SI": "COUNTIF",
    "NB.SI.ENS": "COUNTIFS",
    "RECHERCHEV": "VLOOKUP",
    "RECHERCHEH": "HLOOKUP",
    "RECHERCHEX": "XLOOKUP",
    "EQUIV": "MATCH",
    "EQUIVX": "XMATCH",
    "DECALER": "OFFSET",
    "ARRONDI": "ROUND",
    "ARRONDI.SUP": "ROUNDUP",
    "ARRONDI.INF": "ROUNDDOWN",
    "ENT": "INT",
    "PUISSANCE": "POWER",
    "RACINE": "SQRT",
    "ESTERREUR": "ISERROR",
    "ESTNA": "ISNA",
    "ESTVIDE": "ISBLANK",
    "FILTRE": "FILTER",
    "TRIER": "SORT",
    "GRANDE.VALEUR": "LARGE",
    "PETITE.VALEUR": "SMALL",
    "VAN": "NPV",
    "TRI": "IRR",
    "TRIM": "IRR",
    "VPM": "PMT",
    "VA": "PV",
    "VC": "FV",
    "TAUX": "RATE",
    "NPM": "NPER",
    "MAX": "MAX",
    "MIN": "MIN",
    "ABS": "ABS",
}

# Fonctions volatiles : leur presence rend le cache de valeurs peu fiable et
# complique tout recalcul hors Excel.
VOLATILE_FUNCTIONS = {
    "NOW", "TODAY", "RAND", "RANDBETWEEN", "RANDARRAY",
    "OFFSET", "INDIRECT", "CELL", "INFO",
}

# Fonctions que LibreOffice headless n'evalue pas de maniere fiable.
# Sert au testeur de faisabilite (phase 5) : on refuse le recalcul plutot que
# de produire des chiffres faux.
UNSUPPORTED_BY_LIBREOFFICE = {
    "XLOOKUP", "XMATCH", "LET", "LAMBDA", "FILTER", "UNIQUE", "SORT", "SORTBY",
    "SEQUENCE", "RANDARRAY", "TEXTSPLIT", "TEXTBEFORE", "TEXTAFTER", "VSTACK",
    "HSTACK", "TOCOL", "TOROW", "WRAPROWS", "WRAPCOLS", "CHOOSECOLS", "CHOOSEROWS",
    "GROUPBY", "PIVOTBY", "BYROW", "BYCOL", "MAKEARRAY", "SCAN", "REDUCE", "MAP",
}

ERROR_LITERALS = ("#REF!", "#VALUE!", "#N/A", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!")

_CELL_PART = r"(?P<{p}ca>\$?)(?P<{p}col>[A-Za-z]{{1,3}})(?P<{p}ra>\$?)(?P<{p}row>[0-9]{{1,7}})"
_SHEET_PART = r"(?:(?P<{p}sheet>(?:\[[^\]]*\])?(?:'(?:[^']|'')*'|[^'!\[\]:,;()\s*/+^&=<>-]+))!)?"

_RE_RANGE = re.compile(
    r"^"
    + _SHEET_PART.format(p="s1_")
    + _CELL_PART.format(p="c1_")
    + r":"
    + _SHEET_PART.format(p="s2_")
    + _CELL_PART.format(p="c2_")
    + r"$"
)
_RE_SINGLE = re.compile(r"^" + _SHEET_PART.format(p="s1_") + _CELL_PART.format(p="c1_") + r"$")
_RE_WHOLE_COL = re.compile(
    r"^"
    + _SHEET_PART.format(p="s1_")
    + r"(?P<c1_ca>\$?)(?P<c1_col>[A-Za-z]{1,3}):(?:(?P<s2_sheet>[^'!\s]+)!)?(?P<c2_ca>\$?)(?P<c2_col>[A-Za-z]{1,3})$"
)
_RE_WHOLE_ROW = re.compile(
    r"^"
    + _SHEET_PART.format(p="s1_")
    + r"(?P<c1_ra>\$?)(?P<c1_row>[0-9]{1,7}):(?:(?P<s2_sheet>[^'!\s]+)!)?(?P<c2_ra>\$?)(?P<c2_row>[0-9]{1,7})$"
)


@lru_cache(maxsize=8192)
def col_to_index(letters: str) -> int:
    """'A' -> 1, 'AA' -> 27. Leve ValueError si la chaine n'est pas une colonne."""
    letters = letters.upper()
    if not letters or not letters.isalpha():
        raise ValueError(f"colonne invalide: {letters!r}")
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return idx


@lru_cache(maxsize=8192)
def index_to_col(idx: int) -> str:
    """1 -> 'A', 27 -> 'AA'."""
    if idx < 1:
        raise ValueError(f"index de colonne invalide: {idx}")
    out = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


def quote_sheet(name: str) -> str:
    """Entoure le nom d'onglet de quotes si Excel l'exige."""
    if not name:
        return ""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", name) and not _looks_like_cell(name):
        return name
    return "'" + name.replace("'", "''") + "'"


def _looks_like_cell(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{1,3}[0-9]{1,7}", name))


def _unquote_sheet(raw: str | None) -> str | None:
    if raw is None:
        return None
    raw = raw.strip()
    # Reference externe [1]Feuille! : on conserve le marqueur, il est signifiant.
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1].replace("''", "'")
    return raw


@dataclass(frozen=True)
class CellRef:
    """Une borne de reference, avec son ancrage."""

    col: int
    row: int
    col_abs: bool = False
    row_abs: bool = False
    sheet: str | None = None

    @property
    def a1(self) -> str:
        c = "$" if self.col_abs else ""
        r = "$" if self.row_abs else ""
        return f"{c}{index_to_col(self.col)}{r}{self.row}"

    @property
    def plain(self) -> str:
        """Reference sans ancrage, pour comparer des positions."""
        return f"{index_to_col(self.col)}{self.row}"

    def to_r1c1(self, anchor_row: int, anchor_col: int) -> str:
        r = f"R{self.row}" if self.row_abs else (
            "R" if self.row == anchor_row else f"R[{self.row - anchor_row}]"
        )
        c = f"C{self.col}" if self.col_abs else (
            "C" if self.col == anchor_col else f"C[{self.col - anchor_col}]"
        )
        return r + c


@dataclass(frozen=True)
class RangeRef:
    """Une reference de plage (ou de cellule unique, start == end).

    `whole_col` / `whole_row` marquent les references de type `A:A` et `1:1`,
    dont une borne est absente.
    """

    start: CellRef
    end: CellRef
    sheet: str | None = None
    whole_col: bool = False
    whole_row: bool = False
    raw: str = ""

    @property
    def is_single(self) -> bool:
        return (
            not self.whole_col
            and not self.whole_row
            and self.start.col == self.end.col
            and self.start.row == self.end.row
        )

    @property
    def min_col(self) -> int:
        return min(self.start.col, self.end.col)

    @property
    def max_col(self) -> int:
        return max(self.start.col, self.end.col)

    @property
    def min_row(self) -> int:
        return min(self.start.row, self.end.row)

    @property
    def max_row(self) -> int:
        return max(self.start.row, self.end.row)

    @property
    def width(self) -> int:
        return self.max_col - self.min_col + 1

    @property
    def height(self) -> int:
        return self.max_row - self.min_row + 1

    @property
    def anchor_pattern(self) -> str:
        """Motif d'ancrage des quatre coordonnees, p.ex. '$O488:S491' -> 'AR:RR'.

        A = ancre (absolu), R = relatif. Ordre : col debut, ligne debut, col fin,
        ligne fin. C'est la signature utilisee par R205.
        """
        def f(flag: bool) -> str:
            return "A" if flag else "R"

        return (
            f(self.start.col_abs) + f(self.start.row_abs)
            + ":" + f(self.end.col_abs) + f(self.end.row_abs)
        )

    @property
    def a1(self) -> str:
        if self.whole_col:
            c1 = ("$" if self.start.col_abs else "") + index_to_col(self.start.col)
            c2 = ("$" if self.end.col_abs else "") + index_to_col(self.end.col)
            body = f"{c1}:{c2}"
        elif self.whole_row:
            r1 = ("$" if self.start.row_abs else "") + str(self.start.row)
            r2 = ("$" if self.end.row_abs else "") + str(self.end.row)
            body = f"{r1}:{r2}"
        elif self.is_single:
            body = self.start.a1
        else:
            body = f"{self.start.a1}:{self.end.a1}"
        if self.sheet:
            return f"{quote_sheet(self.sheet)}!{body}"
        return body

    def with_sheet(self, default_sheet: str) -> "RangeRef":
        """Resout l'onglet implicite : une ref sans prefixe vise sa propre feuille."""
        if self.sheet:
            return self
        return RangeRef(
            start=self.start, end=self.end, sheet=default_sheet,
            whole_col=self.whole_col, whole_row=self.whole_row, raw=self.raw,
        )

    def cells(self, max_cells: int = 100_000):
        """Itere les (row, col) de la plage. Borne pour ne pas exploser sur `A:A`."""
        if self.whole_col or self.whole_row:
            return
        count = 0
        for r in range(self.min_row, self.max_row + 1):
            for c in range(self.min_col, self.max_col + 1):
                if count >= max_cells:
                    return
                count += 1
                yield r, c

    def to_r1c1(self, anchor_row: int, anchor_col: int) -> str:
        if self.whole_col:
            def cpart(ref: CellRef) -> str:
                return f"C{ref.col}" if ref.col_abs else (
                    "C" if ref.col == anchor_col else f"C[{ref.col - anchor_col}]"
                )
            body = f"{cpart(self.start)}:{cpart(self.end)}"
        elif self.whole_row:
            def rpart(ref: CellRef) -> str:
                return f"R{ref.row}" if ref.row_abs else (
                    "R" if ref.row == anchor_row else f"R[{ref.row - anchor_row}]"
                )
            body = f"{rpart(self.start)}:{rpart(self.end)}"
        elif self.is_single:
            body = self.start.to_r1c1(anchor_row, anchor_col)
        else:
            body = (
                self.start.to_r1c1(anchor_row, anchor_col)
                + ":"
                + self.end.to_r1c1(anchor_row, anchor_col)
            )
        if self.sheet:
            return f"{quote_sheet(self.sheet)}!{body}"
        return body


def parse_ref(text: str, default_sheet: str | None = None) -> RangeRef | None:
    """Parse un operande de type RANGE.

    Rend None si le texte est un nom defini, une reference structuree de tableau,
    une reference 3D multi-onglets, ou depasse les bornes d'Excel : dans tous ces
    cas ce n'est pas une plage de cellules exploitable, et le confondre avec une
    plage produirait des signaux faux.
    """
    text = text.strip()
    if not text:
        return None

    m = _RE_RANGE.match(text)
    if m:
        g = m.groupdict()
        try:
            c1 = col_to_index(g["c1_col"])
            c2 = col_to_index(g["c2_col"])
            r1 = int(g["c1_row"])
            r2 = int(g["c2_row"])
        except (ValueError, TypeError):
            return None
        if not (1 <= c1 <= MAX_COL and 1 <= c2 <= MAX_COL):
            return None
        if not (1 <= r1 <= MAX_ROW and 1 <= r2 <= MAX_ROW):
            return None
        sheet = _unquote_sheet(g["s1_sheet"]) or default_sheet
        return RangeRef(
            start=CellRef(c1, r1, g["c1_ca"] == "$", g["c1_ra"] == "$"),
            end=CellRef(c2, r2, g["c2_ca"] == "$", g["c2_ra"] == "$"),
            sheet=sheet,
            raw=text,
        )

    m = _RE_SINGLE.match(text)
    if m:
        g = m.groupdict()
        try:
            c1 = col_to_index(g["c1_col"])
            r1 = int(g["c1_row"])
        except (ValueError, TypeError):
            return None
        if not (1 <= c1 <= MAX_COL) or not (1 <= r1 <= MAX_ROW):
            return None
        sheet = _unquote_sheet(g["s1_sheet"]) or default_sheet
        ref = CellRef(c1, r1, g["c1_ca"] == "$", g["c1_ra"] == "$")
        return RangeRef(start=ref, end=ref, sheet=sheet, raw=text)

    m = _RE_WHOLE_COL.match(text)
    if m:
        g = m.groupdict()
        try:
            c1, c2 = col_to_index(g["c1_col"]), col_to_index(g["c2_col"])
        except ValueError:
            return None
        if not (1 <= c1 <= MAX_COL and 1 <= c2 <= MAX_COL):
            return None
        sheet = _unquote_sheet(g["s1_sheet"]) or default_sheet
        return RangeRef(
            start=CellRef(c1, 1, g["c1_ca"] == "$", False),
            end=CellRef(c2, MAX_ROW, g["c2_ca"] == "$", False),
            sheet=sheet, whole_col=True, raw=text,
        )

    m = _RE_WHOLE_ROW.match(text)
    if m:
        g = m.groupdict()
        r1, r2 = int(g["c1_row"]), int(g["c2_row"])
        if not (1 <= r1 <= MAX_ROW and 1 <= r2 <= MAX_ROW):
            return None
        sheet = _unquote_sheet(g["s1_sheet"]) or default_sheet
        return RangeRef(
            start=CellRef(1, r1, False, g["c1_ra"] == "$"),
            end=CellRef(MAX_COL, r2, False, g["c2_ra"] == "$"),
            sheet=sheet, whole_row=True, raw=text,
        )

    return None


def normalize_function_name(raw: str) -> str:
    """'_xlfn.XLOOKUP(' -> 'XLOOKUP' ; 'SOMME.SI' -> 'SUMIF'."""
    name = raw.strip()
    if name.endswith("("):
        name = name[:-1]
    name = name.strip()
    for prefix in ("_xlfn.", "_xlws.", "_xludf."):
        if name.upper().startswith(prefix.upper()):
            name = name[len(prefix):]
    name = name.upper()
    return FR_TO_EN.get(name, name)


def tokenize(formula: str) -> list[Token]:
    """Tokenise une formule. Rend [] si la formule est intokenisable."""
    if not formula:
        return []
    if not formula.startswith("="):
        formula = "=" + formula
    try:
        return list(Tokenizer(formula).items)
    except Exception:
        return []


def is_arg_separator(tok: Token) -> bool:
    """`,` et `;` separent tous deux des arguments.

    Le tokenizer classe `;` en SEP/ROW (separateur de ligne de tableau), ce qui est
    correct entre accolades mais pas dans un appel de fonction saisi en locale
    francaise. On accepte les deux et on distingue par le contexte d'appel.
    """
    return tok.type == Token.SEP


def extract_functions(formula: str) -> list[str]:
    """Liste des fonctions appelees, en nom canonique, dans l'ordre d'apparition."""
    out = []
    for tok in tokenize(formula):
        if tok.type == Token.FUNC and tok.subtype == Token.OPEN:
            out.append(normalize_function_name(tok.value))
    return out


def extract_refs(formula: str, default_sheet: str | None = None) -> list[RangeRef]:
    """Toutes les plages citees par la formule, onglet resolu."""
    out: list[RangeRef] = []
    for tok in tokenize(formula):
        if tok.type == Token.OPERAND and tok.subtype == Token.RANGE:
            ref = parse_ref(tok.value, default_sheet)
            if ref is not None:
                out.append(ref)
    return out


def extract_names(formula: str) -> list[str]:
    """Operandes de type RANGE qui ne sont pas des references : noms definis."""
    out = []
    for tok in tokenize(formula):
        if tok.type == Token.OPERAND and tok.subtype == Token.RANGE:
            if parse_ref(tok.value) is None:
                out.append(tok.value)
    return out


@dataclass
class FunctionCall:
    """Un appel de fonction repere dans une formule, avec ses arguments.

    `arg_refs[i]` porte la plage quand l'argument est exactement une reference,
    et None sinon. R207 s'en sert pour comparer la largeur de la plage de somme
    a celle de la plage de criteres.
    """

    name: str
    raw_name: str
    args: list[str]
    arg_refs: list[RangeRef | None]
    depth: int

    @property
    def arity(self) -> int:
        return len(self.args)


def parse_calls(formula: str, default_sheet: str | None = None) -> list[FunctionCall]:
    """Decoupe les appels de fonction et leurs arguments de premier niveau.

    Implemente par une pile sur les tokens : les parentheses de groupement et les
    accolades de tableau ouvrent une frame sans etre des appels, de sorte qu'un
    separateur ne soit jamais attribue au mauvais appel.
    """
    toks = tokenize(formula)
    if not toks:
        return []

    calls: list[FunctionCall] = []
    # frame = [kind, name, depth, args(list[list[str]])]
    stack: list[dict] = []

    def cur() -> dict | None:
        return stack[-1] if stack else None

    def push_text(text: str) -> None:
        frame = cur()
        if frame is not None:
            frame["args"][-1].append(text)

    for tok in toks:
        t, sub, val = tok.type, tok.subtype, tok.value
        if sub == Token.OPEN and t in (Token.FUNC, Token.PAREN, Token.ARRAY):
            if t != Token.FUNC:
                push_text(val)
            frame = {
                "kind": t,
                "raw_name": val if t == Token.FUNC else "",
                "depth": len(stack),
                "args": [[]],
                "text": val,
            }
            stack.append(frame)
            continue

        if sub == Token.CLOSE and t in (Token.FUNC, Token.PAREN, Token.ARRAY):
            if not stack:
                continue
            frame = stack.pop()
            rendered_args = ["".join(a).strip() for a in frame["args"]]
            if frame["kind"] == Token.FUNC:
                # Un appel sans argument rend [""] : on le ramene a [].
                if len(rendered_args) == 1 and rendered_args[0] == "":
                    rendered_args = []
                refs = [parse_ref(a, default_sheet) for a in rendered_args]
                calls.append(
                    FunctionCall(
                        name=normalize_function_name(frame["raw_name"]),
                        raw_name=frame["raw_name"].rstrip("(").strip(),
                        args=rendered_args,
                        arg_refs=refs,
                        depth=frame["depth"],
                    )
                )
                inner = frame["raw_name"] + ",".join(rendered_args) + val
            else:
                inner = "".join("".join(a) for a in frame["args"]) + val
            push_text(inner)
            continue

        if is_arg_separator(tok) and stack:
            stack[-1]["args"].append([])
            continue

        push_text(val)

    return calls


def to_r1c1(formula: str, row: int, col: int, default_sheet: str | None = None) -> str:
    """Normalise une formule en R1C1 relativement a la cellule (row, col).

    Deux formules structurellement identiques recopiees sur des colonnes
    differentes donnent la meme chaine R1C1 : c'est ce qui permet a R203 de
    grouper une ligne et d'isoler ses variantes minoritaires.

    Les noms definis et les litteraux sont laisses intacts.
    """
    toks = tokenize(formula)
    if not toks:
        return formula
    out = []
    for tok in toks:
        if tok.type == Token.OPERAND and tok.subtype == Token.RANGE:
            ref = parse_ref(tok.value, None)
            if ref is not None:
                out.append(ref.to_r1c1(row, col))
                continue
        out.append(tok.value)
    return "=" + "".join(out)


def top_level_terms(formula: str) -> list[tuple[str, str]]:
    """Decompose une formule en termes additifs de premier niveau.

    Rend une liste de (signe, texte) ou signe est '+' ou '-'. `=A1+SUM(B:B)-C1`
    donne [('+','A1'), ('+','SUM(B:B)'), ('-','C1')]. Sert a R208 pour compter les
    termes additionnes, et au chiffreur pour isoler le terme neutralise.

    Rend [] si la formule n'est pas une somme de termes au premier niveau (produit,
    appel unique enveloppant tout, comparaison...). Dans ce cas la decomposition
    additive n'a pas de sens et la regle appelante doit s'abstenir.
    """
    toks = tokenize(formula)
    if not toks:
        return []
    depth = 0
    terms: list[tuple[str, str]] = []
    sign = "+"
    buf: list[str] = []
    saw_top_level_op = False

    for tok in toks:
        t, sub, val = tok.type, tok.subtype, tok.value
        if sub == Token.OPEN and t in (Token.FUNC, Token.PAREN, Token.ARRAY):
            depth += 1
            buf.append(val)
            continue
        if sub == Token.CLOSE and t in (Token.FUNC, Token.PAREN, Token.ARRAY):
            depth -= 1
            buf.append(val)
            continue
        if depth == 0 and t == Token.OP_IN and val in ("+", "-"):
            text = "".join(buf).strip()
            if text:
                terms.append((sign, text))
            buf = []
            sign = val
            saw_top_level_op = True
            continue
        if depth == 0 and t == Token.OP_IN and val not in ("+", "-"):
            # Produit, division, concatenation, comparaison au premier niveau :
            # la lecture additive serait fausse.
            return []
        buf.append(val)

    text = "".join(buf).strip()
    if text:
        terms.append((sign, text))
    if not saw_top_level_op and len(terms) <= 1:
        return terms
    return terms


def contains_error_literal(text: str) -> str | None:
    """Rend le premier littéral d'erreur trouve dans une chaine, ou None."""
    if not text:
        return None
    upper = str(text).upper()
    for err in ERROR_LITERALS:
        if err in upper:
            return err
    return None
