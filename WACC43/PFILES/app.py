import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import subprocess
import sys
import difflib
from datetime import datetime
from get_us_bond_rate import calculate_average_rate
from export_wacc import generate_wacc_workbook

# Vérifier et installer openpyxl si nécessaire
try:
    import openpyxl
except ImportError:
    st.warning("Installation de openpyxl en cours...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    import openpyxl

# Vérifier et installer xlrd si nécessaire
try:
    import xlrd
except ImportError:
    st.warning("Installation de xlrd en cours...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "xlrd"])
    import xlrd

@st.cache_data
def load_betas_data():
    """
    Télécharge et charge les données de betas de Damodaran
    """
    url = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betaemerg.xls"

    try:
        # Télécharger le fichier
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Lire le fichier Excel
        excel_file = BytesIO(response.content)
        df = pd.read_excel(excel_file, sheet_name="Industry Averages", header=None)

        # Extraire la plage A10:H104 (index 9 à 103, colonnes 0 à 7)
        # Les en-têtes sont à la ligne 10 (index 9)
        headers = df.iloc[9, 0:8].tolist()
        data = df.iloc[9:104, 0:8]
        data.columns = headers

        # Réinitialiser l'index
        data = data.reset_index(drop=True)

        return data

    except Exception as e:
        st.error(f"Erreur lors du téléchargement/lecture du fichier betas: {e}")
        return None


@st.cache_data
def load_tax_rates_data():
    """
    Télécharge et charge les données de tax rates de Damodaran
    """
    url = "https://www.stern.nyu.edu/~adamodar/pc/datasets/countrytaxrates.xls"

    try:
        # Télécharger le fichier
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Lire le fichier Excel
        excel_file = BytesIO(response.content)
        df = pd.read_excel(excel_file, sheet_name=0, header=None)

        # Extraire la plage A6:C257 (index 5 à 256, colonnes 0 à 2)
        # Les en-têtes sont à la ligne 6 (index 5)
        headers = df.iloc[5, 0:3].tolist()
        data = df.iloc[5:257, 0:3]
        data.columns = headers

        # Réinitialiser l'index
        data = data.reset_index(drop=True)

        # Supprimer les lignes vides
        data = data.dropna(how='all')

        return data

    except Exception as e:
        st.error(f"Erreur lors du téléchargement/lecture du fichier tax rates: {e}")
        return None


@st.cache_data
def load_erps_data():
    """
    Télécharge et charge les données de ERPs by country de Damodaran
    """
    url = "https://www.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"

    try:
        # Télécharger le fichier
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Lire le fichier Excel
        excel_file = BytesIO(response.content)
        df = pd.read_excel(excel_file, sheet_name="ERPs by country", header=None)

        # Prime de risque marché actions pour un marché mature (cellule E3)
        # "Enter the current risk premium for a mature equity market"
        mature_market_premium = float(df.iloc[2, 4])

        # Extraire la plage A8:F165 (index 7 à 164, colonnes 0 à 5)
        # Les en-têtes sont à la ligne 8 (index 7)
        headers = df.iloc[7, 0:6].tolist()
        data = df.iloc[7:165, 0:6]
        data.columns = headers

        # Réinitialiser l'index
        data = data.reset_index(drop=True)

        # Supprimer les lignes vides
        data = data.dropna(how='all')

        return data, mature_market_premium

    except Exception as e:
        st.error(f"Erreur lors du téléchargement/lecture du fichier ERPs: {e}")
        return None, None


@st.cache_data
def load_financing_spread_data():
    """
    Télécharge et charge les données de spread de financement par industrie de Damodaran
    """
    url = "https://www.stern.nyu.edu/~adamodar/pc/datasets/wacc.xls"

    try:
        # Télécharger le fichier
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Lire le fichier Excel
        excel_file = BytesIO(response.content)
        df = pd.read_excel(excel_file, sheet_name="Industry Averages", header=None)

        # Extraire la plage A19:L113 (index 18 à 112, colonnes 0 à 11)
        # Les en-têtes sont à la ligne 19 (index 18)
        headers = df.iloc[18, 0:12].tolist()
        # Sauter la ligne avec l'en-tête dupliquée et prendre les données à partir de la ligne 20 (index 19)
        data = df.iloc[19:113, 0:12]
        data.columns = headers

        # Réinitialiser l'index
        data = data.reset_index(drop=True)

        # Supprimer les lignes vides
        data = data.dropna(how='all')

        return data

    except Exception as e:
        st.error(f"Erreur lors du téléchargement/lecture du fichier WACC (Financing Spread): {e}")
        return None


@st.cache_data
def load_spread_adjustment_table():
    """
    Télécharge et charge la table d'ajustement du spread (H9:I16 et D11) de Damodaran
    """
    url = "https://www.stern.nyu.edu/~adamodar/pc/datasets/wacc.xls"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        excel_file = BytesIO(response.content)
        df = pd.read_excel(excel_file, sheet_name="Industry Averages", header=None)

        # Extraire H9:I16 (index 8:16, colonnes 7:9)
        thresholds = df.iloc[9:16, 7].tolist()  # Colonne H (index 7)
        spreads = df.iloc[9:16, 8].tolist()     # Colonne I (index 8)
        
        # Extraire D11 (index 10, colonne 3)
        adjustment = float(df.iloc[10, 3])

        return {
            'thresholds': thresholds,
            'spreads': spreads,
            'adjustment': adjustment
        }

    except Exception as e:
        st.error(f"Erreur lors du chargement de la table d'ajustement du spread: {e}")
        return None


def calcul_beta_reendeté(beta_desendetté: float, gearing_sectoriel: float, tax_rate: float) -> float:
    """
    Calcule le beta réendetté selon la formule :
    beta réendetté = beta désendetté * (1 + gearing sectoriel * (1 - tax rate))
    """
    return beta_desendetté * (1 + gearing_sectoriel * (1 - tax_rate))


def calcul_cout_fonds_propres(
    taux_sans_risque_local: float,
    beta_reendeté: float,
    prime_risque_marche: float,
    prime_taille: float,
    prime_specifique: float
) -> float:
    """
    Calcule le coût des fonds propres selon la formule :
    coût des fonds propres = a + b * c + d + e

    a : taux sans risque local
    b : beta réendetté
    c : prime de risque marché actions
    d : prime de taille
    e : prime spécifique
    """
    return taux_sans_risque_local + beta_reendeté * prime_risque_marche + prime_taille + prime_specifique


def get_adjusted_spread(cost_of_debt: float, adjustment_table: dict) -> tuple:
    """
    Retourne le spread ajusté basé sur la comparaison avec les seuils.
    Si cost_of_debt <= seuil, retourne spread + adjustment
    Sinon, retourne le spread original
    
    Retourne: (spread_final, is_adjusted)
    """
    if adjustment_table is None:
        return cost_of_debt, False
    
    thresholds = adjustment_table['thresholds']
    spreads = adjustment_table['spreads']
    adjustment = adjustment_table['adjustment']
    
    # Parcourir les seuils pour trouver le bon spread
    for threshold, spread in zip(thresholds, spreads):
        if pd.notna(threshold) and pd.notna(spread):
            if cost_of_debt <= float(threshold):
                adjusted = float(spread) + adjustment
                return adjusted, True
    
    # Si pas de correspondance trouvée, retourner le spread original
    return cost_of_debt, False


def calcul_cout_dette(adjusted_spread: float, taux_sans_risque_local: float, tax_rate: float) -> float:
    """
    Calcule le coût de la dette selon la formule :
    Coût de la Dette = (Spread de Financement + Taux sans risque local) × (1 - Taux d'IS)
    
    adjusted_spread : spread de financement (ajusté ou non)
    taux_sans_risque_local : taux sans risque (a)
    tax_rate : taux d'imposition des sociétés
    """
    return (adjusted_spread + taux_sans_risque_local) * (1 - tax_rate)


def calcul_wacc(cout_fonds_propres: float, cout_dette: float, quote_part_equity: float, quote_part_debt: float) -> float:
    """
    Calcule le WACC selon la formule :
    WACC = Coût Fonds Propres × Quote-part Equity + Coût Dette × Quote-part Dette
    
    cout_fonds_propres : coût des fonds propres
    cout_dette : coût de la dette
    quote_part_equity : 1/(1+gearing)
    quote_part_debt : 1 - quote_part_equity
    """
    return cout_fonds_propres * quote_part_equity + cout_dette * quote_part_debt


def calcul_wacc_monnaie_locale(wacc: float, inflation_locale: float, inflation_mature: float) -> float:
    """
    Convertit le CMPC de la monnaie du taux sans risque vers la monnaie locale
    via le différentiel d'inflation :
    CMPC local = (1 + CMPC) * (1 + inflation locale) / (1 + inflation mature) - 1
    """
    return (1 + wacc) * (1 + inflation_locale) / (1 + inflation_mature) - 1


def render_comment_trigger(key: str, label: str) -> None:
    """Petit bouton qui ouvre, dans la zone Commentaire, la bulle liée à ce cadre de valeur."""
    if st.button("💬", key=f"btn_comment_{key}", help=f"Commenter : {label}"):
        st.session_state["active_comment_key"] = key
        st.session_state["active_comment_label"] = label
        st.rerun()


def render_value_card(title: str, value: str, accent: str, helper: str = "", comment_key: str | None = None, dark: bool = False, badge: str | None = None) -> None:
    """Affiche une carte de valeur dans le style d’un dashboard de valorisation premium."""
    bloc_valeur, bloc_bouton = st.columns([10, 1])
    card_bg = "#111827" if dark else "#ffffff"
    label_color = "rgba(148,163,184,0.95)" if dark else "#64748b"
    helper_color = "rgba(255,255,255,0.78)" if dark else "#475569"
    border = "rgba(148,163,184,0.28)" if dark else "rgba(15,23,42,0.08)"
    badge_html = f'<span style="display:inline-block;padding:4px 8px;border-radius:999px;background:rgba(255,255,255,0.08);color:{accent};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">{badge}</span>' if badge else ''
    card_html = f"""
    <div style="background:{card_bg}; border:1px solid {border}; border-radius:18px; padding:16px 18px; margin-bottom:14px; box-shadow:0 8px 22px rgba(15, 23, 42, 0.06);">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:12px;">
            <div style="font-size:11px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:{label_color};">{title}</div>
            {badge_html}
        </div>
        <div style="font-size:1.55rem; line-height:1.2; font-weight:800; letter-spacing:-0.02em; color:{accent};">{value}</div>
        {f'<div style="margin-top:8px; font-size:0.82rem; line-height:1.45; color:{helper_color};">{helper}</div>' if helper else ''}
    </div>
    """
    with bloc_valeur:
        st.markdown(card_html, unsafe_allow_html=True)
    if comment_key:
        with bloc_bouton:
            render_comment_trigger(comment_key, title)


# Configuration de la page
st.set_page_config(
    page_title="Calcul WACC",
    page_icon="🔵",
    layout="centered"
)

# Logo texte, centré au-dessus du titre : sans carré ni fond, texte noir.
st.markdown(
    "<div style='text-align:center;margin:0 auto 16px;'>"
    "<span style=\"color:#000;font-family:'Arial Black','Helvetica Neue',Arial,sans-serif;"
    "font-weight:900;font-size:32px;line-height:1.2;\">Making it the 43. Type of way</span>"
    "</div>",
    unsafe_allow_html=True,
)

st.title("Calcul du CMPC - Méthode indirecte")
st.markdown("**Formule Coût Fonds Propres:** Coût = a + b × c + d + e")
st.divider()

# Bulle de commentaire : rectangle avec une flèche pointant vers le cadre de valeur cliqué
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #f6f8fc 0%, #eef3fb 100%);
    }
    .block-container {
        max-width: 1450px;
        padding-top: 1.75rem;
        padding-bottom: 2rem;
    }
    [data-testid="stTab"] {
        font-weight: 700;
        letter-spacing: 0.02em;
        color: #475569;
        padding: 0.7rem 1rem;
        border-radius: 12px 12px 0 0;
    }
    [data-testid="stTabList"] {
        gap: 0.6rem;
        background: rgba(255,255,255,0.7);
        border-radius: 16px;
        padding: 0.35rem 0.5rem;
        border: 1px solid rgba(148, 163, 184, 0.2);
    }
    [data-testid="stTabList"] button[aria-selected="true"] {
        background: linear-gradient(135deg, #eaf2ff 0%, #dfefff 100%);
        color: #103870;
        border: 1px solid rgba(96,165,250,0.25);
        box-shadow: 0 8px 18px rgba(59,130,246,0.1);
    }
    .design-header {
        background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(30,41,59,0.96));
        border-radius: 22px;
        padding: 1.4rem 1.5rem 1.2rem 1.5rem;
        margin-bottom: 1.2rem;
        border: 1px solid rgba(148,163,184,0.18);
        box-shadow: 0 18px 40px rgba(15,23,42,0.08);
    }
    .design-header .eyebrow {
        display: inline-block;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #7dd3fc;
        margin-bottom: 0.55rem;
    }
    .design-header h2 {
        margin: 0;
        color: white;
        font-size: clamp(1.6rem, 2.2vw, 2.4rem);
        line-height: 1.1;
        letter-spacing: -0.04em;
    }
    .design-header .subtitle {
        margin-top: 0.4rem;
        color: rgba(255,255,255,0.72);
        font-size: 0.95rem;
    }
    .panel {
        background: rgba(255,255,255,0.85);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 25px rgba(15,23,42,0.04);
        height: 100%;
    }
    .panel-title {
        font-size: 0.8rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #475569;
        margin-bottom: 0.8rem;
    }
    .kpi-highlight {
        background: linear-gradient(135deg, #eaf2ff 0%, #dfeeff 100%);
        border: 1px solid rgba(59,130,246,0.18);
        border-radius: 18px;
        padding: 1.1rem 1.15rem;
        box-shadow: inset 0 1px rgba(255,255,255,0.8);
    }
    .kpi-highlight .label {
        display: block;
        font-size: 0.73rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #3b82f6;
        margin-bottom: 0.5rem;
        font-weight: 700;
    }
    .kpi-highlight .value {
        font-size: clamp(1.7rem, 2.2vw, 2.5rem);
        font-weight: 900;
        letter-spacing: -0.04em;
        color: #0f172a;
    }
    .st-key-comment_bubble {
        position: relative;
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid rgba(148,163,184,0.28);
        border-radius: 18px;
        padding: 14px 16px;
        margin: 6px 0 10px 18px;
        box-shadow: 0 10px 25px rgba(15,23,42,0.05);
    }
    .st-key-comment_bubble::before {
        content: "";
        position: absolute;
        top: 22px;
        left: -18px;
        width: 0;
        height: 0;
        border-top: 11px solid transparent;
        border-bottom: 11px solid transparent;
        border-right: 18px solid rgba(148,163,184,0.28);
    }
    .st-key-comment_bubble::after {
        content: "";
        position: absolute;
        top: 24px;
        left: -14px;
        width: 0;
        height: 0;
        border-top: 9px solid transparent;
        border-bottom: 9px solid transparent;
        border-right: 15px solid #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "active_comment_key" not in st.session_state:
    st.session_state["active_comment_key"] = None

tab_parametres, tab_valeurs = st.tabs(["Paramètres", "Valeurs"])

# Charger les données (indépendantes de l'année et de la maturité choisies)
with st.spinner("Chargement des données Damodaran..."):
    betas_data = load_betas_data()
    tax_rates_data = load_tax_rates_data()
    erps_data, mature_market_premium = load_erps_data()
    financing_spread_data = load_financing_spread_data()
    spread_adjustment_table = load_spread_adjustment_table()

if betas_data is not None and tax_rates_data is not None and erps_data is not None and financing_spread_data is not None:
    with tab_parametres:
        # Sélection de l'année de valorisation
        current_year = datetime.now().year
        col_year, col_maturity = st.columns(2)
        with col_year:
            valuation_year = st.selectbox(
                "Sélectionner l'année de valorisation",
                options=range(current_year, current_year - 10, -1), # 10 dernières années
                index=0
            )
        with col_maturity:
            risk_free_maturity = st.selectbox(
                "Maturité du taux sans risque",
                options=["30Y", "10Y"],
                index=0,
                help="Taux des bons du Trésor US utilisé comme taux sans risque"
            )
        risk_free_maturity_code = "30" if risk_free_maturity == "30Y" else "10"
        st.divider()

        st.subheader("Sélection Pays et Industrie")

        # Sélection du pays
        countries = sorted(erps_data[erps_data.columns[0]].dropna().unique().tolist())
        selected_country = st.selectbox(
            "Sélectionner un pays",
            countries,
            key="country_select"
        )

        # Sélection de l'industrie
        industries = sorted(betas_data[betas_data.columns[0]].dropna().unique().tolist())
        selected_industry = st.selectbox(
            "Sélectionner une industrie",
            industries,
            key="industry_select"
        )

        st.subheader("Paramètres manuels")

        d = st.number_input(
            "Prime de taille (d)",
            value=0.01,
            step=0.001,
            format="%.2f",
            help="Exemple: 0.01 pour 1%"
        )

        e = st.number_input(
            "Prime spécifique (e)",
            value=0.005,
            step=0.001,
            format="%.2f",
            help="Prime de risque spécifique"
        )

        inflation_mature = st.number_input(
            "Inflation, monnaie du taux sans risque",
            value=0.025,
            step=0.001,
            format="%.3f",
            help="Ex: Cleveland Fed - Ten year expected inflation"
        )

        inflation_locale = st.number_input(
            "Inflation, monnaie locale",
            value=0.03,
            step=0.001,
            format="%.3f",
            help="Ex: critère de convergence UEMOA (3% plafond)"
        )

        # Espace réservé pour le message de pays correspondant
        country_match_placeholder = st.empty()
        
        # Espace réservé pour le message de spread de financement correspondant
        financing_spread_placeholder = st.empty()

    avg_30y_rate = calculate_average_rate(valuation_year, risk_free_maturity_code)

    with tab_valeurs:
        col_values, col_comments = st.columns([3, 2])

        with col_values:
            # Extraire les données pour le pays sélectionné
            country_data = erps_data[erps_data[erps_data.columns[0]].str.lower() == selected_country.lower()]
            c = mature_market_premium if mature_market_premium is not None else 0.06
            if len(country_data) > 0:
                country_risk_premium = float(country_data["Country Risk Premium"].values[0])
            else:
                country_risk_premium = 0.01
                st.warning("Primes de risque non trouvées, valeurs par défaut utilisées")

            industry_data = betas_data[betas_data[betas_data.columns[0]].str.lower() == selected_industry.lower()]
            if len(industry_data) > 0:
                beta_desendetté = float(industry_data["Unlevered beta"].values[0])
                gearing_sectoriel = float(industry_data["D/E Ratio"].values[0])
            else:
                beta_desendetté = 1.0
                gearing_sectoriel = 0.5
                st.warning("Données beta non trouvées, valeurs par défaut utilisées")

            financing_spread_industry = financing_spread_data[financing_spread_data[financing_spread_data.columns[0]].str.lower() == selected_industry.lower()]
            if len(financing_spread_industry) > 0:
                cost_of_debt = float(financing_spread_industry.iloc[0, 5])
                proportion_equity = float(financing_spread_industry.iloc[0, 4])
                financing_spread_placeholder.empty()
            else:
                financing_industries_list = financing_spread_data[financing_spread_data.columns[0]].dropna().str.lower().tolist()
                matches = difflib.get_close_matches(selected_industry.lower(), financing_industries_list, n=1, cutoff=0.9)
                if matches:
                    matched_industry = matches[0]
                    financing_spread_industry = financing_spread_data[financing_spread_data[financing_spread_data.columns[0]].str.lower() == matched_industry]
                    cost_of_debt = float(financing_spread_industry.iloc[0, 5])
                    proportion_equity = float(financing_spread_industry.iloc[0, 4])
                    financing_spread_placeholder.info(f"Financing spread industry match -> {matched_industry}")
                else:
                    cost_of_debt = 0.05
                    proportion_equity = 0.6
                    st.warning("Données de spread de financement non trouvées, valeurs par défaut utilisées")
                    financing_spread_placeholder.empty()

            tax_country_data = tax_rates_data[tax_rates_data[tax_rates_data.columns[0]].str.strip().str.lower() == selected_country.lower().strip()]
            if len(tax_country_data) > 0:
                tax_rate = float(tax_country_data[tax_rates_data.columns[1]].values[0])
                country_match_placeholder.empty()
            else:
                tax_countries_list = tax_rates_data[tax_rates_data.columns[0]].dropna().str.strip().str.lower().tolist()
                matches = difflib.get_close_matches(selected_country.lower().strip(), tax_countries_list, n=1, cutoff=0.9)
                if matches:
                    matched_country = matches[0]
                    tax_country_data = tax_rates_data[tax_rates_data[tax_rates_data.columns[0]].str.strip().str.lower() == matched_country]
                    tax_rate = float(tax_country_data[tax_rates_data.columns[1]].values[0])
                    country_match_placeholder.info(f"Corp. Tax files match -> {matched_country}")
                else:
                    tax_rate = 0.25
                    st.warning("Corporate tax rate non trouvé, valeur par défaut utilisée")
                    country_match_placeholder.empty()

            b = calcul_beta_reendeté(beta_desendetté, gearing_sectoriel, tax_rate)

            if avg_30y_rate is not None:
                a = (avg_30y_rate / 100) + country_risk_premium
            else:
                a = 0.03
                st.error(f"Impossible de calculer le taux US {risk_free_maturity} pour {valuation_year}. Utilisation d'une valeur par défaut pour 'a'.")

            cout_fonds_propres = calcul_cout_fonds_propres(a, b, c, d, e)
            adjusted_spread, is_adjusted = get_adjusted_spread(cost_of_debt, spread_adjustment_table)
            quote_part_equity = 1 / (1 + gearing_sectoriel)
            quote_part_debt = 1 - quote_part_equity
            cout_dette = calcul_cout_dette(adjusted_spread, a, tax_rate)
            wacc = calcul_wacc(cout_fonds_propres, cout_dette, quote_part_equity, quote_part_debt)
            wacc_local = calcul_wacc_monnaie_locale(wacc, inflation_locale, inflation_mature)

            st.markdown(
                """
                <div class="design-header">
                    <div class="eyebrow">Valuation</div>
                    <h2>Onglet Valeur WACC</h2>
                    <div class="subtitle">Pays: <strong>""" + selected_country + """</strong> • Industrie: <strong>""" + selected_industry + """</strong> • Année: <strong>""" + str(valuation_year) + """</strong></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            summary_cols = st.columns(4)
            with summary_cols[0]:
                render_value_card(
                    "Taux sans risque",
                    f"{a:.2%}",
                    "#1d4ed8",
                    helper=f"US {risk_free_maturity} {valuation_year}: {avg_30y_rate:.2f}% + pays {country_risk_premium:.2%}",
                    comment_key="taux_sans_risque",
                    dark=True,
                    badge="a",
                )
            with summary_cols[1]:
                render_value_card(
                    "Beta réendetté",
                    f"{b:.3f}",
                    "#2563eb",
                    helper=f"Beta désendetté {beta_desendetté:.3f} • gearing {gearing_sectoriel:.2f}",
                    comment_key="beta",
                    badge="b",
                )
            with summary_cols[2]:
                render_value_card(
                    "Prime de risque",
                    f"{c:.2%}",
                    "#f59e0b",
                    helper=f"Taille {d:.2%} • spécifique {e:.2%}",
                    comment_key="primes",
                    badge="c+d+e",
                )
            with summary_cols[3]:
                render_value_card(
                    "Spread financement",
                    f"{adjusted_spread:.2%}",
                    "#ef4444",
                    helper=f"Ajusté: {'Oui' if is_adjusted else 'Non'} • dette {cost_of_debt:.2%}",
                    comment_key="spread",
                    dark=True,
                    badge="spread",
                )

            st.markdown('<div class="panel-title" style="margin-top:1.2rem; margin-bottom:0.75rem;">Détail du modèle</div>', unsafe_allow_html=True)
            model_cols = st.columns(3)
            with model_cols[0]:
                render_value_card(
                    "Coût des fonds propres",
                    f"{cout_fonds_propres:.2%}",
                    "#2563eb",
                    helper="a + b × c + d + e",
                    comment_key="cout_fonds_propres",
                    badge="Ke",
                )
            with model_cols[1]:
                render_value_card(
                    "Coût de la dette",
                    f"{cout_dette:.2%}",
                    "#dc2626",
                    helper="(spread + a) × (1 - T)",
                    comment_key="cout_dette",
                    badge="Kd",
                )
            with model_cols[2]:
                render_value_card(
                    "WACC",
                    f"{wacc:.2%}",
                    "#16a34a",
                    helper=f"CP {quote_part_equity:.2%} • Dette {quote_part_debt:.2%}",
                    comment_key="wacc",
                    dark=True,
                    badge="WACC",
                )

            local_cols = st.columns(2)
            with local_cols[0]:
                render_value_card(
                    "CMPC locale",
                    f"{wacc_local:.2%}",
                    "#0ea5e9",
                    helper=f"Inflation locale: {inflation_locale:.2%} • mature: {inflation_mature:.2%}",
                    comment_key="wacc_local",
                    badge="local",
                )
            with local_cols[1]:
                render_value_card(
                    "Taxe",
                    f"{tax_rate:.2%}",
                    "#7c3aed",
                    helper=f"Corporate tax rate • {selected_country}",
                    comment_key="beta",
                    badge="T",
                )

        with col_comments:
            st.markdown('<div class="panel" style="padding:1.2rem; margin-top:0.2rem;">', unsafe_allow_html=True)
            st.markdown('<div class="panel-title">Commentaire</div>', unsafe_allow_html=True)
            active_key = st.session_state.get("active_comment_key")
            if active_key:
                active_label = st.session_state.get("active_comment_label", "")
                with st.container(key="comment_bubble"):
                    st.markdown(f"**{active_label}**")
                    st.text_area(
                        "Commentaire",
                        key=f"comment_input_{active_key}",
                        label_visibility="collapsed",
                        placeholder="Votre commentaire…",
                        height=160,
                    )
                    if st.button("✕ Fermer", key="close_comment_bubble"):
                        st.session_state["active_comment_key"] = None
                        st.rerun()
            else:
                st.info("Cliquez sur le bouton 💬 d’une carte pour ajouter un commentaire sur un élément du WACC.")
            st.markdown('</div>', unsafe_allow_html=True)

        # Export Excel
        st.divider()
        st.subheader("Export")
        excel_buffer = generate_wacc_workbook({
            "country": selected_country,
            "industry": selected_industry,
            "valuation_year": valuation_year,
            "avg_30y_rate": avg_30y_rate if avg_30y_rate is not None else 0.0,
            "risk_free_maturity": risk_free_maturity,
            "country_risk_premium": country_risk_premium,
            "beta_desendette": beta_desendetté,
            "gearing_sectoriel": gearing_sectoriel,
            "tax_rate": tax_rate,
            "beta_reendette": b,
            "c": c,
            "d": d,
            "e": e,
            "cout_fonds_propres": cout_fonds_propres,
            "adjusted_spread": adjusted_spread,
            "is_adjusted": is_adjusted,
            "cout_dette": cout_dette,
            "quote_part_equity": quote_part_equity,
            "quote_part_debt": quote_part_debt,
            "wacc": wacc,
            "inflation_mature": inflation_mature,
            "inflation_locale": inflation_locale,
            "wacc_local": wacc_local,
        }, betas_data, erps_data, tax_rates_data, financing_spread_data)
        file_name = f"WACC_{selected_industry}_{selected_country}_{valuation_year}.xlsx".replace(" ", "_")
        st.download_button(
            label="📥 Exporter en Excel",
            data=excel_buffer,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
