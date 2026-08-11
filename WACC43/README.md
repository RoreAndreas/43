# WACC Calculator

Application Streamlit de calcul du **coût moyen pondéré du capital (WACC)** et du
**coût des fonds propres**, à partir des données publiques de référence :

- **Damodaran (NYU Stern)** — bêtas sectoriels, primes de risque pays (ERP), taux d'imposition
- **US Treasury** — taux sans risque (obligations 10/30 ans)

## Lancer l'application

```bash
pip install -r requirements.txt
cd PFILES
streamlit run app.py
```

## Structure

```
PFILES/
  app.py                  # Interface Streamlit
  get_us_bond_rate.py     # Taux sans risque US (US Treasury)
  export_wacc.py          # Export du calcul WACC en classeur Excel
  betas_damodaran.py      # Récupération des bêtas sectoriels
  erps_damodaran.py       # Primes de risque pays
  tax_rates_damodaran.py  # Taux d'imposition par pays
  calcul_fonds_propres.py # Calcul du coût des fonds propres
  TSR.py
DATA/
  wacc_template.xlsx      # Modèle de mise en forme (référence)
```

## Note

Les données sont téléchargées à la volée depuis les sources publiques Damodaran et US Treasury.
Pour afficher un logo, déposez un fichier `DATA/logo.png`.
