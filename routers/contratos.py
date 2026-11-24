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
    formato_pagamento: Optional[str] = 'amostra'
    parcelas: Optional[int] = 12
    valor_parcela: Optional[float] = 0.0

class LancamentoAmostraModel(BaseModel):
    numero: Optional[int] = None
    data: Optional[str] = None
    quantidade: Optional[int] = 1
    amostra: Optional[str] = None
    valor_amostra: Optional[float] = 0.0
    pago_mes: Optional[float] = 0.0
    observacao: Optional[str] = None

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
            SELECT c.id, c.instituicao, c.tipo, c.objetivo, c.valor,
                   COALESCE((SELECT SUM(la.valor_amostra) FROM contratos.lancamentos_amostras la WHERE la.contrato_id = c.id), c.valor_gasto, 0.0) as valor_gasto,
                   c.prazo, c.processo_sei,
                   COALESCE(c.formato_pagamento, 'amostra') as formato_pagamento,
                   COALESCE(c.parcelas, 12) as parcelas,
                   COALESCE(c.valor_parcela, 0.0) as valor_parcela,
                   CASE 
                       WHEN c.caminho_arquivo IS NULL OR c.caminho_arquivo = '' THEN ''
                       WHEN LENGTH(c.caminho_arquivo) > 200 THEN '/api/contratos/' || c.id || '/arquivo'
                       ELSE c.caminho_arquivo
                   END as caminho_arquivo
            FROM contratos.contratos c ORDER BY c.id DESC
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
            """INSERT INTO contratos.contratos 
               (instituicao, tipo, objetivo, valor, valor_gasto, prazo, caminho_arquivo, formato_pagamento, parcelas, valor_parcela) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (c.instituicao, c.tipo, c.objetivo, c.valor or 0.0, c.valor_gasto or 0.0, c.prazo, c.caminho_arquivo, c.formato_pagamento or 'amostra', c.parcelas or 12, c.valor_parcela or 0.0)
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
                """UPDATE contratos.contratos 
                   SET instituicao = %s, tipo = %s, objetivo = %s, valor = %s, valor_gasto = %s, prazo = %s,
                       formato_pagamento = %s, parcelas = %s, valor_parcela = %s 
                   WHERE id = %s""",
                (c.instituicao, c.tipo, c.objetivo, c.valor or 0.0, c.valor_gasto or 0.0, c.prazo, c.formato_pagamento or 'amostra', c.parcelas or 12, c.valor_parcela or 0.0, id)
            )
        else:
            cursor.execute(
                """UPDATE contratos.contratos 
                   SET instituicao = %s, tipo = %s, objetivo = %s, valor = %s, valor_gasto = %s, prazo = %s, caminho_arquivo = %s,
                       formato_pagamento = %s, parcelas = %s, valor_parcela = %s 
                   WHERE id = %s""",
                (c.instituicao, c.tipo, c.objetivo, c.valor or 0.0, c.valor_gasto or 0.0, c.prazo, c.caminho_arquivo, c.formato_pagamento or 'amostra', c.parcelas or 12, c.valor_parcela or 0.0, id)
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

# --- ENDPOINTS: AMOSTRAS E PAGAMENTOS (TABELA DA FICHA EXECUTIVA) ---

@router.get("/api/contratos/{id}/amostras")
def contratos_listar_amostras(id: int):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, contrato_id, numero, to_char(data, 'YYYY-MM-DD') as data,
                   quantidade, amostra, valor_amostra, pago_mes, observacao
            FROM contratos.lancamentos_amostras
            WHERE contrato_id = %s
            ORDER BY numero ASC, id ASC
        """, (id,))
        itens = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"amostras": itens}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar amostras: {str(e)}")

