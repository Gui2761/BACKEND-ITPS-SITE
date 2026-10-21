from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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

@router.post("/api/folha/cargos/{id}/propagar")
def folha_cargos_propagar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT nome, percentual_padrao FROM folha.cargos WHERE id = %s", (id,))
        cargo = cursor.fetchone()
        if not cargo:
            conn.close()
            raise HTTPException(status_code=404, detail="Cargo não encontrado")
        
        cursor.execute(
            "UPDATE folha.funcionarios SET percentual = %s WHERE LOWER(TRIM(cargo_nome)) = LOWER(TRIM(%s))",
            (cargo['percentual_padrao'], cargo['nome'])
        )
        afetados = cursor.rowcount
        conn.commit()
        conn.close()
        return {"success": True, "afetados": afetados}
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
def folha_config_geral_salvar(payload: Dict[str, Any]):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        # Se for chave/valor único
        if "chave" in payload and "valor" in payload and len(payload) == 2:
            cursor.execute(
                "INSERT INTO folha.config_geral (chave, valor) VALUES (%s, %s) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                (str(payload["chave"]), float(payload["valor"]))
            )
        else:
            # Dicionário com múltiplos campos (ex: base_convenio, aliquota_patronal, teto_inss)
            for k, v in payload.items():
                if v is not None:
                    try:
                        cursor.execute(
                            "INSERT INTO folha.config_geral (chave, valor) VALUES (%s, %s) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                            (str(k), float(v))
                        )
                    except (ValueError, TypeError):
                        continue
        conn.commit()
        conn.close()

        # Sincronização resiliente com SQLite da rede GERH
        try:
            import sqlite3
            sqlite_path = r'\\172.23.6.7\gerh\1- COAPE\FolhaITPS_Dados\folha_itps_v8_rh_sync.db'
            sconn = sqlite3.connect(sqlite_path, timeout=3)
            scur = sconn.cursor()
            if "chave" in payload and "valor" in payload and len(payload) == 2:
                scur.execute("INSERT OR REPLACE INTO config_geral (chave, valor) VALUES (?, ?)", (str(payload["chave"]), float(payload["valor"])))
            else:
                for k, v in payload.items():
                    if v is not None:
                        try:
                            scur.execute("INSERT OR REPLACE INTO config_geral (chave, valor) VALUES (?, ?)", (str(k), float(v)))
                        except Exception:
                            pass
            sconn.commit()
            sconn.close()
        except Exception:
            pass

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

        # Sincronização SQLite opcional
        try:
            import sqlite3
            sqlite_path = r'\\172.23.6.7\gerh\1- COAPE\FolhaITPS_Dados\folha_itps_v8_rh_sync.db'
            sconn = sqlite3.connect(sqlite_path, timeout=3)
            scur = sconn.cursor()
            scur.execute("UPDATE config_inss SET limite = ?, aliquota = ?, deducao = ? WHERE id = ?", (c.limite, c.aliquota, c.deducao, id))
            sconn.commit()
            sconn.close()
        except Exception:
            pass

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

        # Sincronização SQLite opcional
        try:
            import sqlite3
            sqlite_path = r'\\172.23.6.7\gerh\1- COAPE\FolhaITPS_Dados\folha_itps_v8_rh_sync.db'
            sconn = sqlite3.connect(sqlite_path, timeout=3)
            scur = sconn.cursor()
            scur.execute("UPDATE config_irrf SET limite = ?, aliquota = ?, deducao = ? WHERE id = ?", (c.limite, c.aliquota, c.deducao, id))
            sconn.commit()
            sconn.close()
        except Exception:
            pass

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


# ==================== ROTAS SISSGRH (HISTÓRICO E CADASTRO MASTER) ====================

