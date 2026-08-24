#!/bin/bash
# ========================================================
# SCRIPT DE ATUALIZACAO COMPLETA (FRONTEND + BACKEND + DOCKER)
# Instituto de Tecnologia e Pesquisa de Sergipe - ITPS
# ========================================================

echo "========================================================"
echo "  ATUALIZANDO SISTEMA ITPS (FRONTEND & BACKEND)         "
echo "========================================================"
echo ""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# 1. Puxar atualizacoes do GitHub
echo "[1/4] Puxando atualizacoes do GitHub..."
git pull origin main

# 2. Atualizar Frontend na pasta do Apache (/var/www/html)
echo "[2/4] Atualizando arquivos do Frontend em /var/www/html..."
if [ -d "recadastramento" ]; then
    sudo cp -r recadastramento /var/www/html/
fi
sudo chown -R www-data:www-data /var/www/html
sudo chmod -R 755 /var/www/html

# 3. Reconstruir e reiniciar container Docker do Backend
echo "[3/4] Reconstruindo e reiniciando conteiner Docker do Backend..."
sudo docker-compose build --no-cache
sudo docker rm -f backend-itps 2>/dev/null || true
sudo docker run -d --name backend-itps -p 8000:8000 --restart unless-stopped     -v "//172.23.6.7/ageplan/Banco de contratos:/app/db_contratos"     -v "//172.23.6.7/gerh/1- COAPE/FolhaITPS_Dados:/app/db_folha"     backintra_backend-itps:latest

# 4. Finalizacao
echo ""
echo "========================================================"
echo "  SISTEMA ATUALIZADO COM SUCESSO!                       "
echo "========================================================"
echo "Frontend Intranet: http://intranet.itps.net/ ou http://172.23.6.109/"
echo "Backend FastAPI:   http://172.23.6.109:8000/"
echo "Painel Admin RH:   http://intranet.itps.net/recadastramento/admin/"
echo "========================================================"
