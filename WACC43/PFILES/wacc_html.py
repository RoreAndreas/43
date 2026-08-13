"""
Sortie HTML du calcul de CMPC, au format de la maquette `wacc_value_tab.html`.

Le fichier `wacc_value_tab.html` sert de gabarit : on y réinjecte le tableau
`components` (entre les marqueurs COMPONENTS_DATA_START / COMPONENTS_DATA_END)
avec les valeurs réellement calculées par l'application.
"""

import html
import json
import re
from pathlib import Path

TEMPLATE_PATH = Path(__file__).with_name("wacc_value_tab.html")

_DATA_BLOCK = re.compile(
    r"// COMPONENTS_DATA_START.*?// COMPONENTS_DATA_END",
    re.DOTALL,
)
_FISCAL_YEAR = re.compile(r'<div class="fiscal-year">.*?</div>', re.DOTALL)
_TITLE = re.compile(r"<title>.*?</title>", re.DOTALL)
_FOOTER = re.compile(r'<footer class="credit">.*?</footer>', re.DOTALL)

# Styles appliqués quand la page est affichée à l'intérieur de Streamlit :
# l'en-tête et les onglets sont déjà fournis par l'application.
_EMBED_STYLE = """
<style>
  body { background: transparent; }
  .page { max-width: none; padding: 0 0 4px; }
  .top-header, footer.credit { display: none; }
  .detail-panel { height: 660px; }
</style>
"""


def fr_pct(value: float, decimals: int = 2) -> str:
    """0.1316 -> '13,16 %'"""
    return f"{value * 100:.{decimals}f}".replace(".", ",") + " %"


def fr_num(value: float, decimals: int = 2) -> str:
    """1.4389 -> '1,439' (avec decimals=3)"""
    return f"{value:.{decimals}f}".replace(".", ",")


def fr_pts(value: float, decimals: int = 2) -> str:
    """0.0173 -> '1,73 pt' (points de pourcentage)"""
    unit = "pt" if abs(value * 100) < 2 else "pts"
    return f"{value * 100:.{decimals}f}".replace(".", ",") + f" {unit}"


