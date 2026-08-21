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

import os
from fastapi.staticfiles import StaticFiles

# Diretório base de uploads
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

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