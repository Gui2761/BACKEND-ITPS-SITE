from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.database import get_contratos_db

router = APIRouter()

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.get("/api/contratos")
def contratos_listar():
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contratos.contratos ORDER BY id DESC")
        contratos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"contratos": contratos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/contratos")
def contratos_criar(c: ContratoModel):
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
        return {"id": new_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/contratos/{id}")
def contratos_atualizar(id: int, c: ContratoModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contratos.contratos SET instituicao = %s, tipo = %s, objetivo = %s, valor = %s, valor_gasto = %s, prazo = %s, caminho_arquivo = %s WHERE id = %s",
            (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, c.caminho_arquivo, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/contratos/{id}")
def contratos_deletar(id: int):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.contratos WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Categorias
@router.get("/api/contratos/categories")
def contratos_categories_listar():
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contratos.categories ORDER BY name ASC")
        categories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/contratos/categories")
def contratos_categories_criar(cat: CategoryModel):
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
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/contratos/categories/{id}")
def contratos_categories_atualizar(id: int, cat: CategoryModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contratos.categories SET name = %s, color = %s, \"group\" = %s WHERE id = %s",
            (cat.name, cat.color, cat.group, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/contratos/categories/{name}")
def contratos_categories_deletar(name: str):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.categories WHERE name = %s", (name,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")