def build_components(v: dict) -> list:
    """Construit les composantes affichées (cartes + panneau de détail)."""
    year = v["valuation_year"]
    maturity = v.get("risk_free_maturity", "30Y")
    a = v["taux_sans_risque_local"]
    b = v["beta_reendette"]
    c = v["c"]
    d = v["d"]
    e = v["e"]
    t = v["tax_rate"]
    gearing = v["gearing_sectoriel"]
    re_fp = v["cout_fonds_propres"]
    spread = v["adjusted_spread"]
    rd_pre = v["cout_dette_avant_impot"]
    rd_post = v["cout_dette"]
    ev = v["quote_part_equity"]
    dv = v["quote_part_debt"]
    wacc = v["wacc"]
    wacc_local = v["wacc_local"]
    country = v["country"]
    industry = v["industry"]

    contrib_fp = re_fp * ev
    contrib_dette = rd_post * dv
    economie_impot = rd_pre * t

    spread_label = "Spread de financement (ajusté)" if v.get("is_adjusted") else "Spread de financement"

    return [
        {
            "id": "cout_fonds_propres",
            "title": "Coût des fonds propres",
            "symbol": "Re",
            "value": fr_pct(re_fp),
            "rows": [
                {"label": f"Taux US Bond {maturity} ({year})", "value": fr_pct(v["avg_30y_rate"] / 100)},
                {"label": "Prime de risque pays", "value": fr_pct(v["country_risk_premium"])},
                {"label": "Taux sans risque local (a)", "value": fr_pct(a)},
                {"label": "Beta désendetté", "value": fr_num(v["beta_desendette"], 3)},
                {"label": "Gearing sectoriel", "value": fr_num(gearing, 2)},
                {"label": "Beta réendetté (b)", "value": fr_num(b, 3)},
                {"label": "Prime de risque marché (c)", "value": fr_pct(c)},
                {"label": "Prime de taille (d)", "value": fr_pct(d)},
                {"label": "Prime spécifique (e)", "value": fr_pct(e)},
            ],
            "methodology": (
                "MEDAF. Taux sans risque construit sur l'obligation US "
                f"{maturity}, majoré de la prime de risque pays ; bêta sectoriel "
                "désendetté puis ré-endetté au gearing sectoriel."
            ),
            "source": (
                f"US Treasury {maturity} (moyenne {year}) ; prime pays, prime de risque "
                f"marché et bêta sectoriel Damodaran ({industry}, {country})."
            ),
            "hypothesis": (
                "Primes de taille et spécifique maintenues sur tout l'horizon ; "
                "gearing sectoriel considéré comme cible."
            ),
            "formula": [
                "Re = a + b × c + d + e",
                f"= {fr_pct(a)} + {fr_num(b, 3)} × {fr_pct(c)} + {fr_pct(d)} + {fr_pct(e)} = {fr_pct(re_fp)}",
            ],
        },
        {
            "id": "cout_dette",
            "title": "Coût de la dette",
            "symbol": "Rd",
            "value": fr_pct(rd_pre),
            "rows": [
                {"label": "Taux sans risque local (a)", "value": fr_pct(a)},
                {"label": spread_label, "value": fr_pct(spread)},
                {"label": "Coût de la dette avant impôt", "value": fr_pct(rd_pre)},
                {"label": "Coût de la dette après impôt", "value": fr_pct(rd_post)},
            ],
            "methodology": (
                "Coût marginal de la dette : taux sans risque local majoré du spread "
                "de financement sectoriel, puis net d'économie d'impôt."
            ),
            "source": (
                f"Spread de financement sectoriel Damodaran ({industry})"
                + (" ; spread ajusté via la table de notation." if v.get("is_adjusted") else ".")
            ),
            "hypothesis": (
                "Refinancement aux conditions actuelles ; charges financières "
                "intégralement déductibles."
            ),
            "formula": [
                f"Rd = a + spread = {fr_pct(a)} + {fr_pct(spread)} = {fr_pct(rd_pre)}",
                f"Rd après impôt = {fr_pct(rd_pre)} × (1 − {fr_pct(t)}) = {fr_pct(rd_post)}",
            ],
        },
        {
            "id": "poids_fonds_propres",
            "title": "Poids des fonds propres",
            "symbol": "E/V",
            "value": fr_pct(ev),
            "rows": [
                {"label": "Gearing sectoriel (D/E)", "value": fr_num(gearing, 2)},
                {"label": "Quote-part fonds propres", "value": fr_pct(ev)},
                {"label": "Quote-part dette", "value": fr_pct(dv)},
            ],
            "methodology": (
                "Structure financière cible en valeur de marché, déduite du gearing "
                "sectoriel plutôt que du levier comptable spot."
            ),
            "source": "Gearing médian de l'échantillon sectoriel retenu pour le désendettement du bêta.",
            "hypothesis": "Structure stable sur l'horizon d'actualisation, sans opération de haut de bilan.",
            "formula": [
                f"E/V = 1 / (1 + D/E) = 1 / {fr_num(1 + gearing, 2)} = {fr_pct(ev)}",
            ],
        },
        {
            "id": "poids_dette",
            "title": "Poids de la dette",
            "symbol": "D/V",
            "value": fr_pct(dv),
            "rows": [
                {"label": "Gearing sectoriel (D/E)", "value": fr_num(gearing, 2)},
                {"label": "Quote-part dette", "value": fr_pct(dv)},
                {"label": "Quote-part fonds propres", "value": fr_pct(ev)},
            ],
            "methodology": (
                "Complément de la quote-part de fonds propres, sur la même structure "
                "cible ; dette financière brute, trésorerie non déduite."
            ),
            "source": "Gearing médian de l'échantillon sectoriel retenu pour le désendettement du bêta.",
            "hypothesis": "Obligations locatives assimilées à de la dette financière.",
            "formula": [
                f"D/V = (D/E) / (1 + D/E) = {fr_num(gearing, 2)} / {fr_num(1 + gearing, 2)} = {fr_pct(dv)}",
            ],
        },
        {
            "id": "taux_imposition",
            "title": "Taux d'imposition",
            "symbol": "t",
            "value": fr_pct(t),
            "rows": [
                {"label": "Corporate tax rate", "value": fr_pct(t)},
                {"label": "Coût de la dette avant impôt", "value": fr_pct(rd_pre)},
                {"label": "Économie d'impôt", "value": fr_pts(economie_impot)},
            ],
            "methodology": (
                "Taux d'impôt sur les sociétés normatif, également utilisé pour le "
                "ré-endettement du bêta."
            ),
            "source": f"Taux d'IS de droit commun Damodaran ({country}).",
            "hypothesis": "Aucun déficit reportable activé ; pas de plafonnement de la déductibilité.",
            "formula": [
                f"Économie d'impôt = Rd × t = {fr_pct(rd_pre)} × {fr_pct(t)} = {fr_pts(economie_impot)}",
                f"Beta réendetté = {fr_num(v['beta_desendette'], 3)} × (1 + {fr_num(gearing, 2)} × (1 − {fr_pct(t)})) = {fr_num(b, 3)}",
            ],
        },
        {
            "id": "wacc",
            "title": "Coût moyen pondéré du capital",
            "symbol": "WACC",
            "value": fr_pct(wacc),
            "highlight": True,
            "rows": [
                {"label": f"Fonds propres {fr_pct(re_fp)} × {fr_pct(ev)}", "value": fr_pts(contrib_fp)},
                {"label": f"Dette {fr_pct(rd_post)} × {fr_pct(dv)}", "value": fr_pts(contrib_dette)},
                {"label": "WACC", "value": fr_pct(wacc)},
            ],
            "methodology": (
                "Moyenne des deux coûts pondérée par la structure cible, la dette "
                "étant retenue après économie d'impôt."
            ),
            "source": "Structure financière cible et coût de la dette ajusté du taux d'imposition.",
            "hypothesis": "Structure de financement cible maintenue sur tout l'horizon d'actualisation.",
            "retained": (
                f"{fr_pct(wacc)} dans la monnaie du taux sans risque, "
                f"{fr_pct(wacc_local)} en monnaie locale après différentiel d'inflation."
            ),
            "composition": [
                {"label": "Fonds propres", "value": fr_pct(contrib_fp / wacc, 1) if wacc else "—"},
                {"label": "Dette", "value": fr_pct(contrib_dette / wacc, 1) if wacc else "—"},
            ],
            "formula": [
                "WACC = E/V × Re + D/V × Rd après impôt",
                f"= {fr_pct(ev)} × {fr_pct(re_fp)} + {fr_pct(dv)} × {fr_pct(rd_post)} = {fr_pct(wacc)}",
            ],
        },
        {
            "id": "wacc_local",
            "title": "CMPC en monnaie locale",
            "symbol": "CMPC loc.",
            "value": fr_pct(wacc_local),
            "highlight": True,
            "tone": "cyan",
            "rows": [
                {"label": "CMPC, monnaie du taux sans risque", "value": fr_pct(wacc)},
                {"label": "Inflation, monnaie du taux sans risque", "value": fr_pct(v["inflation_mature"])},
                {"label": "Inflation, monnaie locale", "value": fr_pct(v["inflation_locale"])},
                {"label": "CMPC en monnaie locale", "value": fr_pct(wacc_local)},
            ],
            "methodology": (
                "Conversion du CMPC par le différentiel d'inflation entre la monnaie "
                "du taux sans risque et la monnaie locale."
            ),
            "source": "Anticipations d'inflation saisies dans l'onglet Paramètres.",
            "hypothesis": "Parité des pouvoirs d'achat relative vérifiée sur l'horizon d'actualisation.",
            "formula": [
                "CMPC local = (1 + CMPC) × (1 + i locale) / (1 + i référence) − 1",
                f"= (1 + {fr_pct(wacc)}) × (1 + {fr_pct(v['inflation_locale'])}) / "
                f"(1 + {fr_pct(v['inflation_mature'])}) − 1 = {fr_pct(wacc_local)}",
            ],
        },
    ]


