import time
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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
        time.sleep(15) # Aguarda o carregamento dinâmico conforme solicitado
        
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
        print(f"Erro no Scraper IOSE: {e}")
    finally:
        driver.quit()
    return resultados[:6]

# --- ROTAS DA API ---

@app.get("/api/diario-oficial")
async def get_diario():
    return {"resultado": realizar_scraping_iose()}

@app.get("/api/licitacoes")
async def get_licitacoes(data_inicio: str, data_fim: str):
    """Consulta real ao PNCP usando o CNPJ do ITPS"""
    cnpj_itps = "07258529000159"
    url = f"https://pncp.gov.br/api/pncp/v1/contratacoes?dataInicial={data_inicio.replace('-','')}&dataFinal={data_fim.replace('-','')}&cnpjRespondente={cnpj_itps}&pagina=1&tamanhoPagina=10"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            # Formata os dados para o front-end
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

@app.get("/api/falabr/manifestacoes")
async def get_falabr():
    """Estrutura para Fala.BR com OAuth2"""
    # Nota: Substitua pelas suas credenciais reais para obter o token
    # url_token = "https://falabr.cgu.gov.br/oauth/token"
    return {"resultado": []}

@app.get("/api/materiais")
async def get_materiais(termo: str = Query(...)):
    return {"resultado": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)