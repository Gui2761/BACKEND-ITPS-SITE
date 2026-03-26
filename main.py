import os
import time
import requests
import urllib3
import re
import html 
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- CONFIGURAÇÃO DE PROXY DO ITPS ---
proxy_url = "http://itamar.sandes:S%40ndes2026%2B%2B@proxy.itps.gov-se:8080"

os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
os.environ['http_proxy'] = proxy_url
os.environ['https_proxy'] = proxy_url
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1,itps.se.gov.br'
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1,itps.se.gov.br'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SCRAPING: DIÁRIO OFICIAL (IOSE) ---
def realizar_scraping_iose():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    resultados = []
    try:
        url_busca = "https://iose.se.gov.br/buscanova/#/p=1&q=ITPS"
        driver.get(url_busca)
        time.sleep(15) 
        texto_pagina = driver.find_element(By.TAG_NAME, "body").text
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

@app.get("/api/diario-oficial")
async def get_diario():
    return {"resultado": realizar_scraping_iose()}


# --- API: NOTÍCIAS DO ITPS (TRUQUE DO OPENGRAPH) ---
@app.get("/api/noticias")
async def get_noticias():
    url = "https://itps.se.gov.br/feed/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
            xml = response.text
            
            if "<item>" not in xml: 
                return {"resultado": []}
                
            itens = xml.split("<item>")[1:4] 
            resultados = []
            
            for item in itens:
                item_limpo = html.unescape(item)
                
                titulo = "Sem Título"
                match_t = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_limpo) or re.search(r'<title>(.*?)</title>', item_limpo)
                if match_t: titulo = match_t.group(1).strip()
                
                link = "#"
                match_l = re.search(r'<link>(.*?)</link>', item_limpo)
                if match_l: link = match_l.group(1).strip()
                
                imagem_url = "images/Itps.png"
                if link.startswith("http"):
                    try:
                        req_noticia = requests.get(link, headers=headers, timeout=5, verify=False)
                        match_og = re.search(r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\'](https?://[^"\'>]+)["\']', req_noticia.text, re.IGNORECASE)
                        if not match_og: 
                            match_og = re.search(r'<meta\s+content=["\'](https?://[^"\'>]+)["\']\s+(?:property|name)=["\']og:image["\']', req_noticia.text, re.IGNORECASE)
                            
                        if match_og:
                            imagem_url = match_og.group(1)
                    except:
                        pass
                
                data_formatada = ""
                match_d = re.search(r'<pubDate>(.*?)</pubDate>', item_limpo)
                if match_d:
                    try:
                        partes = match_d.group(1).strip().split(' ')
                        if len(partes) >= 4:
                            dia = partes[1]
                            mes_ing = partes[2].lower()
                            ano = partes[3]
                            mapa_meses = {'jan': 'janeiro', 'feb': 'fevereiro', 'mar': 'março', 'apr': 'abril', 'may': 'maio', 'jun': 'junho', 'jul': 'julho', 'aug': 'agosto', 'sep': 'setembro', 'oct': 'outubro', 'nov': 'novembro', 'dec': 'dezembro'}
                            mes_pt = mapa_meses.get(mes_ing, mes_ing)
                            data_formatada = f"{dia} de {mes_pt} de {ano}"
                    except:
                        data_formatada = match_d.group(1)
                        
                resultados.append({
                    "titulo": titulo, "link": link, "imagem": imagem_url, "data": data_formatada
                })
                
            return {"resultado": resultados}
            
    except Exception as e:
        print(f"ERRO AO LER NOTÍCIAS: {str(e)}")
        
    return {"resultado": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)