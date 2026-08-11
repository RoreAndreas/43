import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from pathlib import Path
import subprocess
import sys

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
    url = "https://www.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
    
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
        st.error(f"Erreur lors du téléchargement/lecture du fichier: {e}")
        return None


# Configuration de la page
st.set_page_config(
    page_title="Betas Damodaran",
    page_icon="📊",
    layout="wide"
)

# Titre
st.title("📊 Betas par Industrie - Damodaran")
st.markdown("Données téléchargées depuis [Stern NYU](https://www.stern.nyu.edu/~adamodar/pc/datasets/betas.xls)")
st.divider()

# Charger les données
with st.spinner("Chargement des données..."):
    data = load_betas_data()

if data is not None:
    # Colonnes pour les filtres
    col1, col2 = st.columns(2)
    
    with col1:
        # Liste déroulante pour l'industrie
        industries = sorted(data[data.columns[0]].dropna().unique().tolist())
        selected_industry = st.selectbox(
            "Sélectionner une industrie",
            industries,
            key="industry_select"
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
    filtered_data = data[data[data.columns[0]].str.lower() == selected_industry.lower()]
    
    if len(filtered_data) > 0:
        # Afficher la donnée sélectionnée
        st.subheader(f"{selected_column} - {selected_industry}")
        
        # Créer un dataframe avec industrie et valeur sélectionnée
        result_df = filtered_data[[data.columns[0], selected_column]].copy()
        result_df.columns = ["Industrie", selected_column]
        
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
        st.warning(f"Aucune donnée trouvée pour l'industrie: {selected_industry}")
    
    st.divider()
    
    # Bouton pour voir toutes les données
    if st.button("Afficher toutes les données"):
        st.subheader("Toutes les données")
        st.dataframe(data, use_container_width=True)
    
    st.caption(f"Total industries: {len(industries)} | Colonnes: {', '.join(columns)}")

else:
    st.error("Impossible de charger les données. Veuillez vérifier votre connexion.")
