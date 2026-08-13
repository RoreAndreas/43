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

st.title("Calcul du Coût Moyen Pondéré du Capital - Méthode indirecte")
st.markdown("**Formule Coût Fonds Propres:** Coût = a + b × c + d + e")
st.divider()

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

# Charger les données
with st.spinner(f"Chargement des données pour {valuation_year}..."):
    betas_data = load_betas_data()
    tax_rates_data = load_tax_rates_data()
    erps_data, mature_market_premium = load_erps_data()
    financing_spread_data = load_financing_spread_data()
    spread_adjustment_table = load_spread_adjustment_table()
    # Calculer le taux US pour la maturité et l'année choisies
    avg_30y_rate = calculate_average_rate(valuation_year, risk_free_maturity_code)

if betas_data is not None and tax_rates_data is not None and erps_data is not None and financing_spread_data is not None:
    # Colonnes pour une meilleure disposition
    col1, col2 = st.columns(2)

    with col1:
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

    with col2:
        # Extraire les données pour le pays sélectionné
        country_data = erps_data[erps_data[erps_data.columns[0]].str.lower() == selected_country.lower()]
        # Prime de risque marché actions (c) - prime pour un marché mature (cellule E3)
        c = mature_market_premium if mature_market_premium is not None else 0.06
        if len(country_data) > 0:
            # Prime de risque pays (pour le calcul de 'a')
            country_risk_premium = float(country_data["Country Risk Premium"].values[0])
        else:
            country_risk_premium = 0.01 # Valeur par défaut
            st.warning("Primes de risque non trouvées, valeurs par défaut utilisées")

        # Extraire les données pour l'industrie sélectionnée
        industry_data = betas_data[betas_data[betas_data.columns[0]].str.lower() == selected_industry.lower()]
        if len(industry_data) > 0:
            # Beta désendetté (colonne F)
            beta_desendetté = float(industry_data["Unlevered beta"].values[0])
            # Gearing sectoriel
            gearing_sectoriel = float(industry_data["D/E Ratio"].values[0])
        else:
            beta_desendetté = 1.0  # Valeur par défaut
            gearing_sectoriel = 0.5  # Valeur par défaut
            st.warning("Données beta non trouvées, valeurs par défaut utilisées")

        # Extraire les données de spread de financement pour l'industrie sélectionnée
        financing_spread_industry = financing_spread_data[financing_spread_data[financing_spread_data.columns[0]].str.lower() == selected_industry.lower()]
        if len(financing_spread_industry) > 0:
            # Spread de financement - colonne F, index 5 (Std Dev in Stock)
            cost_of_debt = float(financing_spread_industry.iloc[0, 5])
            # E/(D+E) - proportion de fonds propres - colonne E, index 4
            proportion_equity = float(financing_spread_industry.iloc[0, 4])
            financing_spread_placeholder.empty()  # Effacer le message d'avertissement si trouvé
        else:
            # Fuzzy matching si correspondance exacte échoue
            financing_industries_list = financing_spread_data[financing_spread_data.columns[0]].dropna().str.lower().tolist()
            matches = difflib.get_close_matches(selected_industry.lower(), financing_industries_list, n=1, cutoff=0.9)
            if matches:
                matched_industry = matches[0]
                financing_spread_industry = financing_spread_data[financing_spread_data[financing_spread_data.columns[0]].str.lower() == matched_industry]
                cost_of_debt = float(financing_spread_industry.iloc[0, 5])
                proportion_equity = float(financing_spread_industry.iloc[0, 4])
                financing_spread_placeholder.info(f"Financing spread industry match -> {matched_industry}")
            else:
                cost_of_debt = 0.05  # Valeur par défaut
                proportion_equity = 0.6  # Valeur par défaut
                st.warning("Données de spread de financement non trouvées, valeurs par défaut utilisées")
                financing_spread_placeholder.empty()

        # Tax rate pour le pays (corporate tax rate)
        tax_country_data = tax_rates_data[tax_rates_data[tax_rates_data.columns[0]].str.strip().str.lower() == selected_country.lower().strip()]
        if len(tax_country_data) > 0:
            tax_rate = float(tax_country_data[tax_rates_data.columns[1]].values[0]) # Corporate tax rate
            country_match_placeholder.empty() # Effacer le message si une correspondance exacte est trouvée
        else:
            # Fuzzy matching si correspondance exacte échoue
            tax_countries_list = tax_rates_data[tax_rates_data.columns[0]].dropna().str.strip().str.lower().tolist()
            matches = difflib.get_close_matches(selected_country.lower().strip(), tax_countries_list, n=1, cutoff=0.9)
            if matches:
                matched_country = matches[0]
                tax_country_data = tax_rates_data[tax_rates_data[tax_rates_data.columns[0]].str.strip().str.lower() == matched_country]
                tax_rate = float(tax_country_data[tax_rates_data.columns[1]].values[0]) # Corporate tax rate
                country_match_placeholder.info(f"Corp. Tax files match -> {matched_country}")
            else:
                tax_rate = 0.25  # Valeur par défaut
                st.warning("Corporate tax rate non trouvé, valeur par défaut utilisée")
                country_match_placeholder.empty() # Effacer le message si aucune correspondance n'est trouvée

        # Calcul du beta réendetté
        b = calcul_beta_reendeté(beta_desendetté, gearing_sectoriel, tax_rate)

        # Calcul du Taux sans risque local (a)
        if avg_30y_rate is not None:
            # Le taux US est déjà en %, on le convertit en décimal
            a = (avg_30y_rate / 100) + country_risk_premium
        else:
            a = 0.03 # Fallback si le taux US n'est pas trouvé
            st.error(f"Impossible de calculer le taux US {risk_free_maturity} pour {valuation_year}. Utilisation d'une valeur par défaut pour 'a'.")

        # Calcul du Coût des fonds propres
        cout_fonds_propres = calcul_cout_fonds_propres(a, b, c, d, e)
        
        # Ajuster le spread de financement si applicable
        adjusted_spread, is_adjusted = get_adjusted_spread(cost_of_debt, spread_adjustment_table)

        # ===== AFFICHAGE DANS LE NOUVEL ORDRE =====

        # 1. Tableau de détermination du taux sans risque (bleu)
        if avg_30y_rate is not None:
            st.info(
                f"""
                **Détermination du taux sans risque:**
                - Taux US Bond {risk_free_maturity} ({valuation_year}) : {avg_30y_rate:.2f}%
                - Prime de risque pays : {country_risk_premium:.2%}
                
                **Taux sans risque local (a) : {a:.2%}**
                """
            )
        else:
            country_risk_premium_display = f"{country_risk_premium:.2%}"
            st.info(
                f"""
                **Détermination du taux sans risque:**
                - Prime de risque pays : {country_risk_premium_display}
                
                **Taux sans risque local (a) : {a:.2%}** (valeur par défaut)
                """
            )

        # 2 Carré gris foncé avec beta désendetté et autres infos
        st.markdown(f"""
        <div style="background-color: #404040; padding: 8px; border-radius: 8px; color: white; margin-bottom: 15px;">
            <div style="margin-bottom: 4px; font-weight: bold;">Beta désendetté: {beta_desendetté:.3f}</div>
            <div style="margin-bottom: 4px;">Gearing sectoriel: {gearing_sectoriel:.2f}</div>
            <div style="margin-bottom: 4px;">Corporate Tax Rate: {tax_rate*100:.0f}%</div>
            <div style="font-weight: bold;">Beta réendetté (b): {b:.3f}</div>
        </div>
        """, unsafe_allow_html=True)

        # 3 Prime de taille et prime spécifique, dans un carré gris clair
        st.markdown(f"""
        <div style="background-color: #f0f0f0; padding: 8px; border-radius: 8px; margin-bottom: 15px;">
            <div style="margin-bottom: 4px;">Prime de risque marché (c): {c:.2%}</div>
            <div style="margin-bottom: 4px;">Prime de taille (d): {d:.2%}</div>
            <div style="margin-bottom: 2px;">Prime spécifique (e): {e:.2%}</div>
        </div>
        """, unsafe_allow_html=True)


        # 3.5 Spread de financement
        if is_adjusted:
            spread_display = f"{adjusted_spread:.2%}"
        else:
            spread_display = f"{adjusted_spread:.2%}"
        
        st.markdown(f"""
        <div style="background-color: #404040; padding: 9px; border-radius: 8px; color: white; margin-bottom: 15px;">
            <div style="margin-bottom: 0px; font-weight: bold; font-size: 0.95em;">Spread de Financement: {spread_display}</div>
        </div>
        """, unsafe_allow_html=True)

        # 3.3 Quote-parts des fonds propres et de la dette
        quote_part_equity = 1 / (1 + gearing_sectoriel)
        quote_part_debt = 1 - quote_part_equity
        
        st.markdown(f"""
        <div style="background-color: #f0f0f0; padding: 8px; border-radius: 8px; margin-bottom: 15px;">
            <div style="margin-bottom: 4px;">Quote-part Fonds Propres: {quote_part_equity:.2%}</div>
            <div style="margin-bottom: 2px;">Quote-part Dette: {quote_part_debt:.2%}</div>
        </div>
        """, unsafe_allow_html=True)

        # 4 Coût des fonds propres en gras
        cout_fonds_propres = calcul_cout_fonds_propres(a, b, c, d, e)
        st.markdown(f"""
        <div style="margin-bottom:5px; font-size: 1.15em; font-weight: bold; color: #1f77b4; text-align: center; padding: 6px; background-color: #f0f0f0; border-radius: 8px;">
            Coût des fonds propres: {cout_fonds_propres:.2%}
        </div>
        """, unsafe_allow_html=True)

        # 5 Calcul du coût de la dette
        cout_dette = calcul_cout_dette(adjusted_spread, a, tax_rate)
        st.markdown(f"""
        <div style="margin-bottom:5px;font-size: 1.15em; font-weight: bold; color: #d62728; text-align: center; padding:6px; background-color: #f0f0f0; border-radius: 8px;">
            Coût de la Dette: {cout_dette:.2%}
        </div>
        """, unsafe_allow_html=True)

        # 6 Calcul et affichage du WACC
        wacc = calcul_wacc(cout_fonds_propres, cout_dette, quote_part_equity, quote_part_debt)
        st.markdown(f"""
        <div style="background-color: #f0f0f0;margin-bottom:5px;font-size: 1.2em; font-weight: bold; color: #2ca02c; text-align: center; padding: 6px; background-color: #f0f0f0; border-radius: 8px;">
            WACC: {wacc:.2%}
        </div>
        """, unsafe_allow_html=True)

        # 7 CMPC en monnaie locale
        wacc_local = calcul_wacc_monnaie_locale(wacc, inflation_locale, inflation_mature)
        st.markdown(f"""
        <div style="background-color: #f0f0f0;margin-bottom:5px;font-size: 1.2em; font-weight: bold; color: #2ca02c; text-align: center; padding: 6px; background-color: #f0f0f0; border-radius: 8px;">
            CMPC en monnaie locale: {wacc_local:.2%}
        </div>
        """, unsafe_allow_html=True)

    # Détail du calcul dans col1
    with col1:
        st.info(
            f"""
            **Détail du calcul Coût Fonds Propres:**
            - a = {a:.2%}
            - b × c = {b*c:.2%}
            - d = {d:.2%}
            - e = {e:.2%}
            
            **Total:** {cout_fonds_propres:.2%}
            
            ---
            
            **Détail du calcul Coût de la Dette:**
            - Spread = {adjusted_spread:.4f}
            - a × (1 - Tax Rate) = {a:.4f} × {1-tax_rate:.4f} = {a * (1-tax_rate):.4f}
            
            **Total:** {cout_dette:.2%}
            """
        )

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
