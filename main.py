import time
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO: DIÁRIO OFICIAL (IOSE) ---
def realizar_scraping_iose():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    resultados = []
    try:
        url_busca = "https://iose.se.gov.br/buscanova/#/p=1&q=ITPS"
        driver.get(url_busca)
        time.sleep(15) 
        texto_pagina = driver.find_element("tag name", "body").text
        linhas = texto_pagina.split('\n')
        for linha in linhas:
            if "Diário publicado em:" in linha:
                partes = linha.split(" - ")
                data_pub = partes[0].replace("Diário publicado em:", "").strip()
                titulo_pub = " - ".join(partes[1:])
                resultados.append({"data": data_pub, "titulo": titulo_pub, "link": url_busca})
    except Exception as e:
        print(f"Erro Scraper: {e}")
    finally:
        driver.quit()
    return resultados[:10]

# --- ROTAS DINÂMICAS ---

@app.get("/api/diario-oficial")
async def get_diario():
    return {"resultado": realizar_scraping_iose()}

@app.get("/api/licitacoes")
async def get_licitacoes():
    """Consulta PNCP: Busca automática dos últimos 30 dias para o ITPS"""
    cnpj_itps = "07258529000159"
    hoje = datetime.now()
    inicio = (hoje - timedelta(days=30)).strftime("%Y%m%d")
    fim = hoje.strftime("%Y%m%d")
    
    # Endpoint oficial de consulta por data de publicação
    url = f"https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial={inicio}&dataFinal={fim}&cnpj={cnpj_itps}&pagina=1&tamanhoPagina=10"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            dados = response.json().get('data', [])
            return {"resultado": [{
                "orgao": item['orgaoEntidade']['razaoSocial'],
                "objeto": item['objetoCompra'],
                "valor": item['valorTotalEstimado']
            } for item in dados]}
    except: pass
    return {"resultado": []}

@app.get("/api/materiais")
async def get_materiais(termo: str = Query(...)):
    """API Compras.gov.br: Consulta real ao catálogo SIASG (CATMAT)"""
    # Endpoint oficial para pesquisa por descrição
    url = f"https://compras.dados.gov.br/materiais/v1/materiais.json?descricao={termo}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            materiais = response.json().get("_embedded", {}).get("materiais", [])
            return {"resultado": [{"codigoItem": m["codigo"], "descricaoItem": m["descricao"]} for m in materiais]}
    except: pass
    return {"resultado": []}

@app.get("/api/falabr/manifestacoes")
async def get_falabr():
    """Estrutura oficial Fala.BR (OAuth 2.0)"""
    # URL para Token: https://falabr.cgu.gov.br/oauth/token
    # Exige: grant_type=password, client_id, client_secret, username e password
    return {"resultado": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)