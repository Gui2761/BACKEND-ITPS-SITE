from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# Configuração do CORS: Permite que o seu Front-End (Intranet) acesse este Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, coloque o IP/Domínio da Intranet do ITPS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

URL_BASE_COMPRAS = "https://dadosabertos.compras.gov.br"

@app.get("/api/materiais")
async def buscar_materiais(termo: str):
    url = f"{URL_BASE_COMPRAS}/modulo-material/4_consultarItemMaterial?pagina=1&tamanhoPagina=5&descricaoItem={termo}"
    
    # Faz a requisição servidor-servidor (CORS não existe aqui)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

@app.get("/api/licitacoes")
async def buscar_licitacoes(data_inicio: str, data_fim: str):
    url = f"{URL_BASE_COMPRAS}/modulo-contratacoes/1_consultarContratacoes_PNCP_14133?pagina=1&tamanhoPagina=4&unidadeOrgaoUfSigla=SE&codigoModalidade=5&dataPublicacaoPncpInicial={data_inicio}&dataPublicacaoPncpFinal={data_fim}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()