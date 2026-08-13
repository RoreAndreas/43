"""Interface Streamlit de xlaudit.

Le classeur est joint depuis le navigateur, jamais lu depuis un chemin serveur :
l'utilisateur depose son modele, l'outil l'ecrit dans un fichier temporaire et
l'analyse a partir de la. Le fichier joint n'est jamais modifie.

L'interface reprend la frontiere de l'outil : elle affiche des **signaux**, pas
des constats d'audit. Le curseur de confiance ne filtre que l'affichage ; les
exports contiennent toujours l'integralite des signaux.

Ce fichier ne contient que de la mise en page. Toute la logique est dans
`xlaudit.ui`, ou elle est testable.

Lancement :
    streamlit run app.py
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Permet `streamlit run app.py` sans installation prealable du paquet.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from xlaudit import __version__
from xlaudit.core import refs as R
from xlaudit.render.graphviz import sheet_map_dot
from xlaudit.render.markdown import render_markdown
from xlaudit.render.xlsx import write_report
from xlaudit.ui import (
    PHASES, WORK_DIR, filter_signals, format_number, get_model, persist_upload,
    restore_run_log, restore_signals, run_rules, signal_rows, trace_lines,
)

st.set_page_config(
    page_title="xlaudit — audit de modèles financiers",
    page_icon="🔍",
    layout="wide",
)


# ─── Affichage d'un signal ────────────────────────────────────────────────────

def render_signal_detail(sig: dict) -> None:
    """Tout ce qu'il faut pour juger le signal sans rouvrir le classeur."""
    evidence = sig.get("evidence") or {}

    head = f"**{sig['rule_id']}** · {sig['sheet']}"
    if sig.get("refs"):
        head += f"!{', '.join(sig['refs'])}"
    head += f" · confiance **{sig['confidence']:.2f}**"
    st.markdown(head)
    if sig.get("label"):
        st.caption(f"Libellé de la ligne : {sig['label']}")
    st.write(sig.get("note") or "")

    left, right = st.columns(2)
    with left:
        st.caption("Relevé")
        st.code(sig.get("observed") or "—", language="text")
    with right:
        st.caption("Attendu")
        st.code(sig.get("expected") or "— (aucune correction proposée)", language="text")

    if evidence.get("chiffrage"):
        cols = st.columns(4)
        cols[0].metric("Chiffrage", evidence["chiffrage"])
        cols[1].metric("Écart maximal", format_number(evidence.get("ecart_max_absolu")))
        cols[2].metric("Colonnes touchées", len(evidence.get("colonnes_touchees") or []))
        cols[3].metric(
            "Cache conforme",
            "oui" if evidence.get("cache_confirme_la_formule") else "non",
        )

    detail = [
        d for d in (evidence.get("detail_colonnes") or []) if d.get("ecart") is not None
    ]
    if detail:
        st.caption("Chiffrage colonne par colonne")
        st.dataframe(
            pd.DataFrame(detail).rename(
                columns={
                    "colonne": "Colonne", "ref": "Référence", "cache": "Valeur en cache",
                    "recalcul_formule_ecrite": "Recalcul (formule écrite)",
                    "recalcul_formule_attendue": "Recalcul (attendu)",
                    "ecart": "Écart", "statut": "Statut",
                }
            ),
            width="stretch", hide_index=True,
        )

    if sig.get("consumers"):
        st.caption(f"Consommateurs de la ligne ({len(sig['consumers'])})")
        st.write(", ".join(sig["consumers"][:40]))
    elif sig["rule_id"] == "R215":
        st.caption("Consommateurs")
        st.write("**Aucun** — la ligne est calculée et personne ne la lit.")

    with st.expander("Évidence complète (JSON)"):
        st.json(evidence)


# ─── Barre latérale : dépôt du classeur et périmètre ──────────────────────────

st.sidebar.title("🔍 xlaudit")
st.sidebar.caption(f"version {__version__}")

uploaded = st.sidebar.file_uploader(
    "Joindre le modèle financier",
    type=["xlsx", "xlsm", "xltm", "xlsb"],
    help="Le fichier est copié dans un dossier temporaire pour être lu. Il n'est jamais modifié.",
)

if uploaded is None:
    st.title("Audit de modèles financiers Excel")
    st.markdown(
        """
        Déposez un classeur `.xlsx` ou `.xlsm` dans la barre latérale pour démarrer.

        Cet outil produit des **signaux** : des faits vérifiables, chiffrés et tracés.
        Il ne produit **aucun constat d'audit**. Le tri des faux positifs, la
        qualification erreur/convention et l'attribution de criticité restent à
        l'auditeur.

        Chaque signal contient tout ce qu'il faut pour être jugé sans rouvrir le
        classeur : la formule exacte, la formule majoritaire du voisinage, l'écart
        chiffré sur toutes les colonnes, et la liste des lignes qui consomment la
        ligne en cause.
        """
    )
    st.info(
        "Classeur volumineux : la première analyse d'un modèle de plusieurs centaines "
        "de milliers de formules prend quelques minutes. Le résultat est ensuite mis "
        "en cache et les interactions redeviennent instantanées."
    )
    st.stop()

