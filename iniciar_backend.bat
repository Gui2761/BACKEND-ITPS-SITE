@echo off
title Backend ITPS - FastAPI
:: IMPORTANTE: Se voce mudar esta pasta de lugar, altere o caminho abaixo!
cd /d "C:\Users\gnsilva\BACKEND-ITPS-SITE"
echo Iniciando o Servidor Backend...
call venv\Scripts\activate
python main.py
pause
