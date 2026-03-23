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

# --- SCRAPER: DIÁRIO OFICIAL (IOSE) ---
def realizar_scraping_iose():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    resultados = []
    try:
        # Busca exata por ITPS ordenada por data no site
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
                
                resultados.append({
                    "data": data_pub,
                    "titulo": titulo_pub,
                    "link": url_busca
                })
    except Exception as e:
        print(f"Erro IOSE: {e}")
    finally:
        driver.quit()
    return resultados[:10] # Retorna os 10 mais recentes

# --- ROTAS ---

@app.get("/api/diario-oficial")
async def get_diario():
    return {"resultado": realizar_scraping_iose()}

@app.get("/api/licitacoes")
async def get_licitacoes(data_inicio: str = None, data_fim: str = None):
    """Busca automática dos últimos 30 dias no PNCP para o ITPS"""
    cnpj_itps = "07258529000159"
    
    # Se não vier data, calcula os últimos 30 dias automaticamente
    if not data_inicio or not data_fim:
        hoje = datetime.now()
        inicio_dt = hoje - timedelta(days=30)
        data_inicio = inicio_dt.strftime("%Y%m%d")
        data_fim = hoje.strftime("%Y%m%d")
    else:
        data_inicio = data_inicio.replace("-", "")
        data_fim = data_fim.replace("-", "")

    url = f"https://pncp.gov.br/api/pncp/v1/contratacoes?dataInicial={data_inicio}&dataFinal={data_fim}&cnpjRespondente={cnpj_itps}&pagina=1&tamanhoPagina=10"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            dados = response.json()
            processados = []
            for item in dados.get('data', []):
                processados.append({
                    "orgaoEntidade": {"razaoSocial": item.get('orgaoEntidade', {}).get('razaoSocial', 'ITPS')},
                    "objetoCompra": item.get('objetoCompra', 'Sem descrição'),
                    "valorTotalEstimado": item.get('valorTotalEstimado', 0)
                })
            return {"resultado": processados}
    except Exception as e:
        print(f"Erro PNCP: {e}")
    return {"resultado": []}

@app.get("/api/materiais")
async def get_materiais(termo: str = Query(...)):
    """Consulta real ao catálogo federal SIASG"""
    url = f"https://compras.dados.gov.br/materiais/v1/materiais.json?descricao={termo}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            materiais = resp.json().get("_embedded", {}).get("materiais", [])
            return {"resultado": [{"codigoItem": m["codigo"], "descricaoItem": m["descricao"]} for m in materiais]}
    except: pass
    return {"resultado": []}

@app.get("/api/falabr/manifestacoes")
async def get_falabr():
    return {"resultado": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)