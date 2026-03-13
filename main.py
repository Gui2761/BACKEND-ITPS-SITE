from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime
from bs4 import BeautifulSoup

app = FastAPI()

# Permite que o Frontend no navegador comunique com este Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS_PADRAO = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Sistema de Cache em Memória
cache_dados = {}

async def fetch_governo_com_cache(url: str, params: dict, cache_key: str, is_pncp=False):
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, params=params, headers=HEADERS_PADRAO)
            response.raise_for_status()
            dados = response.json()
            
            # A API do PNCP devolve os itens na chave "data", enquanto o Compras.gov usa "resultado"
            resultado_final = dados.get("data") if is_pncp else dados.get("resultado", dados)

            # Guarda os dados em cache em caso de queda futura
            cache_dados[cache_key] = {
                "dados": resultado_final,
                "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
            }
            return {"sucesso": True, "cache": False, "resultado": resultado_final}
            
        except Exception as e:
            print(f"[X] Falha na API governamental: {e}")
            
            # Tenta resgatar do CACHE
            if cache_key in cache_dados:
                print(f"[!] A usar o CACHE de emergência para {cache_key}")
                return {
                    "sucesso": True, 
                    "cache": True,
                    "ultima_atualizacao": cache_dados[cache_key]["ultima_atualizacao"],
                    "resultado": cache_dados[cache_key]["dados"]
                }
            
            return JSONResponse(
                status_code=500, 
                content={"erro_interno": f"Serviço fora do ar e sem cache: {str(e)}"}
            )

@app.get("/api/materiais")
async def buscar_materiais(termo: str):
    url = "https://dadosabertos.compras.gov.br/modulo-material/4_consultarItemMaterial"
    parametros = {"pagina": 1, "tamanhoPagina": 10, "descricaoItem": termo}
    return await fetch_governo_com_cache(url, parametros, f"catmat_{termo}")

@app.get("/api/licitacoes")
async def buscar_licitacoes(data_inicio: str, data_fim: str):
    # A usar o endpoint correto do PNCP
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    
    # O PNCP exige que as datas não tenham traços (YYYYMMDD)
    data_ini_formata = data_inicio.replace("-", "")
    data_fim_formata = data_fim.replace("-", "")

    parametros = {
        "dataInicial": data_ini_formata,
        "dataFinal": data_fim_formata,
        "uf": "SE",
        "tamanhoPagina": 10
    }
    return await fetch_governo_com_cache(url, parametros, "licitacoes_se", is_pncp=True)

@app.get("/api/diario-oficial")
async def raspar_diario_oficial():
    try:
        # Raspador com BeautifulSoup para alimentar o portal
        url_noticias = "https://itps.se.gov.br/feed/"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url_noticias)
            
            # features="xml" porque estamos a ler um feed estruturado
            soup = BeautifulSoup(response.content, features="xml")
            
            noticias_itps = []
            # Apanha apenas os 5 resultados mais recentes
            items = soup.find_all("item", limit=5)
            
            for item in items:
                data_pub = item.pubDate.text if item.pubDate else datetime.now().strftime("%d/%m/%Y")
                
                noticias_itps.append({
                    "data": data_pub[:16], # Recorta o fuso horário da string
                    "titulo": item.title.text, 
                    "link": item.link.text
                })

        return {"sucesso": True, "resultado": noticias_itps}
    except Exception as e:
        return JSONResponse(status_code=500, content={"erro_interno": f"Falha no raspador: {e}"})