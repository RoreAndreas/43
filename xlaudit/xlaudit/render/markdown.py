"""Rapport Markdown.

Le rapport expose les signaux tries par confiance decroissante et ne masque rien.
Les reserves methodologiques figurent avant les signaux : un lecteur doit savoir
sur quoi les chiffres reposent avant de les lire.
"""

from __future__ import annotations

from pathlib import Path

from ..models import RunLog, Signal


def _fence(text: str) -> str:
    """Encadre une formule pour qu'aucun rendu Markdown ne la reinterprete."""
    if not text:
        return ""
    return "`" + str(text).replace("`", "'") + "`"


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.6g}".replace(",", " ")
    return str(value)


def render_markdown(
    signals: list[Signal],
    run_log: RunLog | None = None,
    title: str = "Rapport xlaudit",
) -> str:
    lines: list[str] = [f"# {title}", ""]

    if run_log:
        lines += [
            "| | |",
            "|---|---|",
            f"| Classeur | `{run_log.workbook}` |",
            f"| Empreinte SHA-256 | `{run_log.sha256}` |",
            f"| Analyse | {run_log.started_at} → {run_log.finished_at} |",
            f"| Version de l'outil | {run_log.tool_version} |",
            f"| Version du schema de sortie | {run_log.schema_version} |",
            "",
        ]

    lines += [
        "> Ce document ne contient que des **signaux** : des faits verifiables et",
        "> chiffres. Il ne contient aucun constat d'audit. Le tri des faux positifs,",
        "> la qualification erreur/convention et l'attribution de criticite",
        "> appartiennent a l'auditeur.",
        "",
    ]

    if run_log and run_log.reserves:
        lines += ["## Reserves methodologiques", ""]
        for reserve in run_log.reserves:
            lines.append(f"- **{reserve.code}** ({reserve.severity}) — {reserve.message}")
        lines.append("")

    lines += _summary(signals, run_log)
    lines += _details(signals)

    if run_log:
        lines += _log_section(run_log)
    return "\n".join(lines) + "\n"


def _summary(signals: list[Signal], run_log: RunLog | None) -> list[str]:
    lines = ["## Synthese", "", f"**{len(signals)} signal(aux)** au total.", ""]
    by_rule: dict[str, list[Signal]] = {}
    for sig in signals:
        by_rule.setdefault(sig.rule_id, []).append(sig)
    if by_rule:
        lines += [
            "| Regle | Phase | Signaux | Confiance max | Chiffrage actif |",
            "|---|---|---|---|---|",
        ]
        for rule_id in sorted(by_rule):
            group = by_rule[rule_id]
            actifs = sum(
                1 for s in group if (s.evidence or {}).get("chiffrage") == "actif"
            )
            lines.append(
                f"| {rule_id} | {group[0].phase} | {len(group)} | "
                f"{max(s.confidence for s in group):.2f} | {actifs} |"
            )
        lines.append("")
    if run_log and run_log.skipped:
        lines += ["### Controles non executes", ""]
        for run in run_log.skipped:
            lines.append(f"- **{run.rule_id}** {run.label} — {run.reason}")
        lines.append("")
    return lines


def _details(signals: list[Signal]) -> list[str]:
    lines = ["## Signaux", "", "_Tries par confiance decroissante._", ""]
    ordered = sorted(signals, key=lambda s: (-s.confidence, s.rule_id, s.sheet))
    for sig in ordered:
        evidence = sig.evidence or {}
        lines.append(
            f"### {sig.rule_id} · {sig.sheet}"
            + (f"!{', '.join(sig.refs)}" if sig.refs else "")
            + f" · confiance {sig.confidence:.2f}"
        )
        lines.append("")
        if sig.label:
            lines.append(f"**Libelle** : {sig.label}")
            lines.append("")
        lines.append(sig.note)
        lines.append("")
        if sig.observed:
            lines.append(f"- Relevé : {_fence(sig.observed)}")
        if sig.expected:
            lines.append(f"- Attendu : {_fence(sig.expected)}")
        if evidence.get("chiffrage"):
            lines.append(
                f"- Chiffrage : **{evidence['chiffrage']}**, ecart maximal "
                f"{_fmt(evidence.get('ecart_max_absolu'))} sur "
                f"{len(evidence.get('colonnes_touchees') or [])} colonne(s)"
                + (
                    " — valeur en cache conforme a la formule ecrite"
                    if evidence.get("cache_confirme_la_formule")
                    else ""
                )
            )
        if sig.consumers:
            shown = ", ".join(sig.consumers[:8])
            more = f" (+{len(sig.consumers) - 8})" if len(sig.consumers) > 8 else ""
            lines.append(f"- Consommateurs : {shown}{more}")
        elif sig.rule_id == "R215":
            lines.append("- Consommateurs : **aucun**")
        lines.append("")
        lines += _evidence_table(evidence)
    return lines


def _evidence_table(evidence: dict) -> list[str]:
    detail = evidence.get("detail_colonnes") or []
    rows = [d for d in detail if d.get("ecart") is not None]
    if not rows:
        return []
    lines = [
        "| Colonne | Cache | Recalcul (formule ecrite) | Recalcul (attendu) | Ecart |",
        "|---|---|---|---|---|",
    ]
    for row in rows[:20]:
        lines.append(
            f"| {row.get('ref')} | {_fmt(row.get('cache'))} | "
            f"{_fmt(row.get('recalcul_formule_ecrite'))} | "
            f"{_fmt(row.get('recalcul_formule_attendue'))} | {_fmt(row.get('ecart'))} |"
        )
    lines.append("")
    return lines


def _log_section(run_log: RunLog) -> list[str]:
    lines = ["## Journal d'execution", "",
             "| Regle | Libelle | Phase | Statut | Signaux | Duree (s) | Motif |",
             "|---|---|---|---|---|---|---|"]
    for run in run_log.rules:
        lines.append(
            f"| {run.rule_id} | {run.label} | {run.phase} | {run.status} | "
            f"{run.signals} | {run.duration_s} | {run.reason or '—'} |"
        )
    lines.append("")
    return lines


def write_markdown(
    signals: list[Signal],
    path: str | Path,
    run_log: RunLog | None = None,
    title: str = "Rapport xlaudit",
) -> Path:
    path = Path(path)
    path.write_text(render_markdown(signals, run_log, title), encoding="utf-8")
    return path
