from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from core.database import get_folha_db

router = APIRouter()

# --- MODELOS PYDANTIC: FOLHA DE PAGAMENTO ---

class FolhaLoginRequest(BaseModel):
    usuario: str
    senha: str

class FuncionarioModel(BaseModel):
    nome: str
    cpf: str
    rg: str
    vinculo: str
    banco: str
    agencia: str
    conta: str
    cargo_nome: str
    locacao: str
    percentual: float
    valor_sipes: float
    pensao: float
    outros: float
    acrescimos: float
    tem_inss: int
    tem_irrf: int
    irrf_sipes_real: Optional[float] = 0.0
    irrf_manual: Optional[float] = 0.0
    dias_trabalhados: Optional[int] = 30
    previdencia_rpps: Optional[int] = 0

class CargoModel(BaseModel):
    nome: str
    locacao: str
    percentual_padrao: float

class ConfigGeralModel(BaseModel):
    chave: str
    valor: float

class ConfigInssModel(BaseModel):
    limite: float
    aliquota: float
    deducao: float

class ConfigIrrfModel(BaseModel):
    limite: float
    aliquota: float
    deducao: float

class ClosedFolhaDetail(BaseModel):
    funcionario_id: int
    nome: str
    cpf: str
    cargo_nome: str
    locacao: str
    vinculo: str
    percentual: float
    valor_sipes: float
    pensao: float
    outros: float
    acrescimos: float
    bruto: float
    inss: float
    irrf: float
    liquido: float
    dias_trabalhados: Optional[int] = 30
    previdencia_rpps: Optional[int] = 0

class FecharFolhaRequest(BaseModel):
    mes_ano: str
    criado_por: str
    detalhes: List[ClosedFolhaDetail]

class LogRequest(BaseModel):
    usuario: str
    acao: str
    detalhes: str


# --- ENDPOINTS: FOLHA DE PAGAMENTO ---

@router.post("/api/folha/login")
def folha_login(req: FolhaLoginRequest):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, permissao FROM folha.usuarios WHERE usuario = %s AND senha = %s", (req.usuario, req.senha))
        user = cursor.fetchone()
        conn.close()
        if user:
            return dict(user)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.get("/api/folha/funcionarios")
def folha_funcionarios_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha.funcionarios ORDER BY nome ASC")
        funcionarios = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"funcionarios": funcionarios}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/folha/funcionarios")
