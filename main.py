import os
import time
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# --- CONFIGURAÇÃO DE PROXY DO ITPS ---
# A senha 'S@ndes2026++' está convertida para 'S%40ndes2026%2B%2B' para funcionar na URL
proxy_url = "http://itamar.sandes:S%40ndes2026%2B%2B@proxy.itps.gov-se:8080"

os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
os.environ['http_proxy'] = proxy_url
os.environ['https_proxy'] = proxy_url

app = FastAPI()

# Configuração de CORS para permitir que o seu site (Frontend) aceda à API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SCRAPING: DIÁRIO OFICIAL (IOSE) ---
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
        print(f"Erro Scraper IOSE: {e}")
    finally:
        driver.quit()
    return resultados[:10]

# --- ROTAS DA API ---

@app.get("/api/diario-oficial")
async def get_diario():
    return {"resultado": realizar_scraping_iose()}

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import time

import time
from selenium.webdriver.common.by import By

@app.get("/api/licitacoes")
async def get_licitacoes():
    """Captura Atas buscando pelos elementos corretos (links <a>)"""
    options = Options()
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.minimize_window() 
    
    resultados = []
    
    try:
        url_atas = "https://www.pncp.gov.br/app/atas?q=itps&status=vigente&pagina=1"
        print("1. Acessando PNCP...")
        driver.get(url_atas)
        
        print("2. Aguardando 15 segundos para renderização...")
        time.sleep(15)
        
        # O SEGREDO ESTÁ AQUI: Buscar por tags <a> (links), que é como o PNCP estrutura a lista de Atas
        elementos = driver.find_elements(By.TAG_NAME, "a")
        print(f"3. Varrendo {len(elementos)} links na página...")
        
        for index, el in enumerate(elementos):
            texto = el.text
            
            # Condição para achar o bloco da Ata
            if "Id ata PNCP:" in texto or "Extrator" in texto or "ESTADO DE SERGIPE" in texto:
                print("   [!] Ata verdadeira encontrada!")
                linhas = texto.split('\n')
                
                # Pegamos o link real já pronto direto do HTML!
                link_direto = el.get_attribute("href")
                if not link_direto:
                    link_direto = url_atas

                # Evita pegar linhas vazias como título
                titulo = linhas[0] if len(linhas) > 0 and linhas[0].strip() != "" else "Ata de Registro de Preços"

                resultados.append({
                    "orgao": "ITPS / SERGIPE",
                    "objeto": titulo,
                    "valor": 0,
                    "link": link_direto
                })
                
        print(f"4. Processamento concluído. {len(resultados)} atas extraídas.")
        
    except Exception as e:
        print(f"ERRO NO SCRAPING: {str(e)}")
    finally:
        driver.quit()
        
    # Limpa duplicatas (às vezes o site renderiza o mesmo link 2x em telas grandes)
    resultados_unicos = []
    links_vistos = set()
    for r in resultados:
        if r["link"] not in links_vistos:
            resultados_unicos.append(r)
            links_vistos.add(r["link"])
            
    return {"resultado": resultados_unicos}

@app.get("/api/materiais")
async def get_materiais(termo: str = Query(...)):
    """Consulta o catálogo oficial CATMAT (SIASG)"""
    url = f"https://compras.dados.gov.br/materiais/v1/materiais.json?descricao={termo}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            materiais = response.json().get("_embedded", {}).get("materiais", [])
            return {"resultado": [{
                "codigoItem": m.get("codigo"),
                "descricaoItem": m.get("descricao")
            } for m in materiais]}
    except: pass
    return {"resultado": []}

@app.get("/api/falabr/manifestacoes")
async def get_falabr():
    """Esqueleto para integração futura com Fala.BR"""
    return {"resultado": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)