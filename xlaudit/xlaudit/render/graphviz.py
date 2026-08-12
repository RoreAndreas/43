"""Carte des dependances : DOT et Mermaid.

La carte utile est celle des onglets : un graphe de lignes d'un modele reel est
illisible. La carte de lignes reste disponible autour d'une cellule donnee, pour
accompagner une trace.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core.graph import DependencyGraph


def _mermaid_id(name: str) -> str:
    """Identifiant Mermaid sur : lettres, chiffres et souligne uniquement."""
    ident = re.sub(r"[^A-Za-z0-9]", "_", name)
    return ident if ident and ident[0].isalpha() else f"n_{ident}"


def _escape(label: str) -> str:
    return label.replace('"', "'")


def sheet_map_mermaid(graph: DependencyGraph, title: str = "Carte des onglets") -> str:
    """Graphe des dependances entre onglets, au format Mermaid."""
    snap = graph.snapshot
    lines = [f"%% {title}", "graph LR"]
    for name in snap.sheet_names:
        sheet = snap.sheets[name]
        state = "" if sheet.state == "visible" else " · masque"
        lines.append(
            f'    {_mermaid_id(name)}["{_escape(name)}<br/>'
            f'{len(sheet.formulas)} formules{state}"]'
        )
    seen: set[tuple[str, str]] = set()
    for src, dst in graph.sheet_graph.edges():
        if src == dst or (src, dst) in seen:
            continue
        seen.add((src, dst))
        lines.append(f"    {_mermaid_id(src)} --> {_mermaid_id(dst)}")
    cycles = graph.sheet_cycles()
    for i, comp in enumerate(cycles):
        for name in comp:
            lines.append(f"    class {_mermaid_id(name)} circulaire;")
    if cycles:
        lines.append("    classDef circulaire fill:#f8cbad,stroke:#c00,stroke-width:2px;")
    return "\n".join(lines) + "\n"


def sheet_map_dot(graph: DependencyGraph, title: str = "Carte des onglets") -> str:
    """Meme carte, au format DOT."""
    snap = graph.snapshot
    lines = [f'digraph "{_escape(title)}" {{', "  rankdir=LR;", "  node [shape=box];"]
    for name in snap.sheet_names:
        sheet = snap.sheets[name]
        style = ', style="filled", fillcolor="#eeeeee"' if sheet.state != "visible" else ""
        lines.append(
            f'  "{_escape(name)}" [label="{_escape(name)}\\n'
            f'{len(sheet.formulas)} formules"{style}];'
        )
    for src, dst in graph.sheet_graph.edges():
        if src == dst:
            continue
        lines.append(f'  "{_escape(src)}" -> "{_escape(dst)}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def trace_mermaid(node, direction: str = "up") -> str:
    """Rend une trace de cellule sous forme d'arbre Mermaid."""
    lines = ["graph " + ("BT" if direction == "up" else "TD")]
    seen: set[str] = set()

    def walk(current) -> None:
        ident = _mermaid_id(current.full_ref)
        if ident not in seen:
            seen.add(ident)
            label = _escape(current.full_ref)
            if current.label:
                label += "<br/>" + _escape(current.label[:40])
            if current.formula:
                label += "<br/>" + _escape(str(current.formula)[:60])
            lines.append(f'    {ident}["{label}"]')
        for child in current.children:
            walk(child)
            if direction == "up":
                lines.append(f"    {_mermaid_id(child.full_ref)} --> {ident}")
            else:
                lines.append(f"    {ident} --> {_mermaid_id(child.full_ref)}")

    walk(node)
    return "\n".join(lines) + "\n"


def write_map(
    graph: DependencyGraph, path: str | Path, fmt: str | None = None
) -> Path:
    """Ecrit la carte. Le format decoule de l'extension si non precise."""
    path = Path(path)
    if fmt is None:
        fmt = "dot" if path.suffix.lower() in (".dot", ".gv") else "mermaid"
    content = sheet_map_dot(graph) if fmt == "dot" else sheet_map_mermaid(graph)
    path.write_text(content, encoding="utf-8")
    return path