path, sha = persist_upload(uploaded)

st.sidebar.divider()
selected_phases = st.sidebar.multiselect(
    "Phases à exécuter", options=list(PHASES), default=[1, 2],
    format_func=lambda p: PHASES[p],
)

mapping_file = st.sidebar.file_uploader(
    "Mapping (facultatif, requis pour la phase 3)", type=["yaml", "yml"]
)
if mapping_file is not None:
    st.session_state["mapping_text"] = mapping_file.getvalue().decode("utf-8")
mapping_text = st.session_state.get("mapping_text") or None

st.sidebar.divider()
min_confidence = st.sidebar.slider(
    "Confiance minimale affichée", 0.0, 1.0, 0.0, 0.05,
    help=(
        "Filtre d'affichage uniquement. Les exports contiennent toujours "
        "l'intégralité des signaux : rien n'est jamais écarté silencieusement."
    ),
)

if st.sidebar.button("Vider le cache et relire", width="stretch"):
    from xlaudit.ui import MODEL_SLOT

    st.session_state.pop(MODEL_SLOT, None)  # le modele vit en session, pas au cache
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()


# ─── Chargement ───────────────────────────────────────────────────────────────

progress_slot = st.empty()
bar = progress_slot.progress(0.0, text="Lecture du classeur…")


def report(stage: str, done: int, total: int) -> None:
    bar.progress(min(done / max(total, 1), 1.0), text=f"{stage} — {done}/{total}")


started = time.perf_counter()
try:
    snapshot, graph, from_cache = get_model(sha, path, report)
except Exception as exc:  # un classeur illisible doit le dire clairement
    progress_slot.empty()
    st.error(f"Lecture impossible : {type(exc).__name__} — {exc}")
    st.stop()
progress_slot.empty()

header = st.columns(5)
header[0].metric("Onglets", len(snapshot.sheets))
header[1].metric("Formules", f"{snapshot.formula_count:,}".replace(",", " "))
header[2].metric("Noms définis", len(snapshot.defined_names))
header[3].metric("VBA", "oui" if (snapshot.vba or {}).get("has_vba") else "non")
header[4].metric(
    "Chargement", "cache" if from_cache else f"{time.perf_counter() - started:.1f} s"
)
st.caption(f"`{uploaded.name}` · empreinte SHA-256 `{sha[:32]}…`")

if snapshot.formula_count == 0:
    st.info(
        "Ce classeur ne contient aucune formule : les règles de la phase 2 n'ont rien "
        "à examiner. C'est le cas d'un export de données."
    )
if 3 in selected_phases and not mapping_text:
    st.warning(
        "La phase 3 est sélectionnée mais aucun mapping n'est fourni : ses contrôles "
        "seront déclarés sautés. Utilisez l'onglet **Bouclages** pour en générer un."
    )


# ─── Exécution des règles ─────────────────────────────────────────────────────

with st.spinner("Exécution des règles… (plusieurs minutes sur un gros modèle)"):
    try:
        document = run_rules(
            sha, tuple(selected_phases), (), mapping_text, snapshot, graph
        )
    except Exception as exc:
        st.error(f"Analyse interrompue : {type(exc).__name__} — {exc}")
        st.stop()

signals = document["signals"]
run_log = document.get("run") or {}

for reserve in run_log.get("reserves") or []:
    st.warning(f"**Réserve {reserve['code']}** — {reserve['message']}")

tab_signaux, tab_trace, tab_carto, tab_mapping, tab_export = st.tabs(
    ["Signaux", "Trace", "Cartographie", "Bouclages", "Export"]
)


# ─── Signaux ──────────────────────────────────────────────────────────────────

