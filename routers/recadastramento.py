import os
import re
import csv
import io
import json
import uuid
import shutil
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Request, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from core.database import get_folha_db

class AdminLoginRequest(BaseModel):
    usuario: str
    senha: str

class AdminUpdateRequest(BaseModel):
    status: Optional[str] = "ENVIADO"
    observacoes: Optional[str] = ""
    matricula: Optional[str] = ""
    cargo: Optional[str] = ""
    setor: Optional[str] = ""
    vinculo: Optional[str] = ""
    data_admissao: Optional[str] = ""

class AdminEditCompletoRequest(BaseModel):
    nome_completo: Optional[str] = None
    cpf: Optional[str] = None
    rg: Optional[str] = None
    rg_orgao: Optional[str] = None
    rg_uf: Optional[str] = None
    rg_data_expedicao: Optional[str] = None
    data_nascimento: Optional[str] = None
    sexo: Optional[str] = None
    estado_civil: Optional[str] = None
    nome_mae: Optional[str] = None
    nome_pai: Optional[str] = None
    titulo_eleitor: Optional[str] = None
    titulo_zona: Optional[str] = None
    titulo_secao: Optional[str] = None
    ctps_numero: Optional[str] = None
    ctps_serie: Optional[str] = None
    ctps_uf: Optional[str] = None
    escolaridade: Optional[str] = None
    curso_formacao: Optional[str] = None
    cep: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    whatsapp: Optional[str] = None
    email_pessoal: Optional[str] = None
    email_institucional: Optional[str] = None
    possui_dependentes: Optional[bool] = None
    dependentes_json: Optional[str] = None
    matricula: Optional[str] = None
    cargo: Optional[str] = None
    setor: Optional[str] = None
    vinculo: Optional[str] = None
    data_admissao: Optional[str] = None
    status: Optional[str] = None
    observacoes: Optional[str] = None

# Backward compatibility alias
StatusUpdateRequest = AdminUpdateRequest

router = APIRouter(prefix="/api/recadastramento", tags=["Recadastramento"])

# Diretório base para armazenamento dos documentos enviados
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads", "recadastramento"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitizar_nome_arquivo(nome: str) -> str:
    """Remove caracteres especiais e espaços do nome do arquivo."""
    nome = os.path.basename(nome)
    nome = re.sub(r'[^a-zA-Z0-9_.-]', '_', nome)
    return nome

def gerar_numero_protocolo() -> str:
    """Gera um número de protocolo único sequencial ou com timestamp."""
    ano_atual = datetime.now().year
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as total FROM folha.recadastramentos")
        row = cursor.fetchone()
        proximo_num = (row['total'] if row else 0) + 1
        return f"ITPS-REC-{ano_atual}-{proximo_num:05d}"
    except Exception:
        codigo_aleatorio = uuid.uuid4().hex[:6].upper()
        return f"ITPS-REC-{ano_atual}-{codigo_aleatorio}"
    finally:
        conn.close()

