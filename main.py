from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

URL_BASE_COMPRAS = "https://dadosabertos.compras.gov.br"
HEADERS_PADRAO = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

# --- SISTEMA DE CACHE EM MEMÓRIA ---
# Guarda os últimos resultados válidos para salvar o dia se o governo cair
cache_dados = {}

async def fetch_governo_com_cache(endpoint: str, params: dict, cache_key: str):
    url = f"{URL_BASE_COMPRAS}{endpoint}"
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, params=params, headers=HEADERS_PADRAO)
            response.raise_for_status()
            dados = response.json()
            
            # Se deu certo, salva no cache com a data e hora atual
            cache_dados[cache_key] = {
                "dados": dados,
                "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
            }
            return {"sucesso": True, "cache": False, "resultado": dados["resultado"]}
            
        except Exception as e:
            print(f"[X] Falha na API do Governo: {e}")
            
            # Se falhou, tenta resgatar do CACHE!
            if cache_key in cache_dados:
                print(f"[!] Governo caiu. Retornando CACHE de {cache_key}")
                return {
                    "sucesso": True, 
                    "cache": True, # Avisa o Front-End que é um dado antigo
                    "ultima_atualizacao": cache_dados[cache_key]["ultima_atualizacao"],
                    "resultado": cache_dados[cache_key]["dados"]["resultado"]
                }
            
            # Se falhou e não tem cache...
            return JSONResponse(
                status_code=500, 
                content={"erro_interno": "Governo fora do ar e nenhum dado salvo no cache ainda."}
            )

@app.get("/api/materiais")
async def buscar_materiais(termo: str):
    endpoint = "/modulo-material/4_consultarItemMaterial"
    parametros = {"pagina": 1, "tamanhoPagina": 10, "descricaoItem": termo}
    # A chave do cache é a própria palavra procurada
    return await fetch_governo_com_cache(endpoint, parametros, f"catmat_{termo}")

@app.get("/api/licitacoes")
async def buscar_licitacoes(data_inicio: str, data_fim: str):
    endpoint = "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133"
    parametros = {
        "pagina": 1, "tamanhoPagina": 10, "unidadeOrgaoUfSigla": "SE",
        "codigoModalidade": 5, "dataPublicacaoPncpInicial": data_inicio,
        "dataPublicacaoPncpFinal": data_fim
    }
    return await fetch_governo_com_cache(endpoint, parametros, "licitacoes_se")

# --- ROTA DO RASPADOR DO DIÁRIO OFICIAL ---
@app.get("/api/diario-oficial")
async def raspar_diario_oficial():
    # AQUI ENTRARÁ O SEU CÓDIGO EM PYTHON (BEAUTIFULSOUP)
    # Por enquanto, usamos dados de teste para validar a interface:
    try:
        noticias_itps = [
            {"data": datetime.now().strftime("%d/%m/%Y"), "titulo": "Nomeação de Estagiários - ITPS", "link": "#"},
            {"data": "Ontem", "titulo": "Aviso de Licitação - Manutenção de Equipamentos ITPS", "link": "#"}
        ]
        return {"sucesso": True, "resultado": noticias_itps}
    except Exception as e:
        return JSONResponse(status_code=500, content={"erro_interno": f"Falha no raspador: {e}"})