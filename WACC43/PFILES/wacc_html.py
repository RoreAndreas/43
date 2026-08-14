"""
Assemblage de la page : injection du jeu de données dans le gabarit.

Toute la présentation vit dans `templates/wacc_value_tab.html`, et les formules
y sont appliquées en JavaScript. Ce module se contente de coller le jeu de
données produit par `wacc_core.build_dataset()` entre les marqueurs
DATA_START / DATA_END.
"""

import json
import re
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "wacc_value_tab.html"

_DATA_BLOCK = re.compile(r"// DATA_START.*?// DATA_END", re.DOTALL)


def render_page(dataset: dict, compact: bool = True) -> str:
    """Page HTML autonome : gabarit + jeu de données embarqué."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = json.dumps(
        dataset,
        ensure_ascii=False,
        separators=(",", ":") if compact else (", ", ": "),
        indent=None if compact else 2,
    )
    # Un "</script>" présent dans une chaîne fermerait la balise du gabarit.
    payload = payload.replace("</", "<\\/")
    return _DATA_BLOCK.sub(lambda _: "const DATA = " + payload + ";", template, count=1)