@router.get("/api/folha/sissgrh/servidores")
def sissgrh_servidores_listar(
    termo: Optional[str] = None,
    situacao: Optional[str] = None,
    setor: Optional[str] = None,
    vinculo: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        where_clauses = []
        params = []
        
        if termo and termo.strip():
            t = f"%{termo.strip()}%"
            where_clauses.append("(nome ILIKE %s OR cpf ILIKE %s OR rg ILIKE %s OR cargo ILIKE %s)")
            params.extend([t, t, t, t])
            
        if situacao and situacao.strip() and situacao.lower() != 'todos':
            where_clauses.append("situacao ILIKE %s")
            params.append(situacao.strip())
            
        if setor and setor.strip() and setor.lower() != 'todos':
            where_clauses.append("(setor ILIKE %s OR sigla_setor ILIKE %s)")
            s = f"%{setor.strip()}%"
            params.extend([s, s])
            
        if vinculo and vinculo.strip() and vinculo.lower() != 'todos':
            where_clauses.append("vinculo ILIKE %s")
            params.append(vinculo.strip())
            
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        # Total
        cursor.execute(f"SELECT COUNT(*) as total FROM folha.sissgrh_servidores {where_sql}", tuple(params))
        total = cursor.fetchone()['total']
        
        # Dados paginados
        params_pag = list(params) + [limit, offset]
        cursor.execute(
            f"""
            SELECT id, sisgeri_id, nome, cpf, rg, nascimento, sexo, banco, agencia, conta,
                   cargo, setor, sigla_setor, comissao_simbolo, comissao_descricao,
                   situacao, vinculo, insalubridade, percentual_insalubridade,
                   email, email_corporativo, celular, telefone, cidade, uf
            FROM folha.sissgrh_servidores
            {where_sql}
            ORDER BY nome ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params_pag)
        )
        servidores = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "servidores": servidores
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.get("/api/folha/sissgrh/servidores/{id}")
def sissgrh_servidor_detalhe(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha.sissgrh_servidores WHERE id = %s", (id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Servidor não encontrado no SISSGRH")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.get("/api/folha/sissgrh/estatisticas")
def sissgrh_estatisticas():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM folha.sissgrh_servidores")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT situacao, COUNT(*) as qtd FROM folha.sissgrh_servidores GROUP BY situacao")
        situacoes = {row['situacao']: row['qtd'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT vinculo, COUNT(*) as qtd FROM folha.sissgrh_servidores GROUP BY vinculo")
        vinculos = {row['vinculo']: row['qtd'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT COUNT(DISTINCT setor) as total_setores FROM folha.sissgrh_servidores WHERE setor IS NOT NULL AND setor != ''")
        total_setores = cursor.fetchone()['total_setores']
        
        cursor.execute("SELECT COUNT(*) as com_banco FROM folha.sissgrh_servidores WHERE conta IS NOT NULL AND conta != ''")
        com_banco = cursor.fetchone()['com_banco']
        
        conn.close()
        return {
            "total_servidores": total,
            "situacoes": situacoes,
            "vinculos": vinculos,
            "total_setores": total_setores,
            "com_dados_bancarios": com_banco
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@router.post("/api/folha/sissgrh/ativar/{id}")
def sissgrh_ativar_servidor(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha.sissgrh_servidores WHERE id = %s", (id,))
        s = cursor.fetchone()
        if not s:
            raise HTTPException(status_code=404, detail="Servidor não encontrado no SISSGRH")
        
        # Verifica se já está em folha.funcionarios
        cursor.execute("SELECT id FROM folha.funcionarios WHERE nome ILIKE %s OR (cpf = %s AND cpf != '')", (s['nome'], s['cpf']))
        existente = cursor.fetchone()
        if existente:
            conn.close()
            return {"success": False, "message": "Este colaborador já está na Folha Ativa!", "id": existente['id']}
        
        vinculo = s['vinculo'] or 'Efetivo'
        tem_inss = 0 if vinculo.lower() in ['efetivo', 'estágio', 'estagiário'] else 1
        prev_rpps = 1 if vinculo.lower() == 'efetivo' else 0
        try:
            perc = float(str(s['percentual_insalubridade'] or 1.0).replace(',', '.').replace('%', ''))
        except:
            perc = 1.0
        
        cursor.execute(
            """
            INSERT INTO folha.funcionarios (
                nome, cpf, rg, vinculo, banco, agencia, conta,
                cargo_nome, locacao, percentual, valor_sipes, pensao,
                outros, acrescimos, tem_inss, tem_irrf, irrf_sipes_real,
                irrf_manual, dias_trabalhados, previdencia_rpps
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, 0.0, 0.0,
                0.0, 0.0, %s, 1, 0.0,
                0.0, 30, %s
            ) RETURNING id
            """,
            (
                s['nome'], s['cpf'], s['rg'], vinculo, s['banco'], s['agencia'], s['conta'],
                s['cargo'] or s['comissao_descricao'] or 'Geral', s['setor'] or 'Geral',
                perc, tem_inss, prev_rpps
            )
        )
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return {"success": True, "id": new_id, "message": f"{s['nome']} adicionado à Folha Ativa com sucesso!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ativar servidor: {str(e)}")

@router.post("/api/folha/sissgrh/sincronizar")
def sissgrh_sincronizar():
    import subprocess
    try:
        ps_path = r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
        script_path = r"C:\Users\gnsilva\BACKEND-ITPS-SITE\scripts\sync_sissgrh.ps1"
        res = subprocess.run([ps_path, "-ExecutionPolicy", "Bypass", "-File", script_path], capture_output=True, text=True, timeout=45)
        if res.returncode != 0:
            raise Exception(res.stderr or res.stdout)
        return {"success": True, "message": "Sincronização com SISGERI (Access) concluída com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na sincronização: {str(e)}")
