import os
import time
import requests
import urllib3
import re
import html 
from datetime import datetime

# Desativa os avisos vermelhos de SSL no terminal gerados pelo Proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- CONFIGURAÇÃO DE PROXY DO ITPS ---
# Login genérico de serviço (Auditório) para a API acessar a internet
proxy_url = "http://auditorio.itps:auditorio2023@proxy.itps.gov-se:8080"

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

# --- VARIÁVEIS DE CACHE GLOBAL ---
cache_iose = {"dados": [], "ultima_atualizacao": 0}
TEMPO_CACHE = 3600  # O robô do Selenium só roda 1 vez por hora (3600 segundos)

# --- SCRAPING: DIÁRIO OFICIAL (IOSE) ---
def realizar_scraping_iose():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    resultados = []
    
    # Filtro automático pelo mês e ano atuais
    agora = datetime.now()
    mes_atual = f"{agora.month:02d}"
    ano_atual = str(agora.year)
    filtro_data = f"/{mes_atual}/{ano_atual}" 
    
    try:
        url_busca = "https://iose.se.gov.br/buscanova/#/p=1&q=ITPS"
        driver.get(url_busca)
        time.sleep(15) # Espera o site do governo carregar
        
        # TÁTICA NOVA: Achar os links (botões) primeiro
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'ver-flip')]")
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if not href: continue
                
                # Sobe na estrutura do site (até 5 níveis) para encontrar a "caixa" que envolve o botão e o texto
                container = link
                texto_caixa = ""
                for _ in range(5):
                    container = container.find_element(By.XPATH, "..")
                    if "Diário publicado em:" in container.text:
                        texto_caixa = container.text
                        break
                
                if texto_caixa:
                    # Achou a caixa! Agora pega a linha exata da data
                    linhas = texto_caixa.split('\n')
                    for linha in linhas:
                        if "Diário publicado em:" in linha:
                            partes = linha.split(" - ")
                            data_pub = partes[0].replace("Diário publicado em:", "").strip()
                            
                            # Verifica se é do mês atual (Filtro)
                            if data_pub.endswith(filtro_data):
                                titulo_pub = " - ".join(partes[1:])
                                
                                # A sua ideia: Adiciona o ?find=ITPS para já cair grifado no PDF
                                link_direto = href
                                if "?find=" not in link_direto:
                                    link_direto = f"{link_direto}?find=ITPS"
                                    
                                # Evita itens duplicados (caso o site tenha 2 botões iguais pro mesmo diário)
                                if not any(r['link'] == link_direto for r in resultados):
                                    resultados.append({"data": data_pub, "titulo": titulo_pub, "link": link_direto})
                            break # Já achou a data nesta caixa, pula pro próximo botão
            except Exception:
                # Se um botão específico der erro, ignora e vai pro próximo sem travar o código
                continue
                    
    except Exception as e:
        print(f"Erro Scraper IOSE: {e}")
    finally:
        driver.quit()
        
    return resultados[:10]

@app.get("/api/diario-oficial")
async def get_diario():
    agora = time.time()
    
    # Se temos dados guardados e passou menos de 1 hora, devolve o Cache instantaneamente
    if cache_iose["dados"] and (agora - cache_iose["ultima_atualizacao"] < TEMPO_CACHE):
        print("Entregando Diário Oficial direto da memória (CACHE) - Super rápido!")
        return {"resultado": cache_iose["dados"]}
        
    # Se o cache estiver vazio ou velho, inicia o robô pesado
    print("Iniciando o Robô Chrome para ler o Diário Oficial...")
    resultados = realizar_scraping_iose()
    
    # Atualiza a memória com os dados novos para os próximos usuários
    if resultados: 
        cache_iose["dados"] = resultados
        cache_iose["ultima_atualizacao"] = agora
        
    return {"resultado": resultados}


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
                
                # Visita a página da notícia e pega a foto de capa (og:image)
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
    # AVISO PARA TI: O host 0.0.0.0 permite que o servidor seja acessado por outras máquinas na rede local
    uvicorn.run(app, host="0.0.0.0", port=8000)