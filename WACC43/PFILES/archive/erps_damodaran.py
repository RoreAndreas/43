import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from pathlib import Path
import subprocess
import sys

# Vérifier et installer openpyxl si nécessaire
try:
    import openpyxl
except ImportError:
    st.warning("Installation de openpyxl en cours...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    import openpyxl


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

        # Extraire la plage A8:F165 (index 7 à 164, colonnes 0 à 5)
        # Les en-têtes sont à la ligne 8 (index 7)
        headers = df.iloc[7, 0:6].tolist()
        data = df.iloc[7:165, 0:6]
        data.columns = headers

        # Réinitialiser l'index
        data = data.reset_index(drop=True)

        # Supprimer les lignes vides
        data = data.dropna(how='all')

        return data

    except Exception as e:
        st.error(f"Erreur lors du téléchargement/lecture du fichier: {e}")
        return None


# Configuration de la page
st.set_page_config(
    page_title="ERPs by Country - Damodaran",
    page_icon="🌍",
    layout="wide"
)

# Titre
st.title("🌍 ERPs by Country - Damodaran")
st.markdown("Données téléchargées depuis [Stern NYU](https://www.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx)")
st.divider()

# Charger les données
with st.spinner("Chargement des données..."):
    data = load_erps_data()

if data is not None:
    # Colonnes pour les filtres
    col1, col2 = st.columns(2)

    with col1:
        # Liste déroulante pour le pays
        countries = sorted(data[data.columns[0]].dropna().unique().tolist())
        selected_country = st.selectbox(
            "Sélectionner un pays",
            countries,
            key="country_select"
        )

    with col2:
        # Liste déroulante pour la colonne à afficher
        columns = [col for col in data.columns if col != data.columns[0]]
        selected_column = st.selectbox(
            "Sélectionner la donnée à afficher",
            columns,
            key="column_select"
        )

    st.divider()

    # Filtrer les données
    filtered_data = data[data[data.columns[0]].str.lower() == selected_country.lower()]

    if len(filtered_data) > 0:
        # Afficher la donnée sélectionnée
        st.subheader(f"{selected_column} - {selected_country}")

        # Créer un dataframe avec pays et valeur sélectionnée
        result_df = filtered_data[[data.columns[0], selected_column]].copy()
        result_df.columns = ["Pays", selected_column]

        # Afficher le tableau
        st.dataframe(result_df, use_container_width=True)

        # Afficher la valeur en surbrillance
        value = filtered_data[selected_column].values[0]

        try:
            value_float = float(value)
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label=selected_column, value=f"{value_float:.4f}")
        except:
            st.info(f"**{selected_column}**: {value}")
    else:
        st.warning(f"Aucune donnée trouvée pour le pays: {selected_country}")

    st.divider()

    # Bouton pour voir toutes les données
    if st.button("Afficher toutes les données"):
        st.subheader("Toutes les données")
        st.dataframe(data, use_container_width=True)

    st.caption(f"Total pays: {len(countries)} | Colonnes: {', '.join(columns)}")

else:
    st.error("Impossible de charger les données. Veuillez vérifier votre connexion.")
