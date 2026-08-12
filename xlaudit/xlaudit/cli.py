"""Interface en ligne de commande."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.tree import Tree

app = typer.Typer(
    add_completion=False,
    help=(
        "Aide a l'audit de modeles financiers Excel. Produit des signaux "
        "verifiables et chiffres, jamais des constats d'audit."
    ),
)
console = Console()
err_console = Console(stderr=True)

TOOL_VERSION = "0.6.0"


# ---------------------------------------------------------------------------
# Chargement partage
# ---------------------------------------------------------------------------

def _load(
    workbook: Path,
    cache_dir: Optional[Path],
    no_cache: bool,
    refresh: bool,
    with_graph: bool = True,
    with_vba: bool = True,
    quiet: bool = False,
    rescan_dimensions: bool = False,
):
    """Charge le snapshot (cache ou collecte) et construit le graphe."""
    from .core.graph import build_graph
    from .core.loader import get_snapshot, load_vba

    if not workbook.exists():
        err_console.print(f"[red]Classeur introuvable :[/red] {workbook}")
        raise typer.Exit(code=2)

    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
    ]
    with Progress(*columns, console=console, disable=quiet, transient=True) as progress:
        task = progress.add_task("lecture du classeur", total=1)

        def report(stage: str, done: int, total: int) -> None:
            progress.update(task, description=stage, completed=done, total=max(total, 1))

        snapshot, from_cache = get_snapshot(
            workbook, cache_dir=cache_dir, force=refresh,
            use_cache=not no_cache, progress=report,
            force_dimensions=rescan_dimensions,
        )
        if with_vba and not snapshot.vba:
            progress.update(task, description="VBA", completed=0, total=1)
            snapshot.vba = load_vba(workbook)
            progress.update(task, completed=1)

        graph = None
        if with_graph:
            graph = build_graph(snapshot, progress=report)

    if not quiet:
        origin = "cache" if from_cache else "collecte"
        console.print(
            f"[dim]{workbook.name} · {len(snapshot.sheets)} onglet(s) · "
            f"{snapshot.formula_count} formule(s) · {origin}[/dim]"
        )
    return snapshot, graph


def _parse_phases(text: Optional[str]) -> Optional[list[int]]:
    if not text:
        return None
    out = []
    for chunk in text.replace(" ", "").split(","):
        if not chunk:
            continue
        if not chunk.isdigit():
            err_console.print(f"[red]Phase invalide :[/red] {chunk}")
            raise typer.Exit(code=2)
        out.append(int(chunk))
    return out or None


def _load_mapping(path: Optional[Path]):
    if path is None:
        return None
    from pydantic import ValidationError

    from .mapping.schema import load_mapping

    try:
        return load_mapping(path)
    except FileNotFoundError:
        err_console.print(f"[red]Mapping introuvable :[/red] {path}")
        raise typer.Exit(code=2)
    except ValidationError as exc:
        err_console.print(f"[red]Mapping invalide :[/red] {path}")
        err_console.print(str(exc))
        raise typer.Exit(code=2)


def _write_json(document: dict, out: Optional[Path]) -> None:
    text = json.dumps(document, ensure_ascii=False, indent=2)
    if out is None:
        console.print_json(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    console.print(f"[green]Ecrit :[/green] {out}")


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

@app.command()
def scan(
    workbook: Path = typer.Argument(..., help="Classeur .xlsx / .xlsm"),
    phases: Optional[str] = typer.Option(None, "--phases", help="p.ex. 1,2,3"),
    rules: Optional[str] = typer.Option(None, "--rules", help="p.ex. R205,R215"),
    mapping: Optional[Path] = typer.Option(None, "--mapping", help="mapping.yaml"),
    out: Optional[Path] = typer.Option(None, "--out", help="sortie JSON"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh", help="ignore le cache existant"),
    rescan_dimensions: bool = typer.Option(
        False, "--rescan-dimensions",
        help=(
            "relit chaque onglet pour retrouver ses bornes, au lieu de se fier a "
            "l'element <dimension> declare. A utiliser si le classeur semble "
            "tronque : une dimension declaree trop petite fait lire moins de "
            "cellules qu'il n'y en a, sans aucune erreur."
        ),
    ),
    validate_first: bool = typer.Option(
        True, "--validate-mapping/--skip-validation",
        help="valide numeriquement le mapping avant d'executer la phase 3",
    ),
):
    """Execute les regles et ecrit les signaux."""
    from .models import AuditContext, RunLog, signals_to_document
    from .rules.base import execute, get_rules

    snapshot, graph = _load(
        workbook, cache_dir, no_cache, refresh, rescan_dimensions=rescan_dimensions
    )
    mapping_model = _load_mapping(mapping)

    run_log = RunLog(tool_version=TOOL_VERSION)
    run_log.start(str(workbook), snapshot.sha256)

    if mapping_model is not None and validate_first:
        from .mapping.validate import validate_mapping as run_validation

        results = run_validation(snapshot, mapping_model)
        rejected = [r for r in results if not r.ok]
        if rejected:
            console.print(
                f"[yellow]{len(rejected)} localisation(s) rejetee(s) par la validation "
                f"numerique ; les controles correspondants seront sautes.[/yellow]"
            )

    ctx = AuditContext(snapshot=snapshot, graph=graph, mapping=mapping_model)
    selected = get_rules(
        phases=_parse_phases(phases),
        ids=[r.strip() for r in rules.split(",")] if rules else None,
    )
    if not selected:
        err_console.print("[red]Aucune regle ne correspond a la selection.[/red]")
        raise typer.Exit(code=2)

    signals = []
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), BarColumn(),
        TextColumn("{task.completed}/{task.total}"), console=console, transient=True,
    ) as progress:
        task = progress.add_task("regles", total=len(selected))
        for rule in selected:
            progress.update(task, description=f"{rule.id} · {rule.label}")
            produced, run = execute(rule, ctx)
            signals.extend(produced)
            run_log.add(run)
            progress.advance(task)

    run_log.reserves = list(ctx.reserves)
    run_log.finish()

    _print_summary(run_log, signals)
    _write_json(signals_to_document(signals, run_log), out)


def _print_summary(run_log, signals) -> None:
    table = Table(title="Signaux par regle", show_lines=False)
    table.add_column("Regle")
    table.add_column("Libelle")
    table.add_column("Ph.", justify="right")
    table.add_column("Statut")
    table.add_column("Signaux", justify="right")
    table.add_column("Duree", justify="right")
    for run in run_log.rules:
        style = {"skipped": "yellow", "error": "red"}.get(run.status, "")
        table.add_row(
            run.rule_id, run.label, str(run.phase),
            run.status + (f" · {run.reason}" if run.reason else ""),
            str(run.signals), f"{run.duration_s:.2f}s", style=style,
        )
    console.print(table)

    high = sum(1 for s in signals if s.confidence >= 0.85)
    console.print(
        f"[bold]{len(signals)} signal(aux)[/bold], dont {high} a confiance ≥ 0.85."
    )
    for reserve in run_log.reserves:
        console.print(f"[yellow]Reserve {reserve.code}[/yellow] — {reserve.message}")


# ---------------------------------------------------------------------------
# discover / validate-mapping / ties
# ---------------------------------------------------------------------------

@app.command()
def discover(
    workbook: Path = typer.Argument(...),
    out: Path = typer.Option(..., "--out", help="mapping.yaml a ecrire"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Propose un mapping candidat par recherche de libelles."""
    from .mapping.discover import discover as run_discover
    from .mapping.schema import dump_mapping

    snapshot, _graph = _load(workbook, cache_dir, no_cache, refresh, with_graph=False)
    mapping, found = run_discover(snapshot)
    if mapping is None:
        err_console.print(
            "[red]Aucune grandeur reconnue.[/red] Ecrire le mapping a la main : la "
            "recherche par libelle n'a rien trouve de suffisamment sur."
        )
        raise typer.Exit(code=1)

    table = Table(title="Localisations proposees")
    table.add_column("Cle")
    table.add_column("Localisation")
    table.add_column("Libelle")
    table.add_column("Score", justify="right")
    table.add_column("Concurrence")
    for item in sorted(found, key=lambda d: -(d.best.score if d.best else 0)):
        best = item.best
        table.add_row(
            item.key, f"{best.sheet}!{best.row}", best.label, f"{best.score:.2f}",
            "[yellow]ambigu[/yellow]" if item.ambiguous else "",
        )
    console.print(table)

    dump_mapping(mapping, out)
    console.print(f"[green]Mapping candidat ecrit :[/green] {out}")
    console.print(
        "[yellow]Aucune localisation n'est confirmee.[/yellow] Relire le fichier, puis "
        "lancer [bold]xlaudit validate-mapping[/bold] avant tout controle."
    )


