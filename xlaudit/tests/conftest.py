"""Fixtures partagees.

Les deux classeurs sont construits une fois par session : leur construction
implique une reecriture du XML pour y injecter les valeurs en cache, ce qui n'a
pas a etre refait a chaque test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xlaudit.core import loader as L
from xlaudit.core.graph import build_graph
from xlaudit.models import AuditContext

from .fixtures import build_faulty, build_healthy

MAPPING_PATH = Path(__file__).parent / "mapping_fixture.yaml"


def _context(path: Path) -> AuditContext:
    snapshot = L.collect(path)
    return AuditContext(snapshot=snapshot, graph=build_graph(snapshot))


@pytest.fixture(scope="session")
def healthy_path(tmp_path_factory) -> Path:
    return build_healthy(tmp_path_factory.mktemp("classeurs") / "sain.xlsx")


@pytest.fixture(scope="session")
def faulty_path(tmp_path_factory) -> Path:
    return build_faulty(tmp_path_factory.mktemp("classeurs") / "anomalies.xlsx")


@pytest.fixture(scope="session")
def healthy_ctx(healthy_path) -> AuditContext:
    return _context(healthy_path)


@pytest.fixture(scope="session")
def faulty_ctx(faulty_path) -> AuditContext:
    return _context(faulty_path)


def signals_of(rule, ctx, sheet: str | None = "Modele"):
    """Signaux d'une regle, eventuellement restreints a un onglet."""
    out = rule.run(ctx)
    if sheet is not None:
        out = [s for s in out if s.sheet == sheet]
    return out


def refs_of(signals) -> set[str]:
    return {ref for s in signals for ref in s.refs}
