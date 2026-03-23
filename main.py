import time
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

# --- CONFIGURAÇÃO ESPECÍFICA: IOSE (DIÁRIO OFICIAL) ---
def realizar_scraping_iose():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    resultados = []
    try:
        # A URL já contém o filtro 'q=ITPS' para busca exata
        url_busca = "https://iose.se.gov.br/buscanova/#/p=1&q=ITPS"
        driver.get(url_busca)
        time.sleep(15) # O site do IOSE é pesado e precisa de tempo para o Angular carregar
        
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
        print(f"Erro no Scraper: {e}")
    finally:
        driver.quit()
    return resultados

# --- ROTAS SEM DADOS PRESOS ---

@app.get("/api/diario-oficial")
async def get_diario():
    return {"resultado": realizar_scraping_iose()}

@app.get("/api/falabr/manifestacoes")
async def get_falabr():
    # Aqui deve entrar a chamada requests.get com o Header 'Authorization: Bearer TOKEN'
    # conforme a documentação do Fala.BR
    return {"resultado": []} 

@app.get("/api/licitacoes")
async def get_licitacoes(data_inicio: str, data_fim: str):
    # CNPJ do ITPS: 07258529000159
    # Recomendado usar a API do PNCP: https://pncp.gov.br/api/pncp/v1/contratacoes/...
    return {"resultado": []}

@app.get("/api/materiais")
async def get_materiais(termo: str = Query(...)):
    # Esta rota deve consultar o teu banco de dados ou API do Compras.gov.br
    return {"resultado": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)