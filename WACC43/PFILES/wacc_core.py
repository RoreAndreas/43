"""
Chargement des données Damodaran et calculs du CMPC, sans dépendance à une UI.

Ce module remplace la partie « données + calculs » de l'ancienne application
Streamlit : il est utilisé par le serveur HTML (serve.py) et par l'export.
"""

import difflib
from functools import lru_cache
from io import BytesIO

import pandas as pd
import requests

BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betaemerg.xls"
TAX_URL = "https://www.stern.nyu.edu/~adamodar/pc/datasets/countrytaxrates.xls"
ERPS_URL = "https://www.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
WACC_URL = "https://www.stern.nyu.edu/~adamodar/pc/datasets/wacc.xls"


def _download(url: str) -> BytesIO:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return BytesIO(response.content)


@lru_cache(maxsize=1)
def load_betas_data():
    """Betas sectoriels (plage A10:H104 de la feuille Industry Averages)."""
    df = pd.read_excel(_download(BETAS_URL), sheet_name="Industry Averages", header=None)
    headers = df.iloc[9, 0:8].tolist()
    data = df.iloc[9:104, 0:8]
    data.columns = headers
    return data.reset_index(drop=True)


@lru_cache(maxsize=1)
def load_tax_rates_data():
    """Taux d'imposition par pays (plage A6:C257)."""
    df = pd.read_excel(_download(TAX_URL), sheet_name=0, header=None)
    headers = df.iloc[5, 0:3].tolist()
    data = df.iloc[5:257, 0:3]
    data.columns = headers
    return data.reset_index(drop=True).dropna(how="all")


@lru_cache(maxsize=1)
def load_erps_data():
    """Primes de risque pays + prime de marché mature (cellule E3)."""
    df = pd.read_excel(_download(ERPS_URL), sheet_name="ERPs by country", header=None)
    mature_market_premium = float(df.iloc[2, 4])
    headers = df.iloc[7, 0:6].tolist()
    data = df.iloc[7:165, 0:6]
    data.columns = headers
    return data.reset_index(drop=True).dropna(how="all"), mature_market_premium


@lru_cache(maxsize=1)
def load_financing_spread_data():
    """Spread de financement par industrie (plage A19:L113 du fichier wacc.xls)."""
    df = pd.read_excel(_download(WACC_URL), sheet_name="Industry Averages", header=None)
    headers = df.iloc[18, 0:12].tolist()
    data = df.iloc[19:113, 0:12]
    data.columns = headers
    return data.reset_index(drop=True).dropna(how="all")


@lru_cache(maxsize=1)
def load_spread_adjustment_table():
    """Table d'ajustement du spread (H9:I16) et son correctif (D11)."""
    df = pd.read_excel(_download(WACC_URL), sheet_name="Industry Averages", header=None)
    return {
        "thresholds": df.iloc[9:16, 7].tolist(),
        "spreads": df.iloc[9:16, 8].tolist(),
        "adjustment": float(df.iloc[10, 3]),
    }


@lru_cache(maxsize=32)
def risk_free_rate(year: int, maturity_code: str):
    """Moyenne annuelle du taux US Treasury, mise en cache par (année, maturité)."""
    from get_us_bond_rate import calculate_average_rate

    return calculate_average_rate(year, maturity_code)


# ----- Formules -----

def calcul_beta_reendeté(beta_desendetté: float, gearing_sectoriel: float, tax_rate: float) -> float:
    """beta réendetté = beta désendetté × (1 + gearing × (1 − taux d'IS))"""
    return beta_desendetté * (1 + gearing_sectoriel * (1 - tax_rate))


def calcul_cout_fonds_propres(a: float, b: float, c: float, d: float, e: float) -> float:
    """Coût des fonds propres = a + b × c + d + e (MEDAF)."""
    return a + b * c + d + e


def get_adjusted_spread(cost_of_debt: float, adjustment_table: dict) -> tuple:
    """Spread ajusté par la table de notation. Retourne (spread, est_ajusté)."""
    if adjustment_table is None:
        return cost_of_debt, False
    for threshold, spread in zip(adjustment_table["thresholds"], adjustment_table["spreads"]):
        if pd.notna(threshold) and pd.notna(spread) and cost_of_debt <= float(threshold):
            return float(spread) + adjustment_table["adjustment"], True
    return cost_of_debt, False


def calcul_cout_dette(adjusted_spread: float, a: float, tax_rate: float) -> float:
    """Coût de la dette après impôt = (spread + taux sans risque) × (1 − taux d'IS)."""
    return (adjusted_spread + a) * (1 - tax_rate)


def calcul_wacc(cout_fonds_propres: float, cout_dette: float, quote_part_equity: float, quote_part_debt: float) -> float:
    """WACC = Re × E/V + Rd après impôt × D/V."""
    return cout_fonds_propres * quote_part_equity + cout_dette * quote_part_debt


