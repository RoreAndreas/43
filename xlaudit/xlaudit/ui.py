"""Couche de donnees de l'interface Streamlit.

Separee de `app.py` pour une raison pratique : un script Streamlit ne s'importe
pas — `st.stop()` n'a aucun effet hors du moteur d'execution, si bien qu'importer
le script pour en tester une fonction ferait derouler toute l'interface. Tout ce
qui n'est pas de la mise en page vit donc ici, ou les tests peuvent l'atteindre.

Streamlit n'est requis que pour les decorateurs de cache ; il fait partie de
l'extra `ui` du paquet.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any, Protocol

import streamlit as st

from . import __version__
from .core.graph import build_graph
from .core.loader import get_snapshot, load_vba
from .models import AuditContext, Reserve, RuleRun, RunLog, Signal, signals_to_document
from .rules.base import execute, get_rules

WORK_DIR = Path(tempfile.gettempdir()) / "xlaudit_streamlit"
CACHE_DIR = WORK_DIR / "cache"

PHASES = {
    1: "Phase 1 — Cartographie",
    2: "Phase 2 — Formules",
    3: "Phase 3 — Bouclages (mapping requis)",
    4: "Phase 4 — Chaînes et reconstitution",
    5: "Phase 5 — Faisabilité et chocs",
}

CHIFFRAGE_LABEL = {
    "actif": "🔴 actif",
    "latent": "🟠 latent",
    "nul": "⚪ nul",
    "indetermine": "❔ indéterminé",
}


class UploadLike(Protocol):
    """Ce que fournit `st.file_uploader` : des octets et un nom d'origine."""

    name: str

    def getvalue(self) -> bytes: ...


def persist_upload(uploaded: UploadLike, work_dir: Path | None = None) -> tuple[Path, str]:
    """Ecrit le fichier joint sur disque, une seule fois par contenu.

    L'empreinte est calculee sur les octets recus : c'est elle qui sert de clef
    de cache. Deux depots du meme fichier ne relancent donc jamais la collecte,
    et un fichier modifie ne peut pas etre servi depuis le cache par erreur.
    """
    base = work_dir or WORK_DIR
    base.mkdir(parents=True, exist_ok=True)
    payload = uploaded.getvalue()
    sha = hashlib.sha256(payload).hexdigest()
    target = base / f"{sha[:16]}{Path(uploaded.name).suffix or '.xlsx'}"
    if not target.exists():
        target.write_bytes(payload)
    return target, sha


def resolve_path(sha: str, work_dir: Path | None = None) -> Path:
    """Retrouve le fichier temporaire d'une empreinte.

    Le motif exclut les livrables derives (`<sha>_constats.xlsx`), qui portent un
    souligne la ou le classeur source porte un point.
    """
    base = work_dir or WORK_DIR
    for candidate in sorted(base.glob(f"{sha[:16]}.*")):
        return candidate
    raise FileNotFoundError(
        "Le fichier joint n'est plus disponible sur le serveur ; le redéposer."
    )


@st.cache_resource(show_spinner=False, max_entries=3)
def load_model(sha: str, _path: Path, _progress=None):
    """Collecte et graphe de dependances, mis en cache par empreinte du fichier.

    Objets lourds et immuables : `cache_resource` les partage sans les serialiser.
    Les parametres prefixes d'un souligne n'entrent pas dans la clef de cache
    (convention Streamlit) ; l'empreinte suffit a identifier le classeur.
    """
    snapshot, from_cache = get_snapshot(_path, cache_dir=CACHE_DIR, progress=_progress)
    if not snapshot.vba:
        snapshot.vba = load_vba(_path)
    graph = build_graph(snapshot, progress=_progress)
    return snapshot, graph, from_cache


