import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import sys

def get_yield_curve_data_for_year(year):
    """
    Récupère les données de la courbe des taux pour une année donnée depuis le site du Trésor américain.
    """
    url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value={year}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des données : {e}")
        return None

def get_all_rates_for_year(xml_data, maturity="30"):
    """
    Extrait tous les taux (maturité "10" ou "30" ans) pour une année à partir des données XML.
    """
    if not xml_data:
        return []

    rates_data = []
    root = ET.fromstring(xml_data)

    ns = {
        'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
        'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'
    }

    field_name = f"BC_{maturity}YEAR"

    # Parcourir toutes les entrées de données
    for entry in root.findall('.//m:properties', ns):
        date_str_element = entry.find('d:NEW_DATE', ns)
        rate_element = entry.find(f'd:{field_name}', ns)

        if date_str_element is not None and rate_element is not None and rate_element.text:
            try:
                # Convertir la date et le taux
                rate_date = datetime.strptime(date_str_element.text, '%Y-%m-%dT00:00:00')
                rate_value = float(rate_element.text)
                rates_data.append((rate_date, rate_value))
            except (ValueError, TypeError):
                # Ignorer les entrées où le taux n'est pas un nombre valide (ex: "N/A")
                continue

    return sorted(rates_data, key=lambda x: x[0])

def calculate_average_rate(year, maturity="30"):
    """
    Fonction réutilisable pour calculer le taux moyen annuel des obligations US
    (maturité "10" ou "30" ans, "30" par défaut).
    Retourne le taux moyen en pourcentage, ou None si les données ne sont pas disponibles.
    """
    xml_content = get_yield_curve_data_for_year(year)

    if not xml_content:
        return None

    rates_data = get_all_rates_for_year(xml_content, maturity)

    if rates_data:
        # Extraire uniquement les valeurs de taux pour le calcul
        rate_values = [item[1] for item in rates_data]

        # Calculer et retourner la moyenne
        return sum(rate_values) / len(rate_values)

    return None

def main():
    """
    Fonction principale du script (utilisation en ligne de commande).
    """
    print("="*60)
    print("Calcul du taux moyen annuel des obligations US 30 ans")
    print("="*60)
    
    # Demander l'année à l'utilisateur
    year_input = input("Entrez l'année que vous souhaitez analyser (AAAA) : ")
    
    try:
        year = int(year_input)
        if not 1990 <= year <= datetime.now().year:
            raise ValueError("Année hors plage valide.")
    except ValueError:
        print("Format d'année invalide. Veuillez entrer une année comme '2023'.")
        return

    print(f"\n[🔍] Recherche des données pour l'année {year}...")
    
    average_rate = calculate_average_rate(year)
    
    if average_rate is not None:
        print("\n" + "-"*50)
        print("Résultat de l'analyse")
        print(f"  - Année analysée : {year}")
        print(f"  - Taux moyen US Bond 30 ans : {average_rate:.2f}%")
        print("-"*50)
    else:
        print(f"\n[✗] Aucune donnée de taux à 30 ans n'a été trouvée pour {year}.")

if __name__ == "__main__":
    main()

