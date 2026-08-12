"""R215 - Lignes calculees sans aucun dependant."""

from __future__ import annotations

from ..core import blocks as B
from ..core import refs as R
from ..models import AuditContext, Signal
from .base import Rule, register


@register
class R215Orphans(Rule):
    """Lignes calculees que personne ne consomme.

    Toute ligne terminale n'est pas une anomalie : un modele se termine bien
    quelque part. Ce qui est un signal de premier ordre, c'est le **canal
    debranche** — un mecanisme dont le libelle annonce une fonction (« Impasse de
    tresorerie », « ADSCR », « Controle ») mais dont le resultat n'alimente rien.
    Le mecanisme parait exister et ne produit aucun effet.

    Tous les orphelins sont exposes, jamais filtres ; c'est la confiance qui
    separe le canal debranche du reliquat de presentation.

    Confiance :
      - 0.90 si le libelle contient un mot de controle (« controle », « ctrl »,
        « check », « ecart »...) : un controle debranche ne controle rien ;
      - 0.85 si le libelle porte un autre terme significatif (« impasse »,
        « ADSCR », « couverture », « covenant », « seuil »...) ;
      - 0.25 pour un libelle quelconque, 0.15 en l'absence de libelle : ce sont
        le plus souvent des lignes de restitution terminales, legitimes.
      - -0.10 si la ligne se trouve sur un onglet masque, ou une zone de travail
        non consommee est courante.
    """

    id = "R215"
    label = "Lignes orphelines"
    phase = 2
    requires_graph = True

    def run(self, ctx: AuditContext) -> list[Signal]:
        snap = ctx.snapshot
        graph = ctx.graph
        if graph is None:
            return []
        out: list[Signal] = []

        for sheet in snap.sheets.values():
            st = B.build_structure(sheet)
            if not st.projection_cols:
                continue
            for row in st.formula_rows:
                cols = [c for c in st.projection_cols if sheet.formula(row, c)]
                if not cols:
                    continue
                if graph.is_consumed(sheet.name, row):
                    continue

                label = sheet.row_label(row)
                control_word = B.label_matches(label, B.CONTROL_WORDS)
                significant_word = B.label_matches(label, B.SIGNIFICANT_WORDS)

                if control_word:
                    confidence = 0.90
                elif significant_word:
                    confidence = 0.85
                elif label:
                    confidence = 0.25
                else:
                    confidence = 0.15
                if sheet.state != "visible":
                    confidence -= 0.10

                precedents = graph.precedents_of_row(sheet.name, row, limit=20)
                out.append(
                    self.signal(
                        sheet=sheet.name,
                        refs=[f"{row}:{row}"],
                        label=label,
                        observed=sheet.formula(row, cols[0]) or "",
                        expected=None,
                        evidence={
                            "colonnes_calculees": len(cols),
                            "premiere_colonne": R.index_to_col(cols[0]),
                            "derniere_colonne": R.index_to_col(cols[-1]),
                            "mot_de_controle": control_word,
                            "mot_significatif": significant_word,
                            "canal_debranche": bool(control_word or significant_word),
                            "onglet_masque": sheet.state != "visible",
                            "alimentee_par": precedents,
                            "valeurs_en_cache": {
                                f"{R.index_to_col(c)}{row}": sheet.value(row, c)
                                for c in cols[:6]
                            },
                        },
                        consumers=[],
                        confidence=confidence,
                        note=(
                            f"Ligne calculee sur {len(cols)} colonne(s) et consommee "
                            f"par aucune formule du classeur"
                            + (
                                f" ; le libelle porte « {control_word or significant_word} », "
                                f"ce qui designe un mecanisme cense produire un effet."
                                if (control_word or significant_word)
                                else "."
                            )
                        ),
                    )
                )
        return out
