"""Modele de donnees de xlaudit.

`Signal` est l'unique interface entre le moteur et l'humain. Toute regle en emet ;
rien d'autre ne sort du moteur. Un signal est un *fait* : verifiable, chiffre, trace.
Il ne porte aucun jugement sur le caractere volontaire ou non de l'anomalie.

Regle de conception appliquee partout : un signal doit contenir tout ce qu'il faut
pour etre juge sans rouvrir le classeur.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Any

# Contrat avec les outils en aval. Toute rupture de compatibilite incremente le majeur.
SCHEMA_VERSION = "1.0"


def _jsonable(value: Any) -> Any:
    """Rend une valeur serialisable en JSON sans perte de sens.

    Les valeurs remontees d'Excel peuvent etre des dates, des Decimal ou des
    objets openpyxl ; on les degrade en types JSON plutot que de faire echouer
    l'ecriture du rapport.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


@dataclass
class Signal:
    """Un fait releve par une regle.

    Attributes:
        rule_id: identifiant de la regle, p.ex. "R205".
        phase: phase d'analyse (1 cartographie, 2 formules, 3 bouclages, ...).
        sheet: onglet concerne.
        refs: references concernees, p.ex. ["S495", "AG495"] ou ["495:497"].
        label: libelle de la ligne dans le modele, si trouve.
        observed: formule ou valeur telle que relevee.
        expected: formule majoritaire du voisinage, cellule jumelle, ou None.
        evidence: chiffrage (ecart max, colonnes touchees, totaux, blocs sources).
        consumers: qui consomme la ligne concernee, en "Onglet!ligne".
        confidence: 0-1, vraisemblance que ce ne soit pas un faux positif.
        note: ce que la regle a detecte, factuellement.
    """

    rule_id: str
    phase: int
    sheet: str
    refs: list[str] = field(default_factory=list)
    label: str = ""
    observed: str = ""
    expected: str | None = None
    evidence: dict = field(default_factory=dict)
    consumers: list[str] = field(default_factory=list)
    confidence: float = 0.5
    note: str = ""

    def __post_init__(self) -> None:
        # La confiance est une aide au tri : on la borne mais on ne filtre jamais.
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @property
    def location(self) -> str:
        """Localisation lisible, utilisable telle quelle dans un rapport."""
        if not self.refs:
            return self.sheet
        return f"{self.sheet}!{','.join(self.refs)}"

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


@dataclass
class Finding:
    """Constat d'audit : produit *par un humain ou un LLM* a partir de signaux.

    xlaudit n'en emet jamais. Le type existe parce que la sortie JSON de l'outil
    est relue par l'etape de redaction, qui rattache sa qualification aux signaux
    d'origine ; `render` sait afficher les deux.
    """

    finding_id: str
    title: str
    severity: str  # libre : l'outil ne definit pas d'echelle de criticite
    signals: list[Signal] = field(default_factory=list)
    rationale: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        d = _jsonable(asdict(self))
        return d


@dataclass
class Reserve:
    """Reserve methodologique attachee au classeur, propagee dans tous les rapports.

    Exemple : calcOnSave="0" signifie que les valeurs en cache ne sont pas
    l'etat converge du modele. Tout chiffrage adosse au cache en herite.
    """

    code: str
    message: str
    severity: str = "info"  # info | warning | blocking

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


@dataclass
class RuleRun:
    """Trace d'execution d'une regle, pour le journal."""

    rule_id: str
    label: str
    phase: int
    status: str  # executed | skipped | error
    signals: int = 0
    reason: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


@dataclass
class RunLog:
    """Journal d'execution horodate, avec empreinte du fichier.

    Liste les regles executees et celles qui ont ete sautees faute de mapping :
    un rapport doit dire ce qu'il n'a pas regarde.
    """

    workbook: str = ""
    sha256: str = ""
    started_at: str = ""
    finished_at: str = ""
    tool_version: str = "0.6.0"
    schema_version: str = SCHEMA_VERSION
    rules: list[RuleRun] = field(default_factory=list)
    reserves: list[Reserve] = field(default_factory=list)

    def start(self, workbook: str, sha256: str) -> None:
        self.workbook = workbook
        self.sha256 = sha256
        self.started_at = _dt.datetime.now().astimezone().isoformat(timespec="seconds")

    def finish(self) -> None:
        self.finished_at = _dt.datetime.now().astimezone().isoformat(timespec="seconds")

    def add(self, run: RuleRun) -> None:
        self.rules.append(run)

    @property
    def skipped(self) -> list[RuleRun]:
        return [r for r in self.rules if r.status == "skipped"]

    def to_dict(self) -> dict:
        return {
            "workbook": self.workbook,
            "sha256": self.sha256,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tool_version": self.tool_version,
            "schema_version": self.schema_version,
            "rules": [r.to_dict() for r in self.rules],
            "reserves": [r.to_dict() for r in self.reserves],
        }


@dataclass
class AuditContext:
    """Tout ce qu'une regle a le droit de regarder.

    Une regle recoit ce contexte et rend des signaux. Elle n'ouvre jamais le
    classeur elle-meme : le passage de collecte est unique (contrainte de perf),
    et l'acces aux cellules passe par le snapshot.
    """

    snapshot: Any  # core.loader.Snapshot ; annote Any pour eviter un import circulaire
    graph: Any = None  # core.graph.DependencyGraph, construit a la demande
    mapping: Any = None  # mapping.schema.MappingModel | None
    reserves: list[Reserve] = field(default_factory=list)
    options: dict = field(default_factory=dict)

    def add_reserve(self, code: str, message: str, severity: str = "info") -> None:
        if not any(r.code == code for r in self.reserves):
            self.reserves.append(Reserve(code=code, message=message, severity=severity))


def signals_to_document(
    signals: list[Signal],
    run_log: RunLog | None = None,
) -> dict:
    """Enveloppe JSON stable : c'est le contrat avec les outils en aval.

    Les signaux sont tries par confiance decroissante puis par localisation, jamais
    filtres : le tri des faux positifs appartient a l'auditeur.
    """
    ordered = sorted(
        signals,
        key=lambda s: (-s.confidence, s.rule_id, s.sheet, s.refs[0] if s.refs else ""),
    )
    doc: dict = {
        "schema_version": SCHEMA_VERSION,
        "signal_count": len(ordered),
        "signals": [s.to_dict() for s in ordered],
    }
    if run_log is not None:
        doc["run"] = run_log.to_dict()
    return doc
