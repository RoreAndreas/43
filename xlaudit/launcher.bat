@echo off
REM ===============================================
REM Lanceur de l'interface xlaudit
REM Audit de modeles financiers Excel
REM ===============================================

echo.
echo ========================================
echo   LANCEMENT DE XLAUDIT
echo ========================================
echo.

REM Se positionner dans le dossier du script
cd /d "%~dp0"

set "VENV=c:\Users\Alexandre.kakou\Documents\Python project\.venv"
set "PY=%VENV%\Scripts\python.exe"

REM Verifier que l'environnement virtuel existe
if not exist "%PY%" (
    echo ERREUR: environnement virtuel introuvable
    echo   attendu : %PY%
    echo.
    echo Creez-le depuis "Python project" avec :
    echo   python -m venv .venv
    echo.
    pause
    exit /b 1
)

call "%VENV%\Scripts\activate.bat"

REM Verifier que les dependances de l'interface sont presentes.
REM Au premier lancement elles manquent : on les installe sans rien demander.
"%PY%" -c "import streamlit, pandas, xlaudit" >nul 2>&1
if errorlevel 1 (
    echo Premier lancement : installation des dependances...
    echo Cette operation peut prendre quelques minutes.
    echo.
    "%PY%" -m pip install -e ".[ui]"
    if errorlevel 1 (
        echo.
        echo ERREUR: installation des dependances impossible
        echo Verifiez votre connexion reseau, puis relancez.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Installation terminee.
    echo.
)

REM --server.address localhost : l'interface reste sur cette machine.
REM Sans cette option Streamlit ecoute sur toutes les interfaces reseau et
REM publie une URL externe, ce qui exposerait le modele financier depose.
echo Demarrage de l'interface...
echo   L'application s'ouvre dans votre navigateur : http://localhost:8501
echo   Deposez le classeur dans la barre laterale.
echo.
echo   Pour arreter : fermez cette fenetre ou faites Ctrl+C.
echo.

"%PY%" -m streamlit run app.py --server.address localhost --browser.gatherUsageStats false

if errorlevel 1 (
    echo.
    echo ERREUR: l'interface s'est arretee de facon anormale
    echo.
    pause
    exit /b 1
)

echo.
pause
