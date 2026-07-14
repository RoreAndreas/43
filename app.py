import streamlit as st
import json
import os
import re
import io
import csv
import subprocess
import sys
import time
import hashlib
import base64
import pandas as pd
import altair as alt

# ─── Chemins ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BRVM_FILE  = os.path.normpath(os.path.join(SCRIPT_DIR, "BRVM",   "brvm_latest.json"))
SIKA_FILE  = os.path.normpath(os.path.join(SCRIPT_DIR, "SIKAPRO", "sikapro_data.json"))
RICHBOURSE_FILE = os.path.normpath(os.path.join(SCRIPT_DIR, "RICHBOURSE", "richbourse_actualites.json"))
BRVM_SCRAPER = os.path.normpath(os.path.join(SCRIPT_DIR, "BRVM",   "brvm_scraper.py"))
SIKA_SCRAPER = os.path.normpath(os.path.join(SCRIPT_DIR, "SIKAPRO", "sikapro_scraper.py"))
RICHBOURSE_SCRAPER = os.path.normpath(os.path.join(SCRIPT_DIR, "RICHBOURSE", "richbourse_scraper.py"))
RICHBOURSE_INDEX_URL = "https://www.richbourse.com/common/actualite/index"
PYTHON_EXE   = sys.executable
BRVM_LONG_FILE = os.path.join(SCRIPT_DIR, "BRVM_long.xlsx")

VIEW_GLOBAL  = "📊 Analyse globale"
VIEW_SOCIETE = "🏢 Analyse par société"

FINANCIALS_COLUMNS = [
    "Société", "Ticker", "FY", "Trimestre",
    "CA_mFCFA", "GP_mFCFA", "EBITDA_mFCFA", "EBIT_mFCFA", "RN_mFCFA",
]
FY_ORDER = ["FY23", "FY24", "FY25", "FY26"]
QUARTER_ORDER = ["Q1", "Q2", "Q3", "Q4"]

# Type de donnée S&P Capital IQ (BRVM_long.xlsx) → colonne du tableau financier
FINANCIALS_TYPE_TO_COLUMN = {
    "IQ_TOTAL_REV":       "CA_mFCFA",
    "IQ_GP":               "GP_mFCFA",
    "IQ_EBITDA":           "EBITDA_mFCFA",
    "IQ_EBIT":             "EBIT_mFCFA",
    "IQ_NET_INC_PARENT":   "RN_mFCFA",
}
# Tickers dont le code diffère entre BRVM_long.xlsx et les sources BRVM/SIKAPRO
FINANCIALS_TICKER_ALIASES = {"ETI": "ETIT"}

METRICS = {
    "CA":          ("CA_mFCFA",     "Chiffre d'affaires (mFCFA)"),
    "Marge brute": ("GP_mFCFA",     "Marge brute (mFCFA)"),
    "EBITDA":      ("EBITDA_mFCFA", "EBITDA (mFCFA)"),
    "EBIT":        ("EBIT_mFCFA",   "EBIT (mFCFA)"),
    "RN":          ("RN_mFCFA",     "Résultat net (mFCFA)"),
}


# ─── Utilitaires ──────────────────────────────────────────────────────────────
def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_price(text):
    """Nettoie une chaîne de prix (ex: '3 650', '3.650', '3,650') → float."""
    if text is None:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", str(text).replace("\xa0", "").replace(" ", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def load_financials():
    """Charge le CA, la marge brute, l'EBITDA, l'EBIT et le RN par société/trimestre
    depuis BRVM_long.xlsx (format long S&P Capital IQ) et les met en forme large,
    en mFCFA (la source est en milliers de FCFA)."""
    if not os.path.exists(BRVM_LONG_FILE):
        return pd.DataFrame(columns=FINANCIALS_COLUMNS)

    raw = pd.read_excel(BRVM_LONG_FILE, sheet_name="Donnees")
    raw = raw[raw["type_code"].isin(FINANCIALS_TYPE_TO_COLUMN)].copy()
    raw["Ticker"] = raw["ticker"].replace(FINANCIALS_TICKER_ALIASES)
    raw["FY"] = "FY" + (raw["annee"] % 100).astype(int).astype(str).str.zfill(2)
    raw["colonne"] = raw["type_code"].map(FINANCIALS_TYPE_TO_COLUMN)
    raw["valeur_mFCFA"] = raw["valeur"] / 1000

    pivot = raw.pivot_table(
        index=["societe", "Ticker", "FY", "trimestre"],
        columns="colonne",
        values="valeur_mFCFA",
        aggfunc="first",
    ).reset_index()
    pivot = pivot.rename(columns={"societe": "Société", "trimestre": "Trimestre"})

    for col in FINANCIALS_COLUMNS:
        if col not in pivot.columns:
            pivot[col] = None
    return pivot[FINANCIALS_COLUMNS]


