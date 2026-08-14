# Archive

Scripts antérieurs à l'application web, conservés pour référence. Aucun n'est
importé par `serve.py` : les déplacer ou les supprimer n'a pas d'effet sur
l'application.

## Remplacés par `wacc_core.py`

Ces quatre scripts chargeaient les mêmes données ou appliquaient la même formule.
Ils importent `streamlit`, qui n'est plus une dépendance du projet : ils ne
s'exécutent donc plus en l'état.

| Fichier | Remplacé par |
|---|---|
| `betas_damodaran.py` | `wacc_core.load_betas_data()` |
| `erps_damodaran.py` | `wacc_core.load_erps_data()` |
| `tax_rates_damodaran.py` | `wacc_core.load_tax_rates_data()` |
| `calcul_fonds_propres.py` | `wacc_core.calcul_cout_fonds_propres()` |

## Sujet distinct

`TSR.py` — récupère les taux des obligations souveraines dans les bulletins PDF
de la BRVM. Rien à voir avec la chaîne CMPC actuelle, et il demande deux
dépendances non installées (`beautifulsoup4`, `pdfplumber`). Piste possible pour
un taux sans risque local en zone UEMOA, à reprendre si le besoin se confirme.