def salvar_arquivo_upload(cpf: str, tipo_doc: str, upload_file: Optional[UploadFile]) -> str:
    """Salva o arquivo no disco de forma segura e retorna o caminho relativo."""
    if not upload_file or not upload_file.filename:
        return ""
    
    cpf_limpo = re.sub(r'\D', '', cpf)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_limpo = sanitizar_nome_arquivo(upload_file.filename)
    nome_final = f"{cpf_limpo}_{tipo_doc}_{timestamp}_{nome_limpo}"
    
    caminho_absoluto = os.path.join(UPLOAD_DIR, nome_final)
    
    with open(caminho_absoluto, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
        
    return f"uploads/recadastramento/{nome_final}"


@router.post("/enviar")
async def enviar_recadastramento(
    request: Request,
    # 1. Dados Pessoais
    nome_completo: str = Form(...),
    cpf: str = Form(...),
    rg: Optional[str] = Form(""),
    rg_orgao: Optional[str] = Form(""),
    rg_uf: Optional[str] = Form(""),
    rg_data_expedicao: Optional[str] = Form(""),
    data_nascimento: str = Form(...),
    sexo: Optional[str] = Form(""),
    estado_civil: Optional[str] = Form(""),
    nome_mae: Optional[str] = Form(""),
    nome_pai: Optional[str] = Form(""),
    titulo_eleitor: Optional[str] = Form(""),
    titulo_zona: Optional[str] = Form(""),
    titulo_secao: Optional[str] = Form(""),
    
    # Escolaridade & CTPS (Checklist GERH)
    escolaridade: Optional[str] = Form(""),
    curso_formacao: Optional[str] = Form(""),
    ctps_numero: Optional[str] = Form(""),
    ctps_serie: Optional[str] = Form(""),
    ctps_uf: Optional[str] = Form(""),
    
    # 2. Endereço & Contato
    cep: Optional[str] = Form(""),
    logradouro: Optional[str] = Form(""),
    numero: Optional[str] = Form(""),
    complemento: Optional[str] = Form(""),
    bairro: Optional[str] = Form(""),
    cidade: Optional[str] = Form(""),
    uf: Optional[str] = Form(""),
    whatsapp: Optional[str] = Form(""),
    email_pessoal: Optional[str] = Form(""),
    email_institucional: Optional[str] = Form(""),
    
    # 3. Dados Funcionais
    matricula: Optional[str] = Form(""),
    cargo: Optional[str] = Form(""),
    setor: Optional[str] = Form(""),
    vinculo: Optional[str] = Form(""),
    data_admissao: Optional[str] = Form(""),
    
    # 4. Dados Bancários
    banco: Optional[str] = Form(""),
    tipo_conta: Optional[str] = Form(""),
    agencia: Optional[str] = Form(""),
    conta: Optional[str] = Form(""),
    tipo_chave_pix: Optional[str] = Form(""),
    chave_pix: Optional[str] = Form(""),
    
    # 5. Dependentes
    possui_dependentes: Optional[str] = Form("false"),
    dependentes_json: Optional[str] = Form("[]"),
    
    # 6. Uploads de Documentos (Checklist Oficial GERH)
    doc_foto3x4: Optional[UploadFile] = File(None),
    doc_identificacao: UploadFile = File(...),
    doc_titulo: Optional[UploadFile] = File(None),
    doc_residencia: UploadFile = File(...),
    doc_ctps: Optional[UploadFile] = File(None),
    doc_escolaridade: Optional[UploadFile] = File(None),
    doc_historico_grade: Optional[UploadFile] = File(None),
    doc_bancario: Optional[UploadFile] = File(None),
    doc_dependentes: Optional[List[UploadFile]] = File(None)
):
    try:
        cpf_limpo = re.sub(r'\D', '', cpf)
        if not cpf_limpo or len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido. Forneça um CPF completo de 11 dígitos.")
        
        protocolo = gerar_numero_protocolo()
        data_hora_envio = datetime.now()
        ip_cliente = request.client.host if request.client else ""
        
        # Salvar arquivos enviados (Checklist Oficial GERH)
        path_foto3x4 = salvar_arquivo_upload(cpf_limpo, "foto3x4", doc_foto3x4)
        path_identificacao = salvar_arquivo_upload(cpf_limpo, "identificacao", doc_identificacao)
        path_titulo = salvar_arquivo_upload(cpf_limpo, "titulo", doc_titulo)
        path_residencia = salvar_arquivo_upload(cpf_limpo, "residencia", doc_residencia)
        path_ctps = salvar_arquivo_upload(cpf_limpo, "ctps", doc_ctps)
        path_escolaridade = salvar_arquivo_upload(cpf_limpo, "escolaridade", doc_escolaridade)
        path_historico_grade = salvar_arquivo_upload(cpf_limpo, "historico_grade", doc_historico_grade)
        path_bancario = salvar_arquivo_upload(cpf_limpo, "bancario", doc_bancario)
        
        paths_dependentes = []
        if doc_dependentes:
            for idx, f in enumerate(doc_dependentes):
                if f and f.filename:
                    p = salvar_arquivo_upload(cpf_limpo, f"dep_{idx+1}", f)
                    if p: paths_dependentes.append(p)
                    
        has_dep = str(possui_dependentes).lower() in ["true", "1", "sim", "s"]
        
        conn = get_folha_db()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO folha.recadastramentos (
                protocolo, nome_completo, cpf, rg, rg_orgao, rg_uf, rg_data_expedicao,
                data_nascimento, sexo, estado_civil, nome_mae, nome_pai,
                titulo_eleitor, titulo_zona, titulo_secao,
                escolaridade, curso_formacao, ctps_numero, ctps_serie, ctps_uf,
                cep, logradouro, numero, complemento, bairro, cidade, uf,
                whatsapp, email_pessoal, email_institucional,
                matricula, cargo, setor, vinculo, data_admissao,
                banco, tipo_conta, agencia, conta, tipo_chave_pix, chave_pix,
                possui_dependentes, dependentes_json,
                doc_foto3x4_path, doc_identificacao_path, doc_titulo_path, doc_residencia_path,
                doc_ctps_path, doc_escolaridade_path, doc_historico_grade_path, doc_bancario_path,
                doc_dependentes_paths, status, data_envio, ip_envio
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            ) RETURNING id;
        """
        
        cursor.execute(query, (
            protocolo, nome_completo.strip(), cpf.strip(), rg.strip(), rg_orgao.strip(), rg_uf.strip(), rg_data_expedicao.strip(),
            data_nascimento.strip(), sexo.strip(), estado_civil.strip(), nome_mae.strip(), nome_pai.strip(),
            titulo_eleitor.strip(), titulo_zona.strip(), titulo_secao.strip(),
            escolaridade.strip(), curso_formacao.strip(), ctps_numero.strip(), ctps_serie.strip(), ctps_uf.strip(),
            cep.strip(), logradouro.strip(), numero.strip(), complemento.strip(), bairro.strip(), cidade.strip(), uf.strip(),
            whatsapp.strip(), email_pessoal.strip(), email_institucional.strip(),
            matricula.strip(), cargo.strip(), setor.strip(), vinculo.strip(), data_admissao.strip(),
            banco.strip(), tipo_conta.strip(), agencia.strip(), conta.strip(), tipo_chave_pix.strip(), chave_pix.strip(),
            has_dep, dependentes_json,
            path_foto3x4, path_identificacao, path_titulo, path_residencia,
            path_ctps, path_escolaridade, path_historico_grade, path_bancario,
            json.dumps(paths_dependentes), 'ENVIADO', data_hora_envio, ip_cliente
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "id": new_id,
            "protocolo": protocolo,
            "data_envio": data_hora_envio.strftime("%d/%m/%Y às %H:%M:%S"),
            "nome_completo": nome_completo.strip(),
            "cpf": cpf.strip(),
            "cargo": cargo.strip(),
            "setor": setor.strip(),
            "mensagem": "Recadastramento e documentação enviados com sucesso!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro ao salvar recadastramento: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar recadastramento: {str(e)}")


@router.get("/consultar/{termo}")
def consultar_recadastramento(termo: str):
    """Consulta o recadastramento por número de protocolo ou CPF."""
    termo_limpo = termo.strip()
    cpf_limpo = re.sub(r'\D', '', termo_limpo)
    
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, protocolo, nome_completo, cpf, cargo, setor, vinculo, 
                   status, observacoes, data_envio, whatsapp, email_pessoal
            FROM folha.recadastramentos
            WHERE protocolo = %s OR cpf = %s OR regexp_replace(cpf, '[^0-9]', '', 'g') = %s
            ORDER BY id DESC LIMIT 1
            """,
            (termo_limpo, termo_limpo, cpf_limpo)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Nenhum recadastramento encontrado com os dados informados.")
            
        data = dict(row)
        if isinstance(data.get('data_envio'), datetime):
            data['data_envio'] = data['data_envio'].strftime("%d/%m/%Y %H:%M:%S")
            
        return {"success": True, "recadastramento": data}
    finally:
        conn.close()


@router.get("/detalhes/{protocolo}")
def obter_detalhes_completos(protocolo: str):
    """Retorna os dados completos do recadastramento para emissão do comprovante."""
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM folha.recadastramentos WHERE protocolo = %s",
            (protocolo.strip(),)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Protocolo não encontrado.")
            
        data = dict(row)
        if isinstance(data.get('data_envio'), datetime):
            data['data_envio'] = data['data_envio'].strftime("%d/%m/%Y às %H:%M:%S")
            
        return {"success": True, "dados": data}
    finally:
        conn.close()


# ========================================================
# ENDPOINTS ADMINISTRATIVOS (PAINEL GERH / RECADASTRAMENTO)
# ========================================================

@router.get("/admin/listar")
def admin_listar_recadastramentos(
    busca: Optional[str] = None,
    status: Optional[str] = None,
    escolaridade: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """Lista todos os recadastramentos com filtros, paginação e estatísticas."""
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []

        if busca and busca.strip():
            b = f"%{busca.strip()}%"
            cpf_num = re.sub(r'\D', '', busca.strip())
            conditions.append(
                "(nome_completo ILIKE %s OR protocolo ILIKE %s OR email_pessoal ILIKE %s OR whatsapp ILIKE %s OR regexp_replace(cpf, '[^0-9]', '', 'g') ILIKE %s)"
            )
            params.extend([b, b, b, b, f"%{cpf_num}%"])

        if status and status.strip() and status != "TODOS":
            conditions.append("status = %s")
            params.append(status.strip())

        if escolaridade and escolaridade.strip() and escolaridade != "TODAS":
            conditions.append("escolaridade = %s")
            params.append(escolaridade.strip())

        if data_inicio and data_inicio.strip():
            conditions.append("data_envio >= %s")
            params.append(f"{data_inicio.strip()} 00:00:00")

        if data_fim and data_fim.strip():
            conditions.append("data_envio <= %s")
            params.append(f"{data_fim.strip()} 23:59:59")

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # 1. Total filtrado
        count_query = f"SELECT COUNT(*) as total FROM folha.recadastramentos {where_clause}"
        cursor.execute(count_query, params)
        total_filtrado = cursor.fetchone()['total']

        # 2. Registros paginados
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT * FROM folha.recadastramentos
            {where_clause}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(data_query, params + [page_size, offset])
        rows = cursor.fetchall()

        itens = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get('data_envio'), datetime):
                d['data_envio_formatada'] = d['data_envio'].strftime("%d/%m/%Y %H:%M")
                d['data_envio'] = d['data_envio'].isoformat()
            
            # Formatar lista de dependentes
            try:
                d['dependentes'] = json.loads(d.get('dependentes_json') or '[]')
            except Exception:
                d['dependentes'] = []
                
            # Formatar caminhos de dependentes
            try:
                d['doc_dependentes_paths'] = json.loads(d.get('doc_dependentes_paths') or '[]')
            except Exception:
                d['doc_dependentes_paths'] = []

            itens.append(d)

        # 3. Estatísticas Gerais (Dashboard)
        cursor.execute("""
            SELECT
                COUNT(*) as total_geral,
                COUNT(*) FILTER (WHERE data_envio >= CURRENT_DATE) as total_hoje,
                COUNT(*) FILTER (WHERE possui_dependentes = true) as total_com_dependentes,
                COUNT(*) FILTER (WHERE status = 'ENVIADO') as total_enviados,
                COUNT(*) FILTER (WHERE status = 'EM ANÁLISE') as total_em_analise,
                COUNT(*) FILTER (WHERE status = 'APROVADO') as total_aprovados,
                COUNT(*) FILTER (WHERE status = 'PENDENTE') as total_pendentes
            FROM folha.recadastramentos
        """)
        stats_row = cursor.fetchone()
        metricas = dict(stats_row) if stats_row else {}

        return {
            "success": True,
            "total": total_filtrado,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_filtrado + page_size - 1) // page_size if total_filtrado > 0 else 1,
            "items": itens,
            "metricas": metricas
        }
    finally:
        conn.close()