@app.command("validate-mapping")
def validate_mapping_cmd(
    workbook: Path = typer.Argument(...),
    mapping: Path = typer.Option(..., "--mapping"),
    out: Optional[Path] = typer.Option(None, "--out", help="mapping valide a reecrire"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Confirme chaque localisation par un test numerique et rejette les autres."""
    from .mapping.schema import dump_mapping
    from .mapping.validate import validate_mapping as run_validation

    snapshot, _graph = _load(workbook, cache_dir, no_cache, refresh, with_graph=False)
    model = _load_mapping(mapping)
    results = run_validation(snapshot, model)

    table = Table(title="Validation numerique du mapping")
    table.add_column("Cle")
    table.add_column("Localisation")
    table.add_column("Verdict")
    table.add_column("Motif")
    for result in results:
        table.add_row(
            result.key, result.location,
            "[green]valide[/green]" if result.ok else "[red]rejete[/red]",
            result.note,
        )
    console.print(table)

    rejected = [r for r in results if not r.ok]
    if out:
        dump_mapping(model, out)
        console.print(f"[green]Mapping annote ecrit :[/green] {out}")
    if rejected:
        console.print(
            f"[red]{len(rejected)} localisation(s) rejetee(s).[/red] Les controles qui "
            f"en dependent ne seront pas executes : une ligne mal identifiee produit "
            f"un audit faux."
        )
        raise typer.Exit(code=1)
    console.print("[green]Toutes les localisations sont confirmees.[/green]")


@app.command()
def ties(
    workbook: Path = typer.Argument(...),
    mapping: Path = typer.Option(..., "--mapping"),
    out: Optional[Path] = typer.Option(None, "--out"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Execute les bouclages de la phase 3."""
    from .models import AuditContext, RunLog, signals_to_document
    from .mapping.validate import validate_mapping as run_validation
    from .rules.base import execute, get_rules

    snapshot, graph = _load(workbook, cache_dir, no_cache, refresh)
    model = _load_mapping(mapping)

    results = run_validation(snapshot, model)
    rejected = [r for r in results if not r.ok]
    for result in rejected:
        console.print(
            f"[yellow]Localisation rejetee[/yellow] {result.key} "
            f"({result.location}) — {result.note}"
        )

    run_log = RunLog(tool_version=TOOL_VERSION)
    run_log.start(str(workbook), snapshot.sha256)
    ctx = AuditContext(snapshot=snapshot, graph=graph, mapping=model)
    signals = []
    for rule in get_rules(phases=[3]):
        produced, run = execute(rule, ctx)
        signals.extend(produced)
        run_log.add(run)
    run_log.reserves = list(ctx.reserves)
    run_log.finish()

    _print_summary(run_log, signals)
    _write_json(signals_to_document(signals, run_log), out)


# ---------------------------------------------------------------------------
# trace
# ---------------------------------------------------------------------------

@app.command()
def trace(
    workbook: Path = typer.Argument(...),
    cell: str = typer.Option(..., "--cell", help='p.ex. "Onglet!S495"'),
    depth: int = typer.Option(3, "--depth", min=1, max=20),
    direction: str = typer.Option("up", "--direction", help="up | down"),
    out: Optional[Path] = typer.Option(None, "--out", help="sortie JSON"),
    mermaid: Optional[Path] = typer.Option(None, "--mermaid", help="arbre Mermaid"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Remonte ou descend les dependances d'une cellule."""
    from .core import refs as R

    if direction not in ("up", "down"):
        err_console.print("[red]--direction doit valoir 'up' ou 'down'.[/red]")
        raise typer.Exit(code=2)

    match = re.fullmatch(r"\s*(?:'([^']+)'|([^!]+))!([A-Za-z]{1,3}\d{1,7})\s*", cell)
    if not match:
        err_console.print(
            f"[red]Reference invalide :[/red] {cell!r}. Attendu : \"Onglet!S495\"."
        )
        raise typer.Exit(code=2)
    sheet_name = match.group(1) or match.group(2)
    ref = R.parse_ref(match.group(3))

    snapshot, graph = _load(workbook, cache_dir, no_cache, refresh)
    sheet = snapshot.sheet(sheet_name)
    if sheet is None:
        err_console.print(f"[red]Onglet introuvable :[/red] {sheet_name}")
        console.print("Onglets disponibles : " + ", ".join(snapshot.sheet_names))
        raise typer.Exit(code=2)

    node = graph.trace(
        sheet.name, ref.start.row, ref.start.col, depth=depth, direction=direction
    )
    _print_trace(node, direction)

    if out:
        _write_json(
            {
                "schema_version": "1.0",
                "cellule": node.full_ref,
                "direction": direction,
                "profondeur": depth,
                "trace": node.to_dict(),
            },
            out,
        )
    if mermaid:
        from .render.graphviz import trace_mermaid

        mermaid.write_text(trace_mermaid(node, direction), encoding="utf-8")
        console.print(f"[green]Ecrit :[/green] {mermaid}")


def _print_trace(node, direction: str) -> None:
    heading = "precedents" if direction == "up" else "dependants"
    tree = Tree(_trace_label(node, root=True))
    _grow(tree, node)
    console.print(f"[bold]Trace {heading} de {node.full_ref}[/bold]")
    console.print(tree)


def _trace_label(node, root: bool = False) -> str:
    parts = [f"[bold cyan]{node.full_ref}[/bold cyan]"]
    if node.label:
        parts.append(f"[dim]{node.label}[/dim]")
    if node.formula:
        parts.append(f"[yellow]{node.formula}[/yellow]")
    value = node.value
    if isinstance(value, float):
        parts.append(f"= [green]{value:,.6g}[/green]".replace(",", " "))
    elif value is not None:
        parts.append(f"= [green]{value}[/green]")
    if node.note:
        parts.append(f"[magenta]({node.note})[/magenta]")
    return "  ".join(parts)


def _grow(tree, node) -> None:
    for child in node.children:
        branch = tree.add(_trace_label(child))
        _grow(branch, child)


# ---------------------------------------------------------------------------
# map / feasibility / sensitivity / report / diff
# ---------------------------------------------------------------------------

@app.command("map")
def map_cmd(
    workbook: Path = typer.Argument(...),
    out: Path = typer.Option(..., "--out", help="carte .mmd ou .dot"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Ecrit la carte des dependances entre onglets."""
    from .render.graphviz import write_map

    _snapshot, graph = _load(workbook, cache_dir, no_cache, refresh)
    write_map(graph, out)
    cycles = graph.sheet_cycles()
    console.print(f"[green]Carte ecrite :[/green] {out}")
    if cycles:
        console.print(
            f"[yellow]{len(cycles)} groupe(s) d'onglets en dependance circulaire.[/yellow]"
        )


@app.command()
def feasibility(
    workbook: Path = typer.Argument(...),
    out: Optional[Path] = typer.Option(None, "--out"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Le recalcul hors Excel est-il possible ? Verdict avant toute tentative."""
    from .models import AuditContext
    from .rules.p5_feasibility import assess_feasibility

    snapshot, _graph = _load(workbook, cache_dir, no_cache, refresh, with_graph=False)
    ctx = AuditContext(snapshot=snapshot)
    verdict = assess_feasibility(ctx)

    if verdict.feasible:
        console.print("[green]Recalcul hors Excel envisageable.[/green]")
    else:
        console.print("[red]Recalcul hors Excel refuse.[/red]")
    for blocker in verdict.blockers:
        console.print(f"  [red]obstacle[/red] · {blocker}")
    for warning in verdict.warnings:
        console.print(f"  [yellow]reserve[/yellow] · {warning}")
    if verdict.unsupported:
        table = Table(title="Fonctions non evaluees de facon fiable hors Excel")
        table.add_column("Fonction")
        table.add_column("Occurrences", justify="right")
        for name, count in verdict.unsupported.items():
            table.add_row(name, str(count))
        console.print(table)

    if out:
        _write_json({"schema_version": "1.0", **verdict.to_dict()}, out)
    raise typer.Exit(code=0 if verdict.feasible else 1)


@app.command()
def sensitivity(
    workbook: Path = typer.Argument(...),
    shock: list[str] = typer.Option(
        ..., "--shock", help='p.ex. --shock "production=-5%" (repetable)'
    ),
    mapping: Optional[Path] = typer.Option(None, "--mapping"),
    out: Optional[Path] = typer.Option(None, "--out"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Etendue de propagation d'un choc. L'amplitude n'est pas chiffree."""
    from .models import AuditContext, RunLog, signals_to_document
    from .rules.base import execute, get_rules

    shocks: dict[str, str] = {}
    for item in shock:
        if "=" not in item:
            err_console.print(f"[red]Choc invalide :[/red] {item!r} (attendu cle=valeur)")
            raise typer.Exit(code=2)
        key, value = item.split("=", 1)
        shocks[key.strip()] = value.strip()

    snapshot, graph = _load(workbook, cache_dir, no_cache, refresh)
    ctx = AuditContext(
        snapshot=snapshot, graph=graph, mapping=_load_mapping(mapping),
        options={"shocks": shocks},
    )
    run_log = RunLog(tool_version=TOOL_VERSION)
    run_log.start(str(workbook), snapshot.sha256)
    signals = []
    for rule in get_rules(ids=["R503"]):
        produced, run = execute(rule, ctx)
        signals.extend(produced)
        run_log.add(run)
    run_log.reserves = list(ctx.reserves)
    run_log.finish()

    for sig in signals:
        console.print(f"[bold]{sig.label}[/bold] — {sig.note}")
    console.print(
        "[yellow]L'amplitude du choc n'est pas chiffree :[/yellow] elle exige un "
        "recalcul par Excel, que l'outil refuse de simuler."
    )
    _write_json(signals_to_document(signals, run_log), out)


@app.command()
def report(
    signals_json: Path = typer.Argument(..., help="sortie JSON d'un scan"),
    xlsx: Optional[Path] = typer.Option(None, "--xlsx"),
    md: Optional[Path] = typer.Option(None, "--md"),
    title: str = typer.Option("Rapport xlaudit", "--title"),
):
    """Produit le classeur de constats et le rapport Markdown."""
    from .models import Reserve, RuleRun, RunLog, Signal

    if not signals_json.exists():
        err_console.print(f"[red]Fichier introuvable :[/red] {signals_json}")
        raise typer.Exit(code=2)
    if xlsx is None and md is None:
        err_console.print("[red]Preciser au moins --xlsx ou --md.[/red]")
        raise typer.Exit(code=2)

    document = json.loads(signals_json.read_text(encoding="utf-8"))
    signals = [Signal(**item) for item in document.get("signals", [])]

    run_log = None
    raw_run = document.get("run")
    if raw_run:
        run_log = RunLog(
            workbook=raw_run.get("workbook", ""),
            sha256=raw_run.get("sha256", ""),
            started_at=raw_run.get("started_at", ""),
            finished_at=raw_run.get("finished_at", ""),
            tool_version=raw_run.get("tool_version", TOOL_VERSION),
            schema_version=raw_run.get("schema_version", "1.0"),
            rules=[RuleRun(**r) for r in raw_run.get("rules", [])],
            reserves=[Reserve(**r) for r in raw_run.get("reserves", [])],
        )

    if xlsx:
        from .render.xlsx import write_report

        write_report(signals, xlsx, run_log)
        console.print(f"[green]Classeur de constats :[/green] {xlsx}")
    if md:
        from .render.markdown import write_markdown

        write_markdown(signals, md, run_log, title=title)
        console.print(f"[green]Rapport Markdown :[/green] {md}")


@app.command()
def diff(
    before: Path = typer.Argument(..., help="version anterieure"),
    after: Path = typer.Argument(..., help="version posterieure"),
    mapping: Optional[Path] = typer.Option(None, "--mapping"),
    phases: Optional[str] = typer.Option("2", "--phases"),
    out: Optional[Path] = typer.Option(None, "--out"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
):
    """Non-regression : signaux apparus et disparus entre deux versions."""
    from .models import AuditContext, signals_to_document
    from .rules.base import execute, get_rules

    def run_all(path: Path):
        snapshot, graph = _load(path, cache_dir, False, False, quiet=True)
        ctx = AuditContext(
            snapshot=snapshot, graph=graph, mapping=_load_mapping(mapping)
        )
        produced = []
        for rule in get_rules(phases=_parse_phases(phases)):
            signals, _run = execute(rule, ctx)
            produced.extend(signals)
        return snapshot, produced

    snap_before, signals_before = run_all(before)
    snap_after, signals_after = run_all(after)

    def key(sig):
        return (sig.rule_id, sig.sheet, tuple(sig.refs))

    index_before = {key(s): s for s in signals_before}
    index_after = {key(s): s for s in signals_after}
    appeared = [index_after[k] for k in index_after.keys() - index_before.keys()]
    resolved = [index_before[k] for k in index_before.keys() - index_after.keys()]
    persisted = index_after.keys() & index_before.keys()

    table = Table(title="Non-regression")
    table.add_column("Evolution")
    table.add_column("Nombre", justify="right")
    table.add_row("[red]apparus[/red]", str(len(appeared)))
    table.add_row("[green]disparus[/green]", str(len(resolved)))
    table.add_row("maintenus", str(len(persisted)))
    console.print(table)
    for sig in sorted(appeared, key=lambda s: -s.confidence)[:20]:
        console.print(
            f"  [red]+[/red] [{sig.confidence:.2f}] {sig.rule_id} "
            f"{sig.sheet}!{','.join(sig.refs)} — {sig.note[:120]}"
        )

    document = {
        "schema_version": "1.0",
        "avant": {"classeur": str(before), "sha256": snap_before.sha256},
        "apres": {"classeur": str(after), "sha256": snap_after.sha256},
        "apparus": signals_to_document(appeared)["signals"],
        "disparus": signals_to_document(resolved)["signals"],
        "maintenus": len(persisted),
    }
    _write_json(document, out)


@app.callback()
def main() -> None:
    """xlaudit — aide a l'audit de modeles financiers Excel."""


if __name__ == "__main__":  # pragma: no cover
    app()