@st.cache_data(show_spinner=False, max_entries=8)
def run_rules(
    sha: str,
    phases: tuple[int, ...],
    rule_ids: tuple[str, ...],
    mapping_text: str | None,
) -> dict:
    """Execute les regles et rend le document JSON, mis en cache.

    Le mapping entre dans la clef sous forme de texte : le modifier relance
    l'analyse, ce qui est le comportement attendu.
    """
    snapshot, graph, _ = load_model(sha, resolve_path(sha))

    mapping_model = None
    validation: list[dict] = []
    if mapping_text and mapping_text.strip():
        import yaml

        from .mapping.schema import MappingModel
        from .mapping.validate import validate_mapping

        mapping_model = MappingModel.model_validate(yaml.safe_load(mapping_text) or {})
        validation = [r.to_dict() for r in validate_mapping(snapshot, mapping_model)]

    run_log = RunLog(tool_version=__version__)
    run_log.start(snapshot.path, snapshot.sha256)
    ctx = AuditContext(snapshot=snapshot, graph=graph, mapping=mapping_model)

    signals: list[Signal] = []
    for rule in get_rules(phases=list(phases) or None, ids=list(rule_ids) or None):
        produced, run = execute(rule, ctx)
        signals.extend(produced)
        run_log.add(run)
    run_log.reserves = list(ctx.reserves)
    run_log.finish()

    document = signals_to_document(signals, run_log)
    document["validation_mapping"] = validation
    return document


def restore_run_log(raw: dict) -> RunLog:
    """Reconstruit un `RunLog` depuis le document JSON, pour les rendus."""
    log = RunLog(
        workbook=raw.get("workbook", ""),
        sha256=raw.get("sha256", ""),
        started_at=raw.get("started_at", ""),
        finished_at=raw.get("finished_at", ""),
        tool_version=raw.get("tool_version", __version__),
        schema_version=raw.get("schema_version", "1.0"),
    )
    log.rules = [RuleRun(**r) for r in raw.get("rules", [])]
    log.reserves = [Reserve(**r) for r in raw.get("reserves", [])]
    return log


def restore_signals(items: list[dict]) -> list[Signal]:
    return [Signal(**item) for item in items]


def format_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, (int, float)):
        return f"{value:,.4g}".replace(",", " ")
    return str(value)


def signal_rows(signals: list[dict]) -> list[dict]:
    """Aplatit les signaux en lignes de tableau."""
    rows = []
    for sig in signals:
        evidence = sig.get("evidence") or {}
        rows.append(
            {
                "Règle": sig["rule_id"],
                "Confiance": round(sig["confidence"], 2),
                "Onglet": sig["sheet"],
                "Références": ", ".join(sig.get("refs") or []),
                "Libellé": sig.get("label") or "",
                "Chiffrage": CHIFFRAGE_LABEL.get(evidence.get("chiffrage"), ""),
                "Écart max": evidence.get("ecart_max_absolu"),
                "Constat": sig.get("note") or "",
            }
        )
    return rows


def filter_signals(
    signals: list[dict],
    min_confidence: float = 0.0,
    rules: list[str] | None = None,
    sheets: list[str] | None = None,
) -> list[dict]:
    """Filtre **d'affichage** uniquement.

    Les exports repartent toujours de la liste complete : la specification
    interdit d'ecarter un signal silencieusement.
    """
    out = [s for s in signals if s["confidence"] >= min_confidence]
    if rules is not None:
        out = [s for s in out if s["rule_id"] in rules]
    if sheets is not None:
        out = [s for s in out if s["sheet"] in sheets]
    return out


def trace_lines(node: dict, depth: int = 0) -> list[str]:
    """Rend l'arbre de trace en lignes indentees, comme la sortie de la CLI."""
    prefix = "    " * depth + ("└── " if depth else "")
    parts = [f"{prefix}{node['ref']}"]
    if node.get("label"):
        parts.append(f"  [{node['label']}]")
    if node.get("formula"):
        parts.append(f"  {node['formula']}")
    if node.get("value") is not None:
        parts.append(f"  = {format_number(node['value'])}")
    if node.get("note"):
        parts.append(f"  ({node['note']})")
    lines = ["".join(parts)]
    for child in node.get("children") or []:
        lines.extend(trace_lines(child, depth + 1))
    return lines
