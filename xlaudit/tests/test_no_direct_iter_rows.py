"""L'iteration sure est encapsulee une seule fois : ce test le fait respecter.

En lecture seule, `iter_rows` rend des `EmptyCell` sans `.row` ni `.column`, et
son origine n'est pas celle qu'on croit. Le seul endroit du code autorise a
l'appeler est `xlaudit.core.loader.iter_cells`. Tout autre appel est un futur
plantage ou un decalage de coordonnees silencieux.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "xlaudit"
ALLOWED = {PACKAGE / "core" / "loader.py"}


def _calls_iter_rows(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "iter_rows":
            hits.append(node.lineno)
    return hits


def test_iter_rows_is_only_called_in_the_loader():
    offenders = {}
    for path in PACKAGE.rglob("*.py"):
        if path in ALLOWED:
            continue
        lines = _calls_iter_rows(path)
        if lines:
            offenders[str(path.relative_to(PACKAGE.parent))] = lines
    assert not offenders, (
        "iter_rows ne doit etre appele que dans core/loader.py (iteration sure) ; "
        f"trouve ailleurs : {offenders}"
    )


def test_the_loader_really_does_call_it():
    """Garde-fou : si l'implementation change, ce test ne doit pas devenir vide."""
    loader = PACKAGE / "core" / "loader.py"
    assert _calls_iter_rows(loader), "iter_cells doit rester l'unique appelant"