def run_scraper(script_path, extra_env=None):
    try:
        env = os.environ.copy()
        if extra_env:
            env.update({k: v for k, v in extra_env.items() if v})
        result = subprocess.run(
            [PYTHON_EXE, script_path],
            capture_output=True,
            cwd=os.path.dirname(script_path),
            timeout=120,
            env=env,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        return result.returncode == 0, stdout + stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout : le scraper a pris plus de 2 minutes."
    except Exception as e:
        return False, str(e)


def sikapro_credentials_env():
    """Identifiants SikaFinance PRO pour le scraper, transmis via l'environnement.
    En local : SIKAPRO/config.json (non versionné). Sur Streamlit Cloud : Secrets
    (SIKAPRO_LOGIN / SIKAPRO_PASSWORD), à défaut de config.json."""
    try:
        return {
            "SIKAPRO_LOGIN": st.secrets.get("SIKAPRO_LOGIN", ""),
            "SIKAPRO_PASSWORD": st.secrets.get("SIKAPRO_PASSWORD", ""),
        }
    except Exception:
        return {}


def cell_html(text, align="left", bold=False, bg=None, extra_style=""):
    """Rend une cellule de tableau stylée (bordures + fond), pour reconstituer l'apparence du tableau natif."""
    style = (
        f"padding:6px 10px; border-bottom:1px solid rgba(128,128,128,0.35); "
        f"border-right:1px solid rgba(128,128,128,0.2); "
        f"text-align:{align}; font-weight:{'700' if bold else '400'};"
    )
    if bg:
        style += f" background-color:{bg};"
    if extra_style:
        style += f" {extra_style}"
    return f"<div style='{style}'>{text}</div>"


def style_ratio(val):
    """Rouge uniquement pour Ratio ≤ 5%."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v <= 5:
        return "background-color: #b71c1c; color: white; font-weight: bold"
    return ""


def fmt_ratio(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    return f"{val:.2f}%"


def fmt_ecart(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    return f"{val:,.0f}".replace(",", " ")


def fmt_volatilite(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    return f"{val:.2f}%"


APP_PASSWORD = "alexkakouisnice"
SESSION_TIMEOUT_SECONDS = 30 * 60
LOGO_FILE = os.path.join(SCRIPT_DIR, "assets", "logo.png")


@st.cache_data
def _logo_b64():
    with open(LOGO_FILE, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ─── Persistance de la session (survit à un rafraîchissement, expire après
# 30 min d'inactivité) — un jeton signé est gardé dans l'URL (query params)
# et son horodatage est glissé à chaque exécution du script.
def _auth_token(ts):
    return hashlib.sha256(f"{APP_PASSWORD}:{ts}".encode()).hexdigest()[:16]


def _restore_session_from_url():
    ts_raw = st.query_params.get("ts")
    token = st.query_params.get("tok")
    if not ts_raw or not token:
        return False
    try:
        ts = int(ts_raw)
    except ValueError:
        return False
    if time.time() - ts > SESSION_TIMEOUT_SECONDS:
        return False
    return token == _auth_token(ts)


def _persist_session():
    ts = int(time.time())
    st.query_params["ts"] = str(ts)
    st.query_params["tok"] = _auth_token(ts)


def _clear_session():
    st.query_params.pop("ts", None)
    st.query_params.pop("tok", None)
    st.session_state.authenticated = False


# ─── Porte d'accès ──────────────────────────────────────────────────────────
def render_login_gate():
    if not st.session_state.get("authenticated") and _restore_session_from_url():
        st.session_state.authenticated = True

    if st.session_state.get("authenticated"):
        _persist_session()
        return

    _clear_session()

    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] { background: #000000; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"] { display: none; }
        .login-logo { display: flex; justify-content: center; margin-bottom: 18px; }
        .login-logo img { width: 100%; max-width: 260px; }
        .login-subtitle {
            text-align: center; color: rgba(255,255,255,0.55);
            font-size: 0.78rem; letter-spacing: 0.3em; text-transform: uppercase;
            margin-bottom: 30px;
        }
        .login-divider {
            width: 64px; height: 1px; margin: 0 auto 30px auto;
            background: rgba(255,255,255,0.25);
        }
        .login-footer {
            text-align: center; margin-top: 20px;
            color: rgba(255,255,255,0.25); font-size: 0.72rem; letter-spacing: 0.05em;
        }
        .st-key-login-card {
            background: #000000;
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 10px;
            padding: 8px 36px 26px 36px;
        }
        .st-key-login-card label p {
            color: rgba(255,255,255,0.7) !important;
            font-size: 0.78rem !important;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            text-align: center;
        }
        .st-key-login-card [data-testid="stTextInputRootElement"] { justify-content: center; }
        .st-key-login-card input {
            background-color: #000000 !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.4) !important;
            text-align: center;
        }
        .st-key-login-card input:focus {
            border-color: #ffffff !important;
            box-shadow: 0 0 0 1px rgba(255,255,255,0.5) !important;
        }
        .st-key-login-card button {
            background: #ffffff !important;
            color: #000000 !important;
            border: none !important;
            font-weight: 700 !important;
            letter-spacing: 0.06em;
        }
        .st-key-login-card button:hover {
            background: rgba(255,255,255,0.85) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_mid, col_r = st.columns([1, 1.1, 1])
    with col_mid:
        st.markdown("<div style='height:12vh'></div>", unsafe_allow_html=True)
        if os.path.exists(LOGO_FILE):
            st.markdown(
                f"<div class='login-logo'><img src='data:image/png;base64,{_logo_b64()}'></div>",
                unsafe_allow_html=True,
            )
        st.markdown("<div class='login-subtitle'>To the top</div>", unsafe_allow_html=True)
        st.markdown("<div class='login-divider'></div>", unsafe_allow_html=True)

        with st.container(key="login-card"):
            with st.form("login_form"):
                password = st.text_input("Mot de passe", type="password", placeholder="••••••••••")
                submitted = st.form_submit_button("Entrer", use_container_width=True)
            if submitted:
                if password == APP_PASSWORD:
                    st.session_state.authenticated = True
                    _persist_session()
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect.")

        st.markdown(
            "<div class='login-footer'>Analyse comparative BRVM × SikaFinance PRO</div>",
            unsafe_allow_html=True,
        )

    st.stop()


# ─── Configuration de la page ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Analyse BRVM × SikaFinance PRO",
    page_icon="📊",
    layout="wide",
)

render_login_gate()

st.markdown("<h4 style='margin-bottom:2px'>📊 Analyse comparative — BRVM × SikaFinance PRO</h4>", unsafe_allow_html=True)

# ─── État de session ───────────────────────────────────────────────────────────
if "active_view" not in st.session_state:
    st.session_state.active_view = VIEW_GLOBAL
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None
if "sort_column" not in st.session_state:
    st.session_state.sort_column = "Ticker"
if "sort_ascending" not in st.session_state:
    st.session_state.sort_ascending = True
if "only_matched" not in st.session_state:
    st.session_state.only_matched = True

# ─── Bouton d'actualisation ───────────────────────────────────────────────────
col_btn, col_empty = st.columns([1, 3])
with col_btn:
    if st.button("🔄 Actualiser", use_container_width=True):
        with st.spinner("Mise à jour BRVM, SIKAPRO et RichBourse..."):
            ok1, log1 = run_scraper(BRVM_SCRAPER)
            ok2, log2 = run_scraper(SIKA_SCRAPER, extra_env=sikapro_credentials_env())
            ok3, log3 = run_scraper(RICHBOURSE_SCRAPER)
        if ok1 and ok2 and ok3:
            st.success("Les trois sources mises à jour.")
        else:
            brvm_status = "OK" if ok1 else "ERREUR"
            sika_status = "OK" if ok2 else "ERREUR"
            rich_status = "OK" if ok3 else "ERREUR"
            st.warning(f"BRVM : {brvm_status}  |  SIKAPRO : {sika_status}  |  RichBourse : {rich_status}")
            if not ok1:
                with st.expander("Log BRVM"):
                    st.code(log1)
            if not ok2:
                with st.expander("Log SIKAPRO"):
                    st.code(log2)
            if not ok3:
                with st.expander("Log RichBourse"):
                    st.code(log3)
        st.rerun()

# ─── Chargement des données ───────────────────────────────────────────────────
brvm_raw = load_json(BRVM_FILE)
sika_raw = load_json(SIKA_FILE)

missing = []
if brvm_raw is None:
    missing.append(f"BRVM — `brvm_latest.json` introuvable (lancer brvm_scraper.py)")
if sika_raw is None:
    missing.append(f"SIKAPRO — `sikapro_data.json` introuvable (lancer sikapro_scraper.py)")

if missing:
    st.error("Fichiers de données manquants :")
    for m in missing:
        st.markdown(f"- {m}")
    st.stop()

# ─── Métadonnées ──────────────────────────────────────────────────────────────
st.markdown(
    f"<small>BRVM : <b>{brvm_raw.get('last_update','N/A')}</b> ({brvm_raw.get('count',0)} titres) &nbsp;|&nbsp; "
    f"SIKAPRO : <b>{sika_raw.get('last_update','N/A')}</b> ({sika_raw.get('count',0)} titres)</small>",
    unsafe_allow_html=True,
)

if st.session_state.active_view == VIEW_GLOBAL:
    st.checkbox(
        "Afficher uniquement les titres présents dans les deux sources",
        key="only_matched",
    )

st.divider()

# ─── Index par ticker ─────────────────────────────────────────────────────────
brvm_index = {
    item["symbole"].upper(): item
    for item in brvm_raw.get("data", [])
}
sika_index = {
    item["ticker"].upper(): item
    for item in sika_raw.get("data", [])
}

# ─── Construction du tableau ──────────────────────────────────────────────────
rows = []
all_tickers = sorted(set(brvm_index) | set(sika_index))

for ticker in all_tickers:
    brvm_item = brvm_index.get(ticker)
    sika_item = sika_index.get(ticker)

    cours_brvm_str = brvm_item["prix"] if brvm_item else None
    min_mois_str   = sika_item["cours_bas_1mois_str"] if sika_item else None
    nom_societe    = sika_item["nom_societe"] if sika_item else (
                     brvm_item.get("symbole", ticker) if brvm_item else ticker)

    cours_brvm = parse_price(cours_brvm_str)
    min_mois   = sika_item["cours_bas_1mois"]      if sika_item else None
    max_mois   = sika_item.get("cours_haut_1mois")  if sika_item else None
    max_mois_str = sika_item.get("cours_haut_1mois_str") if sika_item else None

    # Écart (XOF)
    ecart = None
    if cours_brvm is not None and min_mois is not None:
        ecart = round(cours_brvm - min_mois, 2)

    # Ratio (%) = écart / cours_brvm × 100
    ratio = None
    if ecart is not None and cours_brvm and cours_brvm != 0:
        ratio = round(ecart / cours_brvm * 100, 2)

    # Volatilité mois (%) = (Max mois − Min mois) / Min mois × 100
    volatilite = None
    if max_mois is not None and min_mois is not None and min_mois != 0:
        volatilite = round((max_mois - min_mois) / min_mois * 100, 2)

    rows.append({
        "Ticker":           ticker,
        "Société":          nom_societe,
        "Cours BRVM":       cours_brvm_str if cours_brvm_str else "—",
        "Min mois (SIKA)":  min_mois_str   if min_mois_str   else "—",
        "Max mois (SIKA)":  max_mois_str   if max_mois_str   else "—",
        "Écart (XOF)":      ecart          if ecart is not None else None,
        "Ratio (%)":        ratio,
        "Volatilité mois (%)": volatilite,
        "_cours_brvm_num":  cours_brvm,
        "_min_mois_num":    min_mois,
        "_max_mois_num":    max_mois,
    })

df_full = pd.DataFrame(rows)
financials_df = load_financials()

# ─── Navigation (onglets pilotables par code) ─────────────────────────────────
SORTABLE_COLUMNS = {
    "Ticker":              "Ticker",
    "Société":             "Société",
    "Cours BRVM":          "_cours_brvm_num",
    "Min mois (SIKA)":     "_min_mois_num",
    "Max mois (SIKA)":     "_max_mois_num",
    "Écart (XOF)":         "Écart (XOF)",
    "Ratio (%)":           "Ratio (%)",
    "Volatilité mois (%)": "Volatilité mois (%)",
}

nav_choice = st.segmented_control(
    "Navigation",
    options=[VIEW_GLOBAL, VIEW_SOCIETE],
    default=st.session_state.active_view,
    key=f"nav_widget_{st.session_state.active_view}",
    label_visibility="collapsed",
)
if nav_choice is not None and nav_choice != st.session_state.active_view:
    st.session_state.active_view = nav_choice
    st.rerun()

active_view = st.session_state.active_view

st.write("")


# ─── Titres de section (style commun aux deux cartes) ─────────────────────────
def _section_title_html(label, right_html=""):
    right = f"<span style='font-weight:400;'>{right_html}</span>" if right_html else ""
    return (
        "<div style='display:flex; justify-content:space-between; align-items:baseline; "
        "font-size:1rem; font-weight:700; margin-bottom:10px; "
        "padding-bottom:6px; border-bottom:2px solid rgba(255,75,75,0.4);'>"
        f"<span>{label}</span>{right}</div>"
    )


# ─── Hauteur des cartes (méthodologie / publications) ─────────────────────────
CARD_HEIGHT = 230

st.markdown(
    "<style>"
    ".st-key-meth-content { flex: 1 1 auto !important; display: flex !important; "
    "flex-direction: column !important; justify-content: center !important; }"
    "</style>",
    unsafe_allow_html=True,
)


# ─── Actualités RichBourse (publications officielles BRVM) ───────────────────
def _pub_line_html(pub):
    return (
        "<div style='font-size:0.76rem; line-height:1.35; margin-bottom:2px;'>"
        f"<b>{pub['date']}</b> — <a href='{pub['url']}' target='_blank'>{pub['titre']}</a>"
        "</div>"
    )


def render_richbourse_news():
    show_all_link = (
        f"<a href='{RICHBOURSE_INDEX_URL}' target='_blank' "
        "style='font-size:0.82rem;'>Show all →</a>"
    )
    with st.container(border=True, height=CARD_HEIGHT, key="news-card"):
        st.markdown(
            _section_title_html("📰 Dernières publications — RichBourse", show_all_link),
            unsafe_allow_html=True,
        )

        data = load_json(RICHBOURSE_FILE)
        weeks = data.get("weeks") if data else None
        if not weeks:
            st.caption("Publications indisponibles — cliquez sur *Actualiser* pour les récupérer.")
            return

        latest_week = weeks[0]
        st.caption(latest_week.get("semaine") or "Dernière semaine")

        publications = latest_week.get("publications", [])
        if publications:
            for pub in publications:
                st.markdown(_pub_line_html(pub), unsafe_allow_html=True)
        else:
            st.caption("Aucune publication cette semaine.")


# ─── Onglet 1 : Analyse globale ───────────────────────────────────────────────
def render_global_view():
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        only_matched = st.session_state.only_matched
        df_display = (
            df_full[df_full["Ratio (%)"].notna()].reset_index(drop=True)
            if only_matched else df_full.reset_index(drop=True)
        )

        valid = df_display[df_display["Ratio (%)"].notna()]
        with st.container(border=True, height=CARD_HEIGHT, key="meth-card"):
            st.markdown(_section_title_html("📐 Aperçu & méthodologie"), unsafe_allow_html=True)
            with st.container(key="meth-content"):
                col_nb, col_meth = st.columns([1, 3], vertical_alignment="center")
                with col_nb:
                    if not valid.empty:
                        st.metric("Titres analysés", len(valid))
                with col_meth:
                    st.markdown(
                        "<div style='font-size:0.72rem; line-height:1.5;'>"
                        "<b>Ratio</b> : écart entre le cours actuel coté sur la BRVM et le plus bas atteint "
                        "sur le dernier mois selon SikaFinance PRO."
                        "<br>Élevé = éloigné du plancher (reprise) ; "
                        "faible/négatif = proche du plus bas (pression vendeuse)."
                        "<br><b>Volatilité mois</b> : amplitude de la fourchette mensuelle (Max − Min) ; "
                        "plus elle est élevée, plus le titre a oscillé, donc plus le risque à court terme "
                        "est élevé."
                        "<br><b>Formules :</b> Ratio (%) = (Cours BRVM − Min mois) / Cours BRVM × 100 "
                        "&nbsp;|&nbsp; Volatilité (%) = (Max mois − Min mois) / Min mois × 100"
                        "</div>",
                        unsafe_allow_html=True,
                    )

    with col_right:
        render_richbourse_news()

    search_term = st.text_input(
        "🔎 Filtrer par ticker ou société",
        value="",
        placeholder="Ex : SNTS, SONATEL...",
        label_visibility="collapsed",
    )

    if search_term.strip():
        mask = (
            df_display["Ticker"].str.contains(search_term, case=False, na=False)
            | df_display["Société"].str.contains(search_term, case=False, na=False)
        )
        df_display = df_display[mask].reset_index(drop=True)

    sort_key_col = SORTABLE_COLUMNS.get(st.session_state.sort_column, "Ticker")
    df_display = df_display.sort_values(
        by=sort_key_col,
        ascending=st.session_state.sort_ascending,
        na_position="last",
        key=lambda s: s.str.lower() if s.dtype == "object" else s,
    ).reset_index(drop=True)

    st.caption("💡 Cliquez sur l'en-tête d'une colonne pour trier, et sur 🔍 pour ouvrir l'analyse détaillée de la société correspondante.")

    col_widths = [0.5, 0.8, 2.4, 1.1, 1.1, 1.1, 1, 1, 1.3]
    headers = [
        "", "Ticker", "Société", "Cours BRVM", "Min mois (SIKA)",
        "Max mois (SIKA)", "Écart (XOF)", "Ratio (%)", "Volatilité mois (%)",
    ]
    if df_display.empty:
        st.info("Aucun titre à afficher.")
    else:
        with st.container(border=True):
            header_cols = st.columns(col_widths, gap="small")
            for header_col, label in zip(header_cols[1:], headers[1:]):
                arrow = ""
                if st.session_state.sort_column == label:
                    arrow = " ▲" if st.session_state.sort_ascending else " ▼"
                if header_col.button(
                    f"{label}{arrow}", key=f"sort_{label}",
                    use_container_width=True, type="tertiary",
                ):
                    if st.session_state.sort_column == label:
                        st.session_state.sort_ascending = not st.session_state.sort_ascending
                    else:
                        st.session_state.sort_column = label
                        st.session_state.sort_ascending = True
                    st.rerun()

            for idx, (_, row) in enumerate(df_display.iterrows()):
                row_bg = "rgba(128,128,128,0.06)" if idx % 2 else None
                row_cols = st.columns(col_widths, gap="small", vertical_alignment="center")
                if row_cols[0].button(
                    "", icon=":material/search:", key=f"open_{row['Ticker']}",
                    help="Voir l'analyse détaillée",
                ):
                    st.session_state.selected_ticker = row["Ticker"]
                    st.session_state.active_view = VIEW_SOCIETE
                    st.rerun()
                row_cols[1].markdown(cell_html(row["Ticker"], align="left", bg=row_bg), unsafe_allow_html=True)
                row_cols[2].markdown(cell_html(row["Société"], align="left", bg=row_bg), unsafe_allow_html=True)
                row_cols[3].markdown(cell_html(row["Cours BRVM"], align="right", bg=row_bg), unsafe_allow_html=True)
                row_cols[4].markdown(cell_html(row["Min mois (SIKA)"], align="right", bg=row_bg), unsafe_allow_html=True)
                row_cols[5].markdown(cell_html(row["Max mois (SIKA)"], align="right", bg=row_bg), unsafe_allow_html=True)
                row_cols[6].markdown(cell_html(fmt_ecart(row["Écart (XOF)"]), align="right", bg=row_bg), unsafe_allow_html=True)

                ratio_val = row["Ratio (%)"]
                ratio_style = style_ratio(ratio_val) if ratio_val is not None and not pd.isna(ratio_val) else ""
                row_cols[7].markdown(
                    cell_html(fmt_ratio(ratio_val), align="right", bg=row_bg, extra_style=ratio_style),
                    unsafe_allow_html=True,
                )
                row_cols[8].markdown(
                    cell_html(fmt_volatilite(row["Volatilité mois (%)"]), align="right", bg=row_bg),
                    unsafe_allow_html=True,
                )

    # ─── Téléchargement CSV ───────────────────────────────────────────────────
    buf = io.StringIO()
    df_display.drop(columns=["_cours_brvm_num", "_min_mois_num", "_max_mois_num"]).to_csv(buf, index=False)
    col_dl, _ = st.columns([1, 3])
    with col_dl:
        st.download_button(
            label="⬇️ Télécharger en CSV",
            data=buf.getvalue(),
            file_name="analyse_brvm_sikapro.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ─── Onglet 2 : Analyse par société ───────────────────────────────────────────
def render_societe_view():
    if not all_tickers:
        st.info("Aucune société disponible.")
        return

    ticker_labels = {
        t: f"{t} — {df_full.loc[df_full['Ticker'] == t, 'Société'].iloc[0]}"
        for t in all_tickers
    }

    default_ticker = st.session_state.selected_ticker
    default_index = all_tickers.index(default_ticker) if default_ticker in all_tickers else 0

    selected = st.selectbox(
        "Société",
        options=all_tickers,
        format_func=lambda t: ticker_labels.get(t, t),
        index=default_index,
    )
    st.session_state.selected_ticker = selected

    brvm_item = brvm_index.get(selected)
    sika_item = sika_index.get(selected)
    row = df_full[df_full["Ticker"] == selected].iloc[0]

    st.markdown(f"### {row['Société']} ({selected})")
    if sika_item and sika_item.get("url"):
        st.markdown(f"[🔗 Fiche SikaFinance PRO]({sika_item['url']})")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        variation = brvm_item.get("variation") if brvm_item else None
        st.metric("Cours BRVM", row["Cours BRVM"], delta=variation)
    with col2:
        st.metric("Min mois (SIKA)", row["Min mois (SIKA)"])
    with col3:
        st.metric("Max mois (SIKA)", row["Max mois (SIKA)"])
    with col4:
        st.metric("Ratio (%)", fmt_ratio(row["Ratio (%)"]))

    col5, col6 = st.columns(2)
    with col5:
        st.metric("Écart (XOF)", fmt_ecart(row["Écart (XOF)"]))
    with col6:
        st.metric("Volatilité mois (%)", fmt_volatilite(row["Volatilité mois (%)"]))

    ratio_val = row["Ratio (%)"]
    if ratio_val is not None and not pd.isna(ratio_val) and ratio_val <= 5:
        st.error("⚠️ Ratio ≤ 5% — le titre est proche de son plancher mensuel (pression vendeuse potentielle).")

    if brvm_item is None:
        st.warning("Titre absent de la source BRVM.")
    if sika_item is None:
        st.warning("Titre absent de la source SIKAPRO.")

    st.divider()
    st.markdown("#### 📈 Évolution trimestrielle (FY23 → FY26, en mFCFA)")

    company_fin = financials_df[financials_df["Ticker"] == selected].copy()

    if company_fin.empty:
        st.info("Aucune donnée financière trimestrielle pour cette société dans BRVM_long.xlsx.")
    else:
        available_fy = [fy for fy in FY_ORDER if fy in company_fin["FY"].unique()]
        available_q = [q for q in QUARTER_ORDER if q in company_fin["Trimestre"].unique()]

        col_metric, col_type = st.columns(2)
        with col_metric:
            metric_choice = st.multiselect(
                "Indicateurs", options=list(METRICS.keys()), default=["CA", "RN"], key=f"metric_{selected}",
            )
        with col_type:
            chart_type = st.radio(
                "Type de graphique", ["Barres groupées", "Lignes", "Barres empilées"],
                horizontal=True, key=f"charttype_{selected}",
                help="Barres groupées / Lignes : comparent un même trimestre d'une année à l'autre. "
                     "Barres empilées : somment les 4 trimestres (à éviter ici, Q1=Q2 et Q3=Q4 "
                     "étant des valeurs semestrielles dupliquées, la somme double le total réel).",
            )

        col_fy, col_q = st.columns(2)
        with col_fy:
            fy_selected = st.multiselect(
                "Exercices (FY)", options=available_fy, default=available_fy, key=f"fy_{selected}",
            )
        with col_q:
            q_selected = st.multiselect(
                "Trimestres", options=available_q, default=available_q, key=f"q_{selected}",
            )

        filtered = company_fin[
            company_fin["FY"].isin(fy_selected) & company_fin["Trimestre"].isin(q_selected)
        ]

        def build_pivot(value_col):
            if filtered.empty:
                return pd.DataFrame()
            pivot = filtered.pivot_table(index="Trimestre", columns="FY", values=value_col, aggfunc="sum")
            pivot = pivot.reindex(index=[q for q in QUARTER_ORDER if q in pivot.index])
            pivot = pivot.reindex(columns=[fy for fy in FY_ORDER if fy in pivot.columns])
            return pivot.fillna(0)

        def render_chart(pivot, label):
            if pivot.empty or pivot.to_numpy().sum() == 0:
                st.info(f"Pas de données {label} pour cette sélection.")
                return
            long_df = pivot.reset_index().melt(id_vars="Trimestre", var_name="FY", value_name="valeur")
            x_axis = alt.X("Trimestre:N", sort=QUARTER_ORDER, axis=alt.Axis(labelAngle=0), title=None)
            color = alt.Color("FY:N", sort=FY_ORDER, title="FY")
            if chart_type == "Lignes":
                chart = alt.Chart(long_df).mark_line(point=True).encode(
                    x=x_axis, y=alt.Y("valeur:Q", title=None), color=color,
                )
            elif chart_type == "Barres empilées":
                chart = alt.Chart(long_df).mark_bar().encode(
                    x=x_axis, y=alt.Y("valeur:Q", title=None), color=color,
                )
            else:
                chart = alt.Chart(long_df).mark_bar().encode(
                    x=x_axis,
                    xOffset=alt.XOffset("FY:N", sort=FY_ORDER),
                    y=alt.Y("valeur:Q", title=None),
                    color=color,
                )
            st.altair_chart(chart.properties(height=320), use_container_width=True)

        if not metric_choice:
            st.info("Sélectionnez au moins un indicateur.")
        else:
            chart_cols = st.columns(2)
            for i, metric_name in enumerate(metric_choice):
                value_col, caption = METRICS[metric_name]
                with chart_cols[i % 2]:
                    st.caption(caption)
                    render_chart(build_pivot(value_col), metric_name)

    if st.button("⬅️ Retour à l'analyse globale"):
        st.session_state.active_view = VIEW_GLOBAL
        st.rerun()


if active_view == VIEW_SOCIETE:
    render_societe_view()
else:
    render_global_view()
