from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import core.config  # Importa para aplicar as configurações globais de proxy e proxy_url

from routers import portal, contratos, folha, pca, avisos, comprasnet, inmetro, recadastramento

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui as rotas modularizadas
app.include_router(portal.router)
app.include_router(contratos.router)
app.include_router(folha.router)
app.include_router(pca.router)
app.include_router(avisos.router)
app.include_router(comprasnet.router)
app.include_router(inmetro.router)
app.include_router(recadastramento.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)