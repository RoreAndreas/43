import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from io import BytesIO
import subprocess
import sys
import difflib
from datetime import datetime
from get_us_bond_rate import calculate_average_rate
from export_wacc import generate_wacc_workbook
from wacc_html import render_wacc_html

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


# Configuration de la page
st.set_page_config(
    page_title="Calcul WACC",
    page_icon="🔵",
    layout="wide"
)

# Charte visuelle alignée sur la maquette wacc_value_tab.html
st.markdown(
    """
    <style>
    .stApp {
        background: #f5f6f8;
    }
    .block-container {
        max-width: 1180px;
        padding-top: 1.75rem;
        padding-bottom: 3rem;
    }
    .app-header {
        background: #ffffff;
        border: 1px solid #e6e8ee;
        border-bottom: none;
        border-radius: 18px 18px 0 0;
        padding: 22px 26px 18px;
    }
    .app-header .brand-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        flex-wrap: wrap;
        gap: 8px;
    }
    .app-header .brand-line {
        display: block;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.02em;
        color: #12131a;
        margin-bottom: 6px;
    }
    .app-header .brand-43 {
        font-style: italic;
        font-size: 1.2em;
    }
    .app-header h1 {
        margin: 0;
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: #12131a;
    }
    .app-header .fiscal-year {
        font-size: 0.85rem;
        color: #6b7280;
        padding-bottom: 4px;
    }
    [data-testid="stTabs"] {
        background: #ffffff;
        border: 1px solid #e6e8ee;
        border-radius: 0 0 18px 18px;
        padding: 0 26px 4px;
        margin-bottom: 22px;
    }
    [data-testid="stTabList"] {
        gap: 28px;
        background: transparent;
        border: none;
        padding: 0;
    }
    [data-testid="stTab"] {
        font-size: 0.92rem;
        font-weight: 600;
        letter-spacing: 0;
        color: #6b7280;
        padding: 14px 2px;
        border-radius: 0;
    }
    [data-testid="stTabList"] button[aria-selected="true"] {
        color: #12131a;
        background: transparent;
        border: none;
        box-shadow: none;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: #6b3fa0;
    }
    [data-testid="stTabs"] [data-baseweb="tab-border"] {
        display: none;
    }
    [data-testid="stTabs"] h2, [data-testid="stTabs"] h3 {
        font-size: 1rem;
        font-weight: 800;
        color: #12131a;
    }
    /* Onglet Paramètres : mêmes cartes que l'onglet Valeurs */
    .st-key-param_perimetre, .st-key-param_primes {
        background: #ffffff;
        border: 1px solid #e6e8ee;
        border-radius: 18px;
        padding: 20px 22px 6px;
        height: 100%;
    }
    .param-title {
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #9298a6;
        margin-bottom: 6px;
    }
    .st-key-param_perimetre [data-testid="stWidgetLabel"] p,
    .st-key-param_primes [data-testid="stWidgetLabel"] p {
        font-size: 0.82rem;
        font-weight: 600;
        color: #33394a;
    }
    .st-key-param_perimetre div[data-baseweb="select"] > div,
    .st-key-param_primes [data-testid="stNumberInputContainer"] {
        border-radius: 12px;
        border-color: #e6e8ee;
        background: #fbfbfd;
    }
    [data-testid="stAlert"] {
        border-radius: 12px;
        font-size: 0.82rem;
    }
    [data-testid="stDownloadButton"] button {
        border-radius: 12px;
        border: 1px solid #e6e8ee;
        background: #ffffff;
        color: #12131a;
        font-weight: 700;
        padding: 0.6rem 1.1rem;
    }
    [data-testid="stDownloadButton"] button:hover {
        border-color: #6b3fa0;
        color: #6b3fa0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# En-tête : même composition que la maquette (marque, titre, méthode) ;
# les onglets Streamlit ci-dessous prolongent visuellement cette carte.
st.markdown(
    """
    <div class="app-header">
      <div class="brand-row">
        <div>
          <span class="brand-line">Making it the <em class="brand-43">43</em>. Type of way</span>
          <h1>Coût moyen pondéré du capital</h1>
        </div>
        <div class="fiscal-year">Méthode indirecte</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

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
        current_year = datetime.now().year
        col_perimetre, col_primes = st.columns(2, gap="large")

        # ----- Carte 1 : périmètre de calcul -----
        with col_perimetre, st.container(key="param_perimetre"):
            st.markdown('<div class="param-title">Périmètre</div>', unsafe_allow_html=True)

            valuation_year = st.selectbox(
                "Année de valorisation",
                options=range(current_year, current_year - 10, -1), # 10 dernières années
                index=0
            )

            risk_free_maturity = st.selectbox(
                "Maturité du taux sans risque",
                options=["30Y", "10Y"],
                index=0,
                help="Taux des bons du Trésor US utilisé comme taux sans risque"
            )
            risk_free_maturity_code = "30" if risk_free_maturity == "30Y" else "10"

            countries = sorted(erps_data[erps_data.columns[0]].dropna().unique().tolist())
            selected_country = st.selectbox(
                "Pays",
                countries,
                key="country_select"
            )

            industries = sorted(betas_data[betas_data.columns[0]].dropna().unique().tolist())
            selected_industry = st.selectbox(
                "Industrie",
                industries,
                key="industry_select"
            )

            # Messages de correspondance approchée, remplis lors du calcul
            country_match_placeholder = st.empty()
            financing_spread_placeholder = st.empty()

        # ----- Carte 2 : primes et inflation saisies à la main -----
        with col_primes, st.container(key="param_primes"):
            st.markdown('<div class="param-title">Primes et inflation</div>', unsafe_allow_html=True)

            d = st.number_input(
                "Prime de taille (d)",
                value=0.01,
                step=0.001,
                format="%.3f",
                help="Exemple: 0.01 pour 1%"
            )

            e = st.number_input(
                "Prime spécifique (e)",
                value=0.005,
                step=0.001,
                format="%.3f",
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

    avg_30y_rate = calculate_average_rate(valuation_year, risk_free_maturity_code)

    with tab_valeurs:
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

        # Jeu de valeurs partagé par la sortie HTML et l'export Excel
        wacc_values = {
            "country": selected_country,
            "industry": selected_industry,
            "valuation_year": valuation_year,
            "avg_30y_rate": avg_30y_rate if avg_30y_rate is not None else 0.0,
            "risk_free_maturity": risk_free_maturity,
            "country_risk_premium": country_risk_premium,
            "taux_sans_risque_local": a,
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
            "cout_dette_avant_impot": adjusted_spread + a,
            "cout_dette": cout_dette,
            "quote_part_equity": quote_part_equity,
            "quote_part_debt": quote_part_debt,
            "wacc": wacc,
            "inflation_mature": inflation_mature,
            "inflation_locale": inflation_locale,
            "wacc_local": wacc_local,
        }

        # Rendu de l'onglet Valeurs : cartes dépliables + panneau de détail,
        # au format de la maquette wacc_value_tab.html
        wacc_page_html = render_wacc_html(wacc_values, standalone=False)
        components.html(wacc_page_html, height=780, scrolling=True)

        # Export
        st.divider()
        st.subheader("Export")
        base_name = f"WACC_{selected_industry}_{selected_country}_{valuation_year}".replace(" ", "_")
        col_html, col_excel = st.columns(2)

        with col_html:
            st.download_button(
                label="📄 Exporter en HTML",
                data=render_wacc_html(wacc_values, standalone=True).encode("utf-8"),
                file_name=f"{base_name}.html",
                mime="text/html",
                use_container_width=True,
            )

        with col_excel:
            excel_buffer = generate_wacc_workbook(
                wacc_values, betas_data, erps_data, tax_rates_data, financing_spread_data
            )
            st.download_button(
                label="📥 Exporter en Excel",
                data=excel_buffer,
                file_name=f"{base_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