def render_wacc_html(v: dict, standalone: bool = True) -> str:
    """
    Retourne la page HTML du CMPC au format de la maquette.

    `standalone=True` : page complète (en-tête, onglets, pied de page) pour
    l'export. `standalone=False` : contenu seul, à intégrer dans Streamlit.
    """
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    payload = json.dumps(build_components(v), ensure_ascii=False, indent=2)
    # Un "</script>" présent dans une chaîne fermerait la balise du gabarit.
    payload = payload.replace("</", "<\\/")

    page = _DATA_BLOCK.sub(
        lambda _: "const components = " + payload + ";",
        template,
        count=1,
    )

    country = html.escape(str(v["country"]))
    industry = html.escape(str(v["industry"]))
    year = html.escape(str(v["valuation_year"]))

    page = _TITLE.sub(
        lambda _: f"<title>wacc43 — CMPC {industry} · {country} · {year}</title>",
        page,
        count=1,
    )
    page = _FISCAL_YEAR.sub(
        lambda _: f'<div class="fiscal-year">{industry} · {country} · Exercice {year}</div>',
        page,
        count=1,
    )
    page = _FOOTER.sub(
        lambda _: f'<footer class="credit">wacc43 — Méthode indirecte · Exercice {year}</footer>',
        page,
        count=1,
    )

    if not standalone:
        page = page.replace("</head>", _EMBED_STYLE + "</head>", 1)

    return page
