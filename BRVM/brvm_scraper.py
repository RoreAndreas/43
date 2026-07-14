import requests
from bs4 import BeautifulSoup
import json
import urllib3
import re
from datetime import datetime
import os

def scrape_brvm_ticker():
    url = "https://www.brvm.org/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        ticker_section = soup.find('section', id='slide-seance')
        
        if not ticker_section:
            return None
            
        ticker_text = ticker_section.get_text(separator='|', strip=True)
        parts = [p.strip() for p in ticker_text.split('|') if p.strip()]
        
        data = []
        for i in range(0, len(parts) - 2, 3):
            if re.match(r'^[A-Z]{3,}$', parts[i]) and '%' in parts[i+2]:
                data.append({
                    "symbole": parts[i],
                    "prix": parts[i+1],
                    "variation": parts[i+2]
                })
        
        return data
            
    except Exception as e:
        print(f"Erreur lors du scraping : {e}")
        return None

def update_data():
    data = scrape_brvm_ticker()
    if data:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = {
            "last_update": timestamp,
            "count": len(data),
            "data": data
        }
        
        # Sauvegarde du dernier résultat
        script_dir = os.path.dirname(os.path.abspath(__file__))
        latest_file = os.path.join(script_dir, "brvm_latest.json")
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
            
        # Ajout à l'historique
        history_file = os.path.join(script_dir, "brvm_history.json")
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(result)
        # Garder seulement les 100 dernières entrées pour éviter un fichier trop lourd
        history = history[-100:]
        
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
            
        print(f"[{timestamp}] Mise à jour réussie : {len(data)} titres récupérés.")
    else:
        print(f"[{datetime.now()}] Échec de la mise à jour.")

if __name__ == "__main__":
    update_data()
