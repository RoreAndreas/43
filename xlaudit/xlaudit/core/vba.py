"""Extraction du VBA.

`keep_vba=True` fait echouer le chargement des gros `.xlsm` : le code n'est donc
jamais lu via openpyxl mais extrait separement avec `oletools.olevba`.

Les plages nommees `*Copy` / `*Paste` manipulees par le code revelent les boucles
de resolution de circularite : un modele qui resout ses circularites par macro
copie une zone de valeurs sur elle-meme jusqu'a convergence. Savoir que ce
mecanisme existe change la lecture de toutes les valeurs en cache.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Noms de plages evoquant une boucle de resolution de circularite.
CIRCULARITY_HINT = re.compile(r"\b(\w*(?:copy|paste|iter|circ|loop|converg)\w*)\b", re.I)
MACRO_DEF = re.compile(r"^\s*(?:Public\s+|Private\s+)?(?:Sub|Function)\s+(\w+)", re.I | re.M)
RANGE_LITERAL = re.compile(r"""Range\(\s*["']([^"']+)["']\s*\)""", re.I)
NAMED_RANGE = re.compile(r"""\[\s*([A-Za-z_]\w*)\s*\]|Names\(\s*["']([^"']+)["']""")


def extract_vba(path: str | os.PathLike) -> dict:
    """Extrait modules, macros et indices de circularite.

    Rend toujours un dictionnaire : l'absence d'oletools ou de VBA n'est pas une
    erreur d'analyse, c'est un fait a consigner.
    """
    out: dict = {
        "available": False,
        "has_vba": False,
        "modules": [],
        "macros": [],
        "auto_macros": [],
        "circularity_hints": [],
        "note": "",
    }
    suffix = Path(path).suffix.lower()
    if suffix not in (".xlsm", ".xlsb", ".xls", ".xltm"):
        out["note"] = f"format {suffix} : pas de conteneur VBA attendu"
        return out

    try:
        from oletools.olevba import VBA_Parser
    except ImportError:
        out["note"] = "oletools non installe : extraction VBA impossible"
        return out

    out["available"] = True
    parser = None
    try:
        parser = VBA_Parser(str(path))
        if not parser.detect_vba_macros():
            out["note"] = "aucune macro detectee"
            return out
        out["has_vba"] = True
        hints: set[str] = set()
        for _filename, _stream, vba_name, vba_code in parser.extract_macros():
            code = vba_code or ""
            out["modules"].append({"nom": vba_name, "lignes": code.count("\n") + 1})
            macros = MACRO_DEF.findall(code)
            out["macros"].extend(macros)
            for macro in macros:
                if macro.lower() in ("auto_open", "workbook_open", "auto_close"):
                    out["auto_macros"].append(macro)
            for match in RANGE_LITERAL.findall(code):
                if CIRCULARITY_HINT.search(match):
                    hints.add(match)
            for a, b in NAMED_RANGE.findall(code):
                name = a or b
                if name and CIRCULARITY_HINT.search(name):
                    hints.add(name)
        out["circularity_hints"] = sorted(hints)
    except Exception as exc:  # un VBA illisible ne doit pas faire echouer le scan
        out["note"] = f"extraction interrompue : {type(exc).__name__}: {exc}"
    finally:
        if parser is not None:
            try:
                parser.close()
            except Exception:
                pass
    return out