def folha_funcionarios_criar(f: FuncionarioModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO folha.funcionarios (nome, cpf, rg, vinculo, banco, agencia, conta, cargo_nome, locacao, percentual, valor_sipes, pensao, outros, acrescimos, tem_inss, tem_irrf, irrf_sipes_real, irrf_manual, dias_trabalhados, previdencia_rpps) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (f.nome, f.cpf, f.rg, f.vinculo, f.banco, f.agencia, f.conta, f.cargo_nome, f.locacao, f.percentual, f.valor_sipes, f.pensao, f.outros, f.acrescimos, f.tem_inss, f.tem_irrf, f.irrf_sipes_real, f.irrf_manual, f.dias_trabalhados, f.previdencia_rpps)
        )
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return {"id": new_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/folha/funcionarios/{id}")
def folha_funcionarios_atualizar(id: int, f: FuncionarioModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE folha.funcionarios SET nome = %s, cpf = %s, rg = %s, vinculo = %s, banco = %s, agencia = %s, conta = %s, cargo_nome = %s, locacao = %s, percentual = %s, valor_sipes = %s, pensao = %s, outros = %s, acrescimos = %s, tem_inss = %s, tem_irrf = %s, irrf_sipes_real = %s, irrf_manual = %s, dias_trabalhados = %s, previdencia_rpps = %s WHERE id = %s",
            (f.nome, f.cpf, f.rg, f.vinculo, f.banco, f.agencia, f.conta, f.cargo_nome, f.locacao, f.percentual, f.valor_sipes, f.pensao, f.outros, f.acrescimos, f.tem_inss, f.tem_irrf, f.irrf_sipes_real, f.irrf_manual, f.dias_trabalhados, f.previdencia_rpps, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/folha/funcionarios/{id}")
def folha_funcionarios_deletar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM folha.funcionarios WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Cargos
@router.get("/api/folha/cargos")
def folha_cargos_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha.cargos ORDER BY nome ASC")
        cargos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"cargos": cargos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/folha/cargos")
def folha_cargos_criar(c: CargoModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO folha.cargos (nome, locacao, percentual_padrao) VALUES (%s, %s, %s) RETURNING id",
            (c.nome, c.locacao, c.percentual_padrao)
        )
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return {"id": new_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/folha/cargos/{id}")
def folha_cargos_atualizar(id: int, c: CargoModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE folha.cargos SET nome = %s, locacao = %s, percentual_padrao = %s WHERE id = %s",
            (c.nome, c.locacao, c.percentual_padrao, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/folha/cargos/{id}")
def folha_cargos_deletar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM folha.cargos WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Configurações & Tabelas Fiscais
@router.get("/api/folha/config")
def folha_config_obter():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM folha.config_geral")
        geral = {row['chave']: row['valor'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT * FROM folha.config_inss ORDER BY limite ASC")
        inss = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM folha.config_irrf ORDER BY limite ASC")
        irrf = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return {"geral": geral, "inss": inss, "irrf": irrf}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/folha/config/geral")
def folha_config_geral_salvar(c: ConfigGeralModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO folha.config_geral (chave, valor) VALUES (%s, %s) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (c.chave, c.valor)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/folha/config/inss/{id}")
def folha_config_inss_atualizar(id: int, c: ConfigInssModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE folha.config_inss SET limite = %s, aliquota = %s, deducao = %s WHERE id = %s",
            (c.limite, c.aliquota, c.deducao, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.put("/api/folha/config/irrf/{id}")
def folha_config_irrf_atualizar(id: int, c: ConfigIrrfModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE folha.config_irrf SET limite = %s, aliquota = %s, deducao = %s WHERE id = %s",
            (c.limite, c.aliquota, c.deducao, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/folha/config/reset")
def folha_config_reset():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        cursor.execute("TRUNCATE TABLE folha.config_inss RESTART IDENTITY CASCADE")
        cursor.execute("TRUNCATE TABLE folha.config_irrf RESTART IDENTITY CASCADE")
        
        inss_defaults = [
            (1621.00, 7.5, 0.0),
            (2902.84, 9.0, 24.32),
            (4354.27, 12.0, 111.40),
            (8475.55, 14.0, 198.49)
        ]
        cursor.executemany("INSERT INTO folha.config_inss (limite, aliquota, deducao) VALUES (%s, %s, %s)", inss_defaults)
        
        irrf_defaults = [
            (2428.80, 0.0, 0.0),
            (2826.65, 7.5, 182.16),
            (3751.05, 15.0, 394.16),
            (4664.68, 22.5, 675.49),
            (999999999.00, 27.5, 908.73)
        ]
        cursor.executemany("INSERT INTO folha.config_irrf (limite, aliquota, deducao) VALUES (%s, %s, %s)", irrf_defaults)
        
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Fechamentos
@router.get("/api/folha/folhas")
def folha_historico_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha.folhas_salvas ORDER BY mes_ano DESC")
        folhas = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"folhas": folhas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.get("/api/folha/folha-detalhes/{id}")
def folha_detalhes_listar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha.folha_historico_detalhe WHERE folha_salva_id = %s ORDER BY nome ASC", (id,))
        detalhes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"detalhes": detalhes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/folha/fechar")
def folha_historico_fechar(req: FecharFolhaRequest):
    conn = get_folha_db()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM folha.folhas_salvas WHERE mes_ano = %s", (req.mes_ano,))
        antigo = cursor.fetchone()
        if antigo:
            antigo_id = antigo['id']
            cursor.execute("DELETE FROM folha.folha_historico_detalhe WHERE folha_salva_id = %s", (antigo_id,))
            cursor.execute("DELETE FROM folha.folhas_salvas WHERE id = %s", (antigo_id,))
            
        cursor.execute(
            "INSERT INTO folha.folhas_salvas (mes_ano, data_fechamento, criado_por) VALUES (%s, %s, %s) RETURNING id",
            (req.mes_ano, datetime.now().isoformat()[:19].replace('T', ' '), req.criado_por)
        )
        folha_id = cursor.fetchone()['id']
        
        detalhes_tuplas = [
            (
                folha_id,
                d.funcionario_id,
                d.nome,
                d.cpf,
                d.cargo_nome,
                d.locacao,
                d.vinculo,
                d.percentual,
                d.valor_sipes,
                d.pensao,
                d.outros,
                d.acrescimos,
                d.bruto,
                d.inss,
                d.irrf,
                d.liquido,
                d.dias_trabalhados,
                d.previdencia_rpps
            ) for d in req.detalhes
        ]
        
        cursor.executemany(
            "INSERT INTO folha.folha_historico_detalhe (folha_salva_id, funcionario_id, nome, cpf, cargo_nome, locacao, vinculo, percentual, valor_sipes, pensao, outros, acrescimos, bruto, inss, irrf, liquido, dias_trabalhados, previdencia_rpps) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            detalhes_tuplas
        )
        
        conn.commit()
        conn.close()
        return {"id": folha_id, "success": True}
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/folha/folhas/{id}")
def folha_historico_deletar(id: int):
    conn = get_folha_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM folha.folha_historico_detalhe WHERE folha_salva_id = %s", (id,))
        cursor.execute("DELETE FROM folha.folhas_salvas WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Auditoria (Logs)
@router.get("/api/folha/logs")
def folha_logs_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha.auditoria ORDER BY id DESC LIMIT 1000")
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/folha/logs")
def folha_logs_criar(req: LogRequest):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO folha.auditoria (usuario, acao, data_hora, detalhes) VALUES (%s, %s, %s, %s)",
            (req.usuario, req.acao, datetime.now().isoformat()[:19].replace('T', ' '), req.detalhes)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.delete("/api/folha/logs")
def folha_logs_limpar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE folha.auditoria RESTART IDENTITY CASCADE")
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")