@router.post("/api/contratos/{id}/amostras")
def contratos_criar_amostra(id: int, a: LancamentoAmostraModel):
    global _cache_contratos
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        
        # Se numero não informado, pega max(numero) + 1
        num = a.numero
        if not num:
            cursor.execute("SELECT COALESCE(MAX(numero), 0) + 1 as prox FROM contratos.lancamentos_amostras WHERE contrato_id = %s", (id,))
            num = cursor.fetchone()['prox']
            
        cursor.execute("""
            INSERT INTO contratos.lancamentos_amostras 
            (contrato_id, numero, data, quantidade, amostra, valor_amostra, pago_mes, observacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (id, num, a.data if a.data else None, a.quantidade or 1, a.amostra, a.valor_amostra or 0.0, a.pago_mes or 0.0, a.observacao))
        new_id = cursor.fetchone()['id']
        
        # Atualiza valor_gasto do contrato (Investimento Realizado = soma das amostras)
        cursor.execute("""
            UPDATE contratos.contratos 
            SET valor_gasto = (SELECT COALESCE(SUM(valor_amostra), 0.0) FROM contratos.lancamentos_amostras WHERE contrato_id = %s)
            WHERE id = %s
        """, (id, id))
        
        conn.commit()
        conn.close()
        _cache_contratos["data"] = None
        return {"id": new_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar amostra: {str(e)}")

@router.put("/api/contratos/{id}/amostras/{amostra_id}")
def contratos_atualizar_amostra(id: int, amostra_id: int, a: LancamentoAmostraModel):
    global _cache_contratos
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE contratos.lancamentos_amostras
            SET numero = %s, data = %s, quantidade = %s, amostra = %s,
                valor_amostra = %s, pago_mes = %s, observacao = %s
            WHERE id = %s AND contrato_id = %s
        """, (a.numero, a.data if a.data else None, a.quantidade or 1, a.amostra, a.valor_amostra or 0.0, a.pago_mes or 0.0, a.observacao, amostra_id, id))
        
        # Atualiza valor_gasto do contrato
        cursor.execute("""
            UPDATE contratos.contratos 
            SET valor_gasto = (SELECT COALESCE(SUM(valor_amostra), 0.0) FROM contratos.lancamentos_amostras WHERE contrato_id = %s)
            WHERE id = %s
        """, (id, id))
        
        conn.commit()
        conn.close()
        _cache_contratos["data"] = None
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar amostra: {str(e)}")

@router.delete("/api/contratos/{id}/amostras/{amostra_id}")
def contratos_deletar_amostra(id: int, amostra_id: int):
    global _cache_contratos
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.lancamentos_amostras WHERE id = %s AND contrato_id = %s", (amostra_id, id))
        
        # Atualiza valor_gasto do contrato
        cursor.execute("""
            UPDATE contratos.contratos 
            SET valor_gasto = (SELECT COALESCE(SUM(valor_amostra), 0.0) FROM contratos.lancamentos_amostras WHERE contrato_id = %s)
            WHERE id = %s
        """, (id, id))
        
        conn.commit()
        conn.close()
        _cache_contratos["data"] = None
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar amostra: {str(e)}")

@router.post("/api/contratos/{id}/gerar-parcelas")
def contratos_gerar_parcelas_mensais(id: int):
    global _cache_contratos
    from datetime import date
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT valor, parcelas, prazo, formato_pagamento FROM contratos.contratos WHERE id = %s", (id,))
        c = cursor.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Contrato não encontrado")
            
        valor = float(c['valor'] or 0.0)
        qtd_parcelas = int(c['parcelas'] or 12)
        if qtd_parcelas <= 0:
            qtd_parcelas = 12
            
        valor_parcela = round(valor / qtd_parcelas, 2)
        
        # Remove lançamentos anteriores se houver para regenerar
        cursor.execute("DELETE FROM contratos.lancamentos_amostras WHERE contrato_id = %s", (id,))
        
        # Gera cada parcela mensal a partir do início do mês atual
        hoje = date.today()
        for i in range(1, qtd_parcelas + 1):
            m_offset = hoje.month - 1 + (i - 1)
            ano = hoje.year + m_offset // 12
            mes = m_offset % 12 + 1
            dt_str = f"{ano:04d}-{mes:02d}-01"
            
            desc_amostra = f"Mensalidade {i:02d}/{qtd_parcelas:02d}"
            obs = f"Lançamento automático de débito ({mes:02d}/{ano:04d})"
            cursor.execute("""
                INSERT INTO contratos.lancamentos_amostras 
                (contrato_id, numero, data, quantidade, amostra, valor_amostra, pago_mes, observacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (id, i, dt_str, 1, desc_amostra, 0.0, valor_parcela, obs))
            
        conn.commit()
        conn.close()
        _cache_contratos["data"] = None
        return {"success": True, "parcelas_geradas": qtd_parcelas, "valor_parcela": valor_parcela}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar parcelas: {str(e)}")

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
