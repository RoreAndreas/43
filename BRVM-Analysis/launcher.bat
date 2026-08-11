@echo off
cd /d "%~dp0"
call "c:\Users\Alexandre.kakou\Documents\Python project\.venv\Scripts\activate.bat"
echo Lancement de l'analyse BRVM x SikaFinance PRO...
streamlit run app.py
pause
