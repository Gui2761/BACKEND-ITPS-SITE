import base64
import time
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
from core.database import get_contratos_db

router = APIRouter()

# Cache de alta performance em memória (TTL: 60s com invalidação automática em mutações)
_cache_contratos = {"data": None, "timestamp": 0}
_cache_categories = {"data": None, "timestamp": 0}
CACHE_TTL = 60

# --- MODELOS PYDANTIC: CONTRATOS ---
class ContratosLoginRequest(BaseModel):
    username: str
    password: str

class ContratoModel(BaseModel):
    instituicao: str
    tipo: str
    objetivo: Optional[str] = None
    valor: Optional[float] = 0.0
    valor_gasto: Optional[float] = 0.0
    prazo: Optional[str] = None
    caminho_arquivo: Optional[str] = None

class CategoryModel(BaseModel):
    name: str
    color: str
    group: str


# --- ENDPOINTS: CONTRATOS ---

@router.post("/api/contratos/login")
def contratos_login(req: ContratosLoginRequest):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, name, role FROM contratos.users WHERE username = %s AND password = %s", (req.username, req.password))
        user = cursor.fetchone()
        conn.close()
        if user:
            return dict(user)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.get("/api/contratos")
def contratos_listar():
    global _cache_contratos
    now = time.time()
    if _cache_contratos["data"] is not None and (now - _cache_contratos["timestamp"] < CACHE_TTL):
        return {"contratos": _cache_contratos["data"]}

    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, instituicao, tipo, objetivo, valor, valor_gasto, prazo,
                   CASE 
                       WHEN caminho_arquivo IS NULL OR caminho_arquivo = '' THEN ''
                       WHEN LENGTH(caminho_arquivo) > 200 THEN '/api/contratos/' || id || '/arquivo'
                       ELSE caminho_arquivo
                   END as caminho_arquivo
            FROM contratos.contratos ORDER BY id DESC
        """)
        contratos = []
        for row in cursor.fetchall():
            c = dict(row)
            c['tem_arquivo'] = bool(c.get('caminho_arquivo'))
            contratos.append(c)
        conn.close()
        
        _cache_contratos["data"] = contratos
        _cache_contratos["timestamp"] = now
        return {"contratos": contratos}
    except Exception as e:
        if _cache_contratos["data"] is not None:
            return {"contratos": _cache_contratos["data"]}
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.get("/api/contratos/{id}/arquivo")
def contratos_obter_arquivo(id: int, download: Optional[bool] = False):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT instituicao, caminho_arquivo FROM contratos.contratos WHERE id = %s", (id,))
        row = cursor.fetchone()
        conn.close()
        if not row or not row['caminho_arquivo']:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        
        ca = row['caminho_arquivo']
        filename = f"contrato_{id}.pdf"
        
        if '||' in ca:
            parts = ca.split('||', 1)
            filename = parts[0].strip() or filename
            raw_data = parts[1].strip()
        else:
            raw_data = ca.strip()
            
        if raw_data.startswith('data:'):
            header, b64_str = raw_data.split(',', 1)
            pdf_bytes = base64.b64decode(b64_str)
            disp = f'attachment; filename="{filename}"' if download else 'inline'
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": disp,
                    "Content-Type": "application/pdf"
                }
            )
        elif raw_data.startswith('http://') or raw_data.startswith('https://'):
            return RedirectResponse(url=raw_data)
        else:
            return Response(
                content=raw_data.encode('utf-8'),
                media_type="text/plain"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar arquivo: {str(e)}")

@router.post("/api/contratos")
def contratos_criar(c: ContratoModel):
    global _cache_contratos
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contratos.contratos (instituicao, tipo, objetivo, valor, valor_gasto, prazo, caminho_arquivo) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, c.caminho_arquivo)
        )
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        _cache_contratos["data"] = None  # Invalidação imediata
        return {"id": new_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/contratos/{id}")
def contratos_atualizar(id: int, c: ContratoModel):
    global _cache_contratos
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        if c.caminho_arquivo and f"/api/contratos/{id}/arquivo" in c.caminho_arquivo:
            cursor.execute(
                "UPDATE contratos.contratos SET instituicao = %s, tipo = %s, objetivo = %s, valor = %s, valor_gasto = %s, prazo = %s WHERE id = %s",
                (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, id)
            )
        else:
            cursor.execute(
                "UPDATE contratos.contratos SET instituicao = %s, tipo = %s, objetivo = %s, valor = %s, valor_gasto = %s, prazo = %s, caminho_arquivo = %s WHERE id = %s",
                (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, c.caminho_arquivo, id)
            )
        conn.commit()
        conn.close()
        _cache_contratos["data"] = None  # Invalidação imediata
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/contratos/{id}")
def contratos_deletar(id: int):
    global _cache_contratos
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.contratos WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        _cache_contratos["data"] = None  # Invalidação imediata
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Categorias
@router.get("/api/contratos/categories")
def contratos_categories_listar():
    global _cache_categories
    now = time.time()
    if _cache_categories["data"] is not None and (now - _cache_categories["timestamp"] < CACHE_TTL):
        return {"categories": _cache_categories["data"]}

    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contratos.categories ORDER BY name ASC")
        categories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        _cache_categories["data"] = categories
        _cache_categories["timestamp"] = now
        return {"categories": categories}
    except Exception as e:
        if _cache_categories["data"] is not None:
            return {"categories": _cache_categories["data"]}
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/contratos/categories")
def contratos_categories_criar(cat: CategoryModel):
    global _cache_categories
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        
        # Duplicidade tratada via verificação elegante em Python
        cursor.execute("SELECT 1 FROM contratos.categories WHERE name = %s", (cat.name,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(
                "INSERT INTO contratos.categories (name, color, \"group\") VALUES (%s, %s, %s)",
                (cat.name, cat.color, cat.group)
            )
            conn.commit()
            
        conn.close()
        _cache_categories["data"] = None
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/contratos/categories/{id}")
def contratos_categories_atualizar(id: int, cat: CategoryModel):
    global _cache_categories
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contratos.categories SET name = %s, color = %s, \"group\" = %s WHERE id = %s",
            (cat.name, cat.color, cat.group, id)
        )
        conn.commit()
        conn.close()
        _cache_categories["data"] = None
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/contratos/categories/{name}")
def contratos_categories_deletar(name: str):
    global _cache_categories
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.categories WHERE name = %s", (name,))
        conn.commit()
        conn.close()
        _cache_categories["data"] = None
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")