@router.get("/admin/detalhes/{id}")
def admin_obter_detalhes(id: int):
    """Retorna a ficha completa de um servidor por ID."""
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM folha.recadastramentos WHERE id = %s", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Registro não encontrado.")
            
        data = dict(row)
        if isinstance(data.get('data_envio'), datetime):
            data['data_envio_formatada'] = data['data_envio'].strftime("%d/%m/%Y às %H:%M:%S")
            data['data_envio'] = data['data_envio'].isoformat()
            
        try:
            data['dependentes'] = json.loads(data.get('dependentes_json') or '[]')
        except Exception:
            data['dependentes'] = []
            
        try:
            data['doc_dependentes_paths'] = json.loads(data.get('doc_dependentes_paths') or '[]')
        except Exception:
            data['doc_dependentes_paths'] = []

        return {"success": True, "servidor": data}
    finally:
        conn.close()


@router.patch("/admin/{id}/status")
@router.patch("/admin/{id}/dados-funcionais")
def admin_atualizar_dados(id: int, req: AdminUpdateRequest):
    """Atualiza status, observações e dados funcionais preenchidos pelo RH."""
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE folha.recadastramentos
            SET status = COALESCE(%s, status),
                observacoes = %s,
                matricula = %s,
                cargo = %s,
                setor = %s,
                vinculo = %s,
                data_admissao = %s
            WHERE id = %s
            RETURNING id, protocolo, nome_completo, status, observacoes, matricula, cargo, setor, vinculo, data_admissao;
            """,
            (
                req.status.strip() if req.status else "ENVIADO",
                req.observacoes.strip() if req.observacoes else "",
                req.matricula.strip() if req.matricula else "",
                req.cargo.strip() if req.cargo else "",
                req.setor.strip() if req.setor else "",
                req.vinculo.strip() if req.vinculo else "",
                req.data_admissao.strip() if req.data_admissao else "",
                id
            )
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Registro não encontrado.")
        conn.commit()
        return {"success": True, "mensagem": "Dados funcionais e parecer salvos com sucesso!", "dados": dict(row)}
    finally:
        conn.close()


@router.delete("/admin/{id}")
def admin_excluir_registro(id: int):
    """Exclui um recadastramento do sistema."""
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM folha.recadastramentos WHERE id = %s RETURNING id, protocolo, nome_completo;", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Registro não encontrado.")
        conn.commit()
        return {"success": True, "mensagem": f"Recadastramento {row['protocolo']} ({row['nome_completo']}) excluído com sucesso."}
    finally:
        conn.close()


@router.get("/admin/exportar-csv")
def admin_exportar_csv(
    busca: Optional[str] = None,
    status: Optional[str] = None,
    escolaridade: Optional[str] = None
):
    """Exporta todos os dados filtrados em formato CSV (Excel UTF-8)."""
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []

        if busca and busca.strip():
            b = f"%{busca.strip()}%"
            cpf_num = re.sub(r'\D', '', busca.strip())
            conditions.append(
                "(nome_completo ILIKE %s OR protocolo ILIKE %s OR email_pessoal ILIKE %s OR whatsapp ILIKE %s OR regexp_replace(cpf, '[^0-9]', '', 'g') ILIKE %s)"
            )
            params.extend([b, b, b, b, f"%{cpf_num}%"])

        if status and status.strip() and status != "TODOS":
            conditions.append("status = %s")
            params.append(status.strip())

        if escolaridade and escolaridade.strip() and escolaridade != "TODAS":
            conditions.append("escolaridade = %s")
            params.append(escolaridade.strip())

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT protocolo, nome_completo, cpf, rg, rg_orgao, rg_uf, data_nascimento,
                   sexo, estado_civil, nome_mae, nome_pai, titulo_eleitor, escolaridade,
                   curso_formacao, ctps_numero, ctps_serie, logradouro, numero, complemento,
                   bairro, cidade, uf, cep, whatsapp, email_pessoal, possui_dependentes,
                   status, observacoes, data_envio
            FROM folha.recadastramentos
            {where_clause}
            ORDER BY id DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # Header
        writer.writerow([
            "Protocolo", "Nome Completo", "CPF", "RG", "Órgão/UF", "Data Nasc.",
            "Sexo", "Estado Civil", "Nome Mãe", "Nome Pai", "Título Eleitor",
            "Escolaridade", "Curso/Formação", "CTPS", "Série", "Endereço",
            "Número", "Complemento", "Bairro", "Cidade", "UF", "CEP",
            "WhatsApp", "E-mail", "Possui Dependentes", "Status", "Observações", "Data Envio"
        ])

        for r in rows:
            data_env = r['data_envio'].strftime("%d/%m/%Y %H:%M:%S") if isinstance(r.get('data_envio'), datetime) else str(r.get('data_envio') or '')
            writer.writerow([
                r['protocolo'], r['nome_completo'], r['cpf'], r['rg'], f"{r['rg_orgao']}/{r['rg_uf']}", r['data_nascimento'],
                r['sexo'], r['estado_civil'], r['nome_mae'], r['nome_pai'], r['titulo_eleitor'],
                r['escolaridade'], r['curso_formacao'], r['ctps_numero'], r['ctps_serie'], r['logradouro'],
                r['numero'], r['complemento'], r['bairro'], r['cidade'], r['uf'], r['cep'],
                r['whatsapp'], r['email_pessoal'], "Sim" if r['possui_dependentes'] else "Não",
                r['status'], r['observacoes'], data_env
            ])

        csv_data = "\ufeff" + output.getvalue()  # BOM UTF-8 for Excel
        filename = f"recadastramentos_itps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            content=csv_data.encode('utf-8'),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        conn.close()


# ========================================================
# AUTENTICAÇÃO E EDIÇÃO COMPLETA (ADMINISTRATIVO GERH)
# ========================================================

ADMIN_USERS = {
    "gerh": "itps123",
    "admin": "itps123",
    "rh": "itps123",
    "gerh.itps": "gerh@2026"
}

@router.post("/admin/auth/login")
def admin_login(req: AdminLoginRequest):
    """Autentica o operador do RH/GERH para acesso aos dados sensíveis."""
    u = req.usuario.strip().lower()
    s = req.senha.strip()
    
    if u in ADMIN_USERS and ADMIN_USERS[u] == s:
        token_data = f"ITPS-GERH-AUTH-{u}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:12]}"
        return {
            "success": True,
            "mensagem": "Autenticado com sucesso!",
            "token": token_data,
            "usuario": "GERH / Recursos Humanos",
            "perfil": "ADMINISTRADOR_RH",
            "login": u
        }
    else:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")


@router.put("/admin/{id}/editar-completo")
def admin_editar_completo(id: int, req: AdminEditCompletoRequest):
    """Permite ao administrador do RH editar todos os dados cadastrais, pessoais, endereço, dependentes e funcionais."""
    conn = get_folha_db()
    cursor = conn.cursor()
    try:
        # Verifica se o registro existe
        cursor.execute("SELECT * FROM folha.recadastramentos WHERE id = %s", (id,))
        antigo = cursor.fetchone()
        if not antigo:
            raise HTTPException(status_code=404, detail="Registro não encontrado.")

        query = """
            UPDATE folha.recadastramentos
            SET nome_completo = COALESCE(%s, nome_completo),
                cpf = COALESCE(%s, cpf),
                rg = COALESCE(%s, rg),
                rg_orgao = COALESCE(%s, rg_orgao),
                rg_uf = COALESCE(%s, rg_uf),
                rg_data_expedicao = COALESCE(%s, rg_data_expedicao),
                data_nascimento = COALESCE(%s, data_nascimento),
                sexo = COALESCE(%s, sexo),
                estado_civil = COALESCE(%s, estado_civil),
                nome_mae = COALESCE(%s, nome_mae),
                nome_pai = COALESCE(%s, nome_pai),
                titulo_eleitor = COALESCE(%s, titulo_eleitor),
                titulo_zona = COALESCE(%s, titulo_zona),
                titulo_secao = COALESCE(%s, titulo_secao),
                ctps_numero = COALESCE(%s, ctps_numero),
                ctps_serie = COALESCE(%s, ctps_serie),
                ctps_uf = COALESCE(%s, ctps_uf),
                escolaridade = COALESCE(%s, escolaridade),
                curso_formacao = COALESCE(%s, curso_formacao),
                cep = COALESCE(%s, cep),
                logradouro = COALESCE(%s, logradouro),
                numero = COALESCE(%s, numero),
                complemento = COALESCE(%s, complemento),
                bairro = COALESCE(%s, bairro),
                cidade = COALESCE(%s, cidade),
                uf = COALESCE(%s, uf),
                whatsapp = COALESCE(%s, whatsapp),
                email_pessoal = COALESCE(%s, email_pessoal),
                email_institucional = COALESCE(%s, email_institucional),
                possui_dependentes = COALESCE(%s, possui_dependentes),
                dependentes_json = COALESCE(%s, dependentes_json),
                matricula = COALESCE(%s, matricula),
                cargo = COALESCE(%s, cargo),
                setor = COALESCE(%s, setor),
                vinculo = COALESCE(%s, vinculo),
                data_admissao = COALESCE(%s, data_admissao),
                status = COALESCE(%s, status),
                observacoes = COALESCE(%s, observacoes)
            WHERE id = %s
            RETURNING *;
        """
        cursor.execute(
            query,
            (
                req.nome_completo, req.cpf, req.rg, req.rg_orgao, req.rg_uf, req.rg_data_expedicao,
                req.data_nascimento, req.sexo, req.estado_civil, req.nome_mae, req.nome_pai,
                req.titulo_eleitor, req.titulo_zona, req.titulo_secao, req.ctps_numero, req.ctps_serie,
                req.ctps_uf, req.escolaridade, req.curso_formacao, req.cep, req.logradouro, req.numero,
                req.complemento, req.bairro, req.cidade, req.uf, req.whatsapp, req.email_pessoal,
                req.email_institucional, req.possui_dependentes, req.dependentes_json, req.matricula,
                req.cargo, req.setor, req.vinculo, req.data_admissao, req.status, req.observacoes,
                id
            )
        )
        row = cursor.fetchone()
        conn.commit()
        
        dados = dict(row)
        if isinstance(dados.get('data_envio'), datetime):
            dados['data_envio_formatada'] = dados['data_envio'].strftime("%d/%m/%Y às %H:%M:%S")
            dados['data_envio'] = dados['data_envio'].isoformat()
            
        try:
            dados['dependentes'] = json.loads(dados.get('dependentes_json') or '[]')
        except Exception:
            dados['dependentes'] = []
            
        return {"success": True, "mensagem": "Ficha cadastral atualizada com sucesso pelo RH!", "servidor": dados}
    finally:
        conn.close()
