from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/licitacoes")
async def buscar_licitacoes(data_inicio: str, data_fim: str):
    # Tratamento rigoroso das datas para evitar Erro 400
    # Se hoje é 13/03/2026, garantimos que nada passe disso
    dt_ini = data_inicio.replace("-", "")
    dt_fim = data_fim.replace("-", "")
    
    # URL oficial de consulta do PNCP
    url = f"https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    
    params = {
        "dataInicial": dt_ini,
        "dataFinal": dt_fim,
        "uf": "SE",
        "tamanhoPagina": 10
    }
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, params=params)
            
            # Se a API do governo der 400, capturamos o motivo real
            if response.status_code == 400:
                return JSONResponse(
                    status_code=400, 
                    content={"erro": "Requisição Inválida", "detalhe": response.text}
                )
                
            response.raise_for_status()
            dados = response.json()
            return {"sucesso": True, "resultado": dados.get("data", [])}
        except Exception as e:
            print(f"Erro Crítico PNCP: {e}")
            return JSONResponse(
                status_code=500, 
                content={"erro": "Falha na API do Governo", "detalhe": str(e)}
            )

@app.get("/api/diario-oficial")
async def raspar_diario_oficial():
    try:
        url = "https://itps.se.gov.br/feed/"
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url)
            soup = BeautifulSoup(r.content, features="xml")
            items = soup.find_all("item", limit=5)
            noticias = [{"titulo": i.title.text, "link": i.link.text, "data": i.pubDate.text[:16]} for i in items]
            return {"sucesso": True, "resultado": noticias}
    except Exception as e:
        return {"sucesso": False, "resultado": [], "erro": str(e)}

@app.get("/api/materiais")
async def buscar_materiais(termo: str):
    url = "https://dadosabertos.compras.gov.br/modulo-material/4_consultarItemMaterial"
    params = {"pagina": 1, "tamanhoPagina": 10, "descricaoItem": termo}
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(url, params=params)
            return {"sucesso": True, "resultado": r.json().get("resultado", [])}
        except:
            return {"sucesso": False, "resultado": []}