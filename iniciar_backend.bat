@echo off
title Backend ITPS - FastAPI
:: IMPORTANTE: Se voce mudar esta pasta de lugar, altere o caminho abaixo!
cd /d "C:\Users\gnsilva\BACKEND-ITPS-SITE"
echo Iniciando o Servidor Backend...
:: Se voce usa venv, descomente a linha abaixo (troque 'venv' pelo nome da sua pasta)
:: call venv\Scripts\activate
python main.py
pause
