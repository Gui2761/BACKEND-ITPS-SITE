from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import uuid
import os
from datetime import datetime

router = APIRouter()

class AvisoInput(BaseModel):
    titulo: str
    conteudo: str
    prioridade: str  # "urgente", "informativo", "geral"
    codigo_acesso: str

AVISOS_FILE = "avisos.json"

def ler_avisos() -> List[Dict[str, Any]]:
    if not os.path.exists(AVISOS_FILE):
        exemplo = [
            {
                "id": str(uuid.uuid4()),
                "titulo": "Bem-vindo à Nova Intranet!",
                "conteudo": "Este é o novo Mural de Avisos dinâmico do ITPS. Aqui o setor de TI e RH divulgará comunicados oficiais rapidamente.",
                "prioridade": "geral",
                "data_criacao": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
        ]
        with open(AVISOS_FILE, "w", encoding="utf-8") as f:
            json.dump(exemplo, f, ensure_ascii=False, indent=4)
        return exemplo
    
    try:
        with open(AVISOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def salvar_avisos(avisos: List[Dict[str, Any]]):
    with open(AVISOS_FILE, "w", encoding="utf-8") as f:
        json.dump(avisos, f, ensure_ascii=False, indent=4)

@router.get("/api/avisos")
async def get_avisos():
    return {"resultado": ler_avisos()}

@router.post("/api/avisos")
async def post_aviso(aviso_in: AvisoInput):
    if aviso_in.codigo_acesso != "itps123":
        raise HTTPException(status_code=403, detail="Código de acesso incorreto!")
    
    avisos = ler_avisos()
    novo_aviso = {
        "id": str(uuid.uuid4()),
        "titulo": aviso_in.titulo,
        "conteudo": aviso_in.conteudo,
        "prioridade": aviso_in.prioridade,
        "data_criacao": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    avisos.insert(0, novo_aviso)
    salvar_avisos(avisos)
    return {"success": True, "aviso": novo_aviso}

@router.delete("/api/avisos/{aviso_id}")
async def delete_aviso(aviso_id: str, codigo_acesso: str):
    if codigo_acesso != "itps123":
        raise HTTPException(status_code=403, detail="Código de acesso incorreto!")
    
    avisos = ler_avisos()
    novos_avisos = [a for a in avisos if a["id"] != aviso_id]
    
    if len(novos_avisos) == len(avisos):
        raise HTTPException(status_code=404, detail="Aviso não encontrado!")
        
    salvar_avisos(novos_avisos)
    return {"success": True, "message": "Aviso removido com sucesso!"}