def calcul_wacc_monnaie_locale(wacc: float, inflation_locale: float, inflation_mature: float) -> float:
    """Conversion du CMPC par le différentiel d'inflation."""
    return (1 + wacc) * (1 + inflation_locale) / (1 + inflation_mature) - 1


# ----- Orchestration -----

def _match_row(df, column, value: str):
    """Ligne exacte, sinon correspondance approchée (cutoff 0.9). Retourne (ligne, libellé)."""
    series = df[column].astype(str).str.strip().str.lower()
    target = str(value).strip().lower()
    exact = df[series == target]
    if len(exact) > 0:
        return exact, None
    matches = difflib.get_close_matches(target, series.dropna().tolist(), n=1, cutoff=0.9)
    if matches:
        return df[series == matches[0]], matches[0]
    return None, None


def options() -> dict:
    """Listes de choix alimentant l'onglet Paramètres."""
    from datetime import datetime

    betas = load_betas_data()
    erps, _ = load_erps_data()
    current_year = datetime.now().year
    return {
        "years": list(range(current_year, current_year - 10, -1)),
        "maturities": ["30Y", "10Y"],
        "countries": sorted(erps[erps.columns[0]].dropna().unique().tolist()),
        "industries": sorted(betas[betas.columns[0]].dropna().unique().tolist()),
    }


def compute(params: dict) -> dict:
    """
    Calcule le CMPC pour un jeu de paramètres.

    `params` : year, maturity, country, industry, d, e, inflation_ref, inflation_local.
    Retourne les valeurs brutes (floats) plus la liste des correspondances approchées.
    """
    betas = load_betas_data()
    tax_rates = load_tax_rates_data()
    erps, mature_market_premium = load_erps_data()
    spreads = load_financing_spread_data()
    adjustment_table = load_spread_adjustment_table()

    year = int(params["year"])
    maturity = params.get("maturity", "30Y")
    country = params["country"]
    industry = params["industry"]
    d = float(params["d"])
    e = float(params["e"])
    inflation_mature = float(params["inflation_ref"])
    inflation_locale = float(params["inflation_local"])

    notes = []

    c = mature_market_premium if mature_market_premium is not None else 0.06

    country_row, _ = _match_row(erps, erps.columns[0], country)
    if country_row is not None and len(country_row) > 0:
        country_risk_premium = float(country_row["Country Risk Premium"].values[0])
    else:
        country_risk_premium = 0.01
        notes.append("Prime de risque pays non trouvée, valeur par défaut utilisée")

    industry_row, _ = _match_row(betas, betas.columns[0], industry)
    if industry_row is not None and len(industry_row) > 0:
        beta_desendette = float(industry_row["Unlevered beta"].values[0])
        gearing_sectoriel = float(industry_row["D/E Ratio"].values[0])
    else:
        beta_desendette, gearing_sectoriel = 1.0, 0.5
        notes.append("Données beta non trouvées, valeurs par défaut utilisées")

    spread_row, spread_match = _match_row(spreads, spreads.columns[0], industry)
    if spread_row is not None and len(spread_row) > 0:
        cost_of_debt = float(spread_row.iloc[0, 5])
        if spread_match:
            notes.append(f"Spread de financement rapproché de « {spread_match} »")
    else:
        cost_of_debt = 0.05
        notes.append("Spread de financement non trouvé, valeur par défaut utilisée")

    tax_row, tax_match = _match_row(tax_rates, tax_rates.columns[0], country)
    if tax_row is not None and len(tax_row) > 0:
        tax_rate = float(tax_row[tax_rates.columns[1]].values[0])
        if tax_match:
            notes.append(f"Taux d'IS rapproché de « {tax_match} »")
    else:
        tax_rate = 0.25
        notes.append("Taux d'IS non trouvé, valeur par défaut utilisée")

    maturity_code = "30" if maturity == "30Y" else "10"
    avg_rate = risk_free_rate(year, maturity_code)
    if avg_rate is None:
        avg_rate = 0.0
        a = 0.03
        notes.append(f"Taux US {maturity} indisponible pour {year}, valeur par défaut utilisée")
    else:
        a = (avg_rate / 100) + country_risk_premium

    b = calcul_beta_reendeté(beta_desendette, gearing_sectoriel, tax_rate)
    cout_fonds_propres = calcul_cout_fonds_propres(a, b, c, d, e)
    adjusted_spread, is_adjusted = get_adjusted_spread(cost_of_debt, adjustment_table)
    quote_part_equity = 1 / (1 + gearing_sectoriel)
    quote_part_debt = 1 - quote_part_equity
    cout_dette = calcul_cout_dette(adjusted_spread, a, tax_rate)
    wacc = calcul_wacc(cout_fonds_propres, cout_dette, quote_part_equity, quote_part_debt)
    wacc_local = calcul_wacc_monnaie_locale(wacc, inflation_locale, inflation_mature)

    return {
        "country": country,
        "industry": industry,
        "valuation_year": year,
        "risk_free_maturity": maturity,
        "avg_30y_rate": avg_rate,
        "country_risk_premium": country_risk_premium,
        "taux_sans_risque_local": a,
        "beta_desendette": beta_desendette,
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
        "notes": notes,
    }


def _num(value):
    """Float exploitable, sinon None (entêtes répétées, cellules vides, 'NA')."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None  # écarte NaN


def build_dataset(years=None, progress=None) -> dict:
    """
    Condense les fichiers Damodaran et les taux Treasury en un jeu de données
    compact (~18 Ko), suffisant pour recalculer un CMPC sans serveur.

    C'est ce dictionnaire qui est embarqué dans la page : le navigateur y lit
    les entrées du pays et de l'industrie choisis, puis applique les formules.
    """
    say = progress or (lambda *_: None)

    say("Betas sectoriels...")
    betas = load_betas_data()
    say("Taux d'imposition...")
    tax_rates = load_tax_rates_data()
    say("Primes de risque pays...")
    erps, mature_market_premium = load_erps_data()
    say("Spreads de financement...")
    spreads = load_financing_spread_data()
    adjustment = load_spread_adjustment_table()

    pays = {}
    for _, row in erps.iterrows():
        name = str(row[erps.columns[0]]).strip()
        crp = _num(row["Country Risk Premium"])
        if name and name.lower() != "nan" and crp is not None:
            pays[name] = {"crp": crp}

    # Les libellés diffèrent d'un fichier Damodaran à l'autre : on résout ici
    # les correspondances approchées, le navigateur n'aura plus qu'à lire la clé.
    tax_names = {}
    for _, row in tax_rates.iterrows():
        name = str(row[tax_rates.columns[0]]).strip()
        value = _num(row[tax_rates.columns[1]])
        if name and name.lower() != "nan" and value is not None:
            tax_names[name.lower()] = value
    for name, entry in pays.items():
        key = name.lower()
        if key in tax_names:
            entry["tax"] = tax_names[key]
        else:
            close = difflib.get_close_matches(key, list(tax_names), n=1, cutoff=0.9)
            if close:
                entry["tax"] = tax_names[close[0]]

    industries = {}
    for _, row in betas.iterrows():
        name = str(row[betas.columns[0]]).strip()
        beta = _num(row["Unlevered beta"])
        de_ratio = _num(row["D/E Ratio"])
        if name and name.lower() != "nan" and beta is not None and de_ratio is not None:
            industries[name] = {"beta": beta, "de": de_ratio}

    spread_names = {}
    for _, row in spreads.iterrows():
        name = str(row[spreads.columns[0]]).strip()
        value = _num(row.iloc[5])
        if name and name.lower() != "nan" and value is not None:
            spread_names[name.lower()] = value
    for name, entry in industries.items():
        key = name.lower()
        if key in spread_names:
            entry["spread"] = spread_names[key]
        else:
            close = difflib.get_close_matches(key, list(spread_names), n=1, cutoff=0.9)
            if close:
                entry["spread"] = spread_names[close[0]]

    adjustment_rows = [
        [float(threshold), float(spread)]
        for threshold, spread in zip(adjustment["thresholds"], adjustment["spreads"])
        if _num(threshold) is not None and _num(spread) is not None
    ]

    if years is None:
        from datetime import datetime

        current = datetime.now().year
        years = list(range(current, current - 10, -1))

    rf = {}
    for year in years:
        for code in ("30", "10"):
            say(f"Taux US Treasury {code}Y {year}...")
            rate = risk_free_rate(year, code)
            if rate is not None:
                # Pas d'arrondi : le taux entre directement dans le coût du capital.
                rf[f"{year}-{code}"] = rate

    available_years = sorted({int(key.split("-")[0]) for key in rf}, reverse=True)

    return {
        "mature": mature_market_premium,
        "adjustment": {"rows": adjustment_rows, "correction": adjustment["adjustment"]},
        "rf": rf,
        "pays": pays,
        "industries": industries,
        "options": {
            "years": available_years,
            "maturities": ["30Y", "10Y"],
            "countries": sorted(pays),
            "industries": sorted(industries),
        },
        "defaults": {
            "year": available_years[0] if available_years else None,
            "maturity": "30Y",
            "country": sorted(pays)[0] if pays else None,
            "industry": sorted(industries)[0] if industries else None,
            "d": 0.01,
            "e": 0.005,
            "inflation_ref": 0.025,
            "inflation_local": 0.03,
        },
    }


def default_params() -> dict:
    """Paramètres d'ouverture de l'application."""
    opts = options()
    return {
        "year": opts["years"][0],
        "maturity": "30Y",
        "country": opts["countries"][0],
        "industry": opts["industries"][0],
        "d": 0.01,
        "e": 0.005,
        "inflation_ref": 0.025,
        "inflation_local": 0.03,
    }
