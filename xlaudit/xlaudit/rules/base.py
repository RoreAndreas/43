"""Classe de base des regles et registre.

Une regle recoit un `AuditContext` et rend une liste de `Signal`. Elle n'ouvre
jamais le classeur : le passage de collecte est unique.

Chaque regle documente, dans sa docstring, **comment elle calcule `confidence`**.
C'est une exigence du contrat : la confiance est une aide au tri, jamais un
verdict, et un tri dont on ignore la regle de calcul ne vaut rien.
"""

from __future__ import annotations

import time
from typing import Iterable

from ..models import AuditContext, RuleRun, Signal


class Rule:
    """Contrat commun a toutes les regles."""

    id: str = ""
    label: str = ""
    phase: int = 2
    requires_mapping: bool = False
    #: Renseigne quand la regle a besoin d'un service optionnel (graphe, VBA).
    requires_graph: bool = False

    def run(self, ctx: AuditContext) -> list[Signal]:  # pragma: no cover - interface
        raise NotImplementedError

    # -- confort -----------------------------------------------------------
    def signal(self, **kwargs) -> Signal:
        kwargs.setdefault("rule_id", self.id)
        kwargs.setdefault("phase", self.phase)
        return Signal(**kwargs)

    def __repr__(self) -> str:  # pragma: no cover - confort de debug
        return f"<{self.id} {self.label}>"


REGISTRY: dict[str, type[Rule]] = {}


def register(cls: type[Rule]) -> type[Rule]:
    """Enregistre une regle. L'identifiant doit etre unique."""
    if not cls.id:
        raise ValueError(f"{cls.__name__} n'a pas d'identifiant")
    if cls.id in REGISTRY and REGISTRY[cls.id] is not cls:
        raise ValueError(f"identifiant de regle en double : {cls.id}")
    REGISTRY[cls.id] = cls
    return cls


def load_all_rules() -> None:
    """Importe les modules de regles pour peupler le registre."""
    from . import (  # noqa: F401
        p1_cartography,
        p2_r201_cached_errors,
        p2_r202_hardcoded,
        p2_r203_horizontal,
        p2_r204_copy_drift,
        p2_r205_anchoring,
        p2_r206_truncated_sum,
        p2_r207_sumif_width,
        p2_r208_heterogeneous_sum,
        p2_r215_orphans,
        p3_ties,
        p4_chains,
        p5_feasibility,
    )


def get_rules(
    phases: Iterable[int] | None = None,
    ids: Iterable[str] | None = None,
) -> list[Rule]:
    """Instancie les regles demandees, triees par identifiant."""
    load_all_rules()
    wanted_phases = set(phases) if phases else None
    wanted_ids = {i.upper() for i in ids} if ids else None
    out = []
    for rule_id, cls in sorted(REGISTRY.items()):
        if wanted_ids is not None and rule_id.upper() not in wanted_ids:
            continue
        if wanted_phases is not None and cls.phase not in wanted_phases:
            continue
        out.append(cls())
    return out


def execute(rule: Rule, ctx: AuditContext) -> tuple[list[Signal], RuleRun]:
    """Execute une regle en journalisant son issue.

    Une regle qui echoue n'interrompt pas le scan : son echec est consigne et les
    autres regles continuent. Un rapport doit dire ce qu'il n'a pas pu regarder.
    """
    started = time.perf_counter()
    run = RuleRun(rule_id=rule.id, label=rule.label, phase=rule.phase, status="executed")

    if rule.requires_mapping and ctx.mapping is None:
        run.status = "skipped"
        run.reason = "aucun mapping fourni"
        run.duration_s = round(time.perf_counter() - started, 3)
        return [], run

    try:
        signals = rule.run(ctx)
    except Exception as exc:  # une regle fautive ne doit pas tuer le scan
        run.status = "error"
        run.reason = f"{type(exc).__name__}: {exc}"
        run.duration_s = round(time.perf_counter() - started, 3)
        return [], run

    run.signals = len(signals)
    run.duration_s = round(time.perf_counter() - started, 3)
    return signals, run