with tab_signaux:
    rules_present = sorted({s["rule_id"] for s in signals})
    sheets_present = sorted({s["sheet"] for s in signals})
    filters = st.columns(2)
    keep_rules = filters[0].multiselect("Règles", rules_present, default=rules_present)
    keep_sheets = filters[1].multiselect("Onglets", sheets_present, default=sheets_present)
    visible = filter_signals(signals, min_confidence, keep_rules, keep_sheets)

    counters = st.columns(4)
    counters[0].metric("Signaux affichés", len(visible))
    counters[1].metric("Total produit", len(signals))
    counters[2].metric("Confiance ≥ 0.85", sum(1 for s in visible if s["confidence"] >= 0.85))
    counters[3].metric(
        "Chiffrage actif",
        sum(1 for s in visible if (s.get("evidence") or {}).get("chiffrage") == "actif"),
    )

    hidden = len(signals) - len(filter_signals(signals, min_confidence))
    if hidden:
        st.caption(
            f"{hidden} signal(aux) masqué(s) par le curseur de confiance — "
            f"ils restent présents dans les exports."
        )

    if not visible:
        st.success("Aucun signal pour ce périmètre.")
    else:
        event = st.dataframe(
            pd.DataFrame(signal_rows(visible)),
            width="stretch", hide_index=True,
            on_select="rerun", selection_mode="single-row",
            column_config={
                "Confiance": st.column_config.ProgressColumn(
                    "Confiance", min_value=0.0, max_value=1.0, format="%.2f"
                ),
                "Écart max": st.column_config.NumberColumn("Écart max", format="%.4g"),
            },
        )
        chosen = event.selection.rows if event and event.selection else []
        st.divider()
        if chosen:
            render_signal_detail(visible[chosen[0]])
        else:
            st.info("Sélectionnez une ligne du tableau pour en voir le détail chiffré.")


# ─── Trace ────────────────────────────────────────────────────────────────────

with tab_trace:
    st.markdown(
        "Remonter les précédents d'une cellule, ou descendre vers ses dépendants. "
        "Chaque maillon porte sa formule et sa valeur."
    )
    controls = st.columns([3, 2, 2, 2])
    sheet_name = controls[0].selectbox("Onglet", snapshot.sheet_names)
    cell_ref = controls[1].text_input("Cellule", value="A1")
    direction = controls[2].radio(
        "Sens", ["up", "down"],
        format_func=lambda d: "Précédents" if d == "up" else "Dépendants",
        horizontal=True,
    )
    depth = controls[3].number_input("Profondeur", 1, 12, 3)

    if st.button("Tracer", type="primary"):
        parsed = R.parse_ref((cell_ref or "").strip())
        if parsed is None or not parsed.is_single:
            st.error(
                f"Référence invalide : {cell_ref!r}. Attendu une cellule, p. ex. `S495`."
            )
        else:
            node = graph.trace(
                sheet_name, parsed.start.row, parsed.start.col,
                depth=int(depth), direction=direction,
            ).to_dict()
            st.code("\n".join(trace_lines(node)), language="text")
            st.download_button(
                "Télécharger la trace (JSON)",
                json.dumps(node, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"trace_{sheet_name}_{cell_ref}.json",
                mime="application/json",
            )


# ─── Cartographie ─────────────────────────────────────────────────────────────

with tab_carto:
    st.subheader("Onglets")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Onglet": s.name, "État": s.state, "Formules": len(s.formulas),
                    "Valeurs": len(s.values), "Dernière ligne": s.max_row,
                    "Dernière colonne": R.index_to_col(s.max_col),
                }
                for s in sorted(snapshot.sheets.values(), key=lambda x: x.index)
            ]
        ),
        width="stretch", hide_index=True,
    )

    st.subheader("Dépendances entre onglets")
    if graph.sheet_graph.number_of_edges():
        st.graphviz_chart(sheet_map_dot(graph), width="stretch")
    else:
        st.info("Aucune dépendance entre onglets : ils ne se citent pas mutuellement.")

    cycles = graph.cycles()
    recurrences = graph.temporal_recurrences()
    cols = st.columns(2)
    with cols[0]:
        st.metric("Circularités réelles", len(cycles))
        if cycles:
            st.caption("Lignes en dépendance mutuelle sur la même période")
            for comp in cycles[:5]:
                st.write("· " + ", ".join(comp[:12]))
    with cols[1]:
        st.metric("Récurrences temporelles", len(recurrences))
        st.caption(
            "Enchaînements période à période (ouverture = clôture précédente). "
            "Ce ne sont pas des circularités."
        )

    if snapshot.defined_names:
        with st.expander(f"Noms définis ({len(snapshot.defined_names)})"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Nom": n.name, "Portée": n.scope or "(globale)",
                            "Cible": n.refers_to, "Masqué": n.hidden,
                        }
                        for n in snapshot.defined_names
                    ]
                ),
                width="stretch", hide_index=True,
            )

    vba = snapshot.vba or {}
    if vba.get("has_vba"):
        with st.expander("Code VBA"):
            st.write(
                f"{len(vba.get('modules', []))} module(s), "
                f"{len(vba.get('macros', []))} procédure(s)"
            )
            if vba.get("circularity_hints"):
                st.warning(
                    "Plages nommées évoquant une boucle de résolution de circularité : "
                    + ", ".join(vba["circularity_hints"][:8])
                )
            st.json(vba)


# ─── Bouclages ────────────────────────────────────────────────────────────────

with tab_mapping:
    st.markdown(
        "Les bouclages comptables exigent de localiser les grandeurs du modèle. "
        "`discover` **propose**, il ne conclut pas : rien ne s'exécute sur une "
        "localisation que la validation numérique n'a pas confirmée."
    )

    if st.button("Proposer un mapping (discover)"):
        import yaml as _yaml

        from xlaudit.mapping.discover import discover
        from xlaudit.mapping.schema import mapping_to_dict

        proposal, found = discover(snapshot)
        if proposal is None:
            st.error(
                "Aucune grandeur reconnue par recherche de libellés. Le mapping doit "
                "être écrit à la main."
            )
        else:
            st.session_state["mapping_text"] = _yaml.safe_dump(
                mapping_to_dict(proposal), allow_unicode=True, sort_keys=False
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Clé": d.key,
                            "Localisation": f"{d.best.sheet}!{d.best.row}",
                            "Libellé": d.best.label, "Score": d.best.score,
                            "Ambigu": "oui" if d.ambiguous else "",
                        }
                        for d in found
                    ]
                ),
                width="stretch", hide_index=True,
            )
            st.warning(
                "Aucune localisation n'est confirmée. Relisez le mapping ci-dessous, "
                "corrigez-le, puis validez."
            )

    # Pas de `key=` ici : la valeur est pilotee par st.session_state["mapping_text"],
    # et un widget a clef ignorerait `value=` apres la premiere execution — le
    # mapping propose par `discover` ne s'afficherait jamais.
    edited = st.text_area(
        "Mapping YAML", value=st.session_state.get("mapping_text", ""), height=320
    )
    action = st.columns(3)
    if action[0].button("Valider et exécuter les bouclages", type="primary"):
        st.session_state["mapping_text"] = edited
        st.rerun()
    action[1].download_button(
        "Télécharger le mapping", (edited or "").encode("utf-8"),
        file_name="mapping.yaml", mime="text/yaml", disabled=not edited,
    )
    if action[2].button("Oublier le mapping"):
        st.session_state["mapping_text"] = ""
        st.rerun()

    if mapping_text and 3 not in selected_phases:
        st.info("Ajoutez la phase 3 dans la barre latérale pour exécuter les bouclages.")

    validation = document.get("validation_mapping") or []
    if validation:
        st.subheader("Validation numérique")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Clé": v["cle"], "Localisation": v["localisation"],
                        "Verdict": "✅ validée" if v["valide"] else "❌ rejetée",
                        "Motif": v["motif"],
                    }
                    for v in validation
                ]
            ),
            width="stretch", hide_index=True,
        )
        rejected = [v for v in validation if not v["valide"]]
        if rejected:
            st.error(
                f"{len(rejected)} localisation(s) rejetée(s). Les contrôles qui en "
                f"dépendent ne seront pas exécutés : une ligne mal identifiée produit "
                f"un audit faux, ce qui est pire que pas d'audit."
            )
        else:
            st.success("Toutes les localisations sont confirmées.")

    ties = [s for s in signals if s["phase"] == 3]
    if ties:
        st.subheader(f"Écarts de bouclage ({len(ties)})")
        for sig in ties:
            with st.expander(f"{sig['label']} — confiance {sig['confidence']:.2f}"):
                render_signal_detail(sig)


# ─── Export ───────────────────────────────────────────────────────────────────

with tab_export:
    st.markdown(
        "Les exports contiennent **tous** les signaux produits, quel que soit le "
        "curseur de confiance."
    )

    stem = Path(uploaded.name).stem
    restored = restore_signals(signals)
    log_obj = restore_run_log(run_log)

    cols = st.columns(3)
    cols[0].download_button(
        "Signaux (JSON)",
        json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"{stem}_signaux.json", mime="application/json", width="stretch",
    )
    cols[1].download_button(
        "Rapport (Markdown)",
        render_markdown(
            restored, log_obj, title=f"Rapport xlaudit — {uploaded.name}"
        ).encode("utf-8"),
        file_name=f"{stem}_rapport.md", mime="text/markdown", width="stretch",
    )

    xlsx_path = WORK_DIR / f"{sha[:16]}_constats.xlsx"
    write_report(restored, xlsx_path, log_obj)
    cols[2].download_button(
        "Constats (Excel)", xlsx_path.read_bytes(),
        file_name=f"{stem}_constats.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    st.subheader("Journal d'exécution")
    st.caption("Un rapport doit dire ce qu'il n'a pas regardé.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Règle": r["rule_id"], "Libellé": r["label"], "Phase": r["phase"],
                    "Statut": r["status"], "Signaux": r["signals"],
                    "Durée (s)": r["duration_s"], "Motif": r["reason"],
                }
                for r in run_log.get("rules", [])
            ]
        ),
        width="stretch", hide_index=True,
    )
