import os
import re
import json
import uuid
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Request
from fastapi.responses import FileResponse, JSONResponse
from core.database import get_folha_db

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

def salvar_arquivo_upload(cpf: str, tipo_doc: str, upload_file: UploadFile) -> str:
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
    
    # 6. Uploads Obrigatórios
    doc_identificacao: UploadFile = File(...),
    doc_residencia: UploadFile = File(...),
    doc_bancario: UploadFile = File(...),
    doc_dependentes: Optional[List[UploadFile]] = File(None)
):
    try:
        cpf_limpo = re.sub(r'\D', '', cpf)
        if not cpf_limpo or len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido. Forneça um CPF completo de 11 dígitos.")
        
        protocolo = gerar_numero_protocolo()
        data_hora_envio = datetime.now()
        ip_cliente = request.client.host if request.client else ""
        
        # Salvar arquivos enviados
        path_identificacao = salvar_arquivo_upload(cpf_limpo, "identificacao", doc_identificacao)
        path_residencia = salvar_arquivo_upload(cpf_limpo, "residencia", doc_residencia)
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
                cep, logradouro, numero, complemento, bairro, cidade, uf,
                whatsapp, email_pessoal, email_institucional,
                matricula, cargo, setor, vinculo, data_admissao,
                banco, tipo_conta, agencia, conta, tipo_chave_pix, chave_pix,
                possui_dependentes, dependentes_json,
                doc_identificacao_path, doc_residencia_path, doc_bancario_path, doc_dependentes_paths,
                status, data_envio, ip_envio
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            ) RETURNING id;
        """
        
        cursor.execute(query, (
            protocolo, nome_completo.strip(), cpf.strip(), rg.strip(), rg_orgao.strip(), rg_uf.strip(), rg_data_expedicao.strip(),
            data_nascimento.strip(), sexo.strip(), estado_civil.strip(), nome_mae.strip(), nome_pai.strip(),
            titulo_eleitor.strip(), titulo_zona.strip(), titulo_secao.strip(),
            cep.strip(), logradouro.strip(), numero.strip(), complemento.strip(), bairro.strip(), cidade.strip(), uf.strip(),
            whatsapp.strip(), email_pessoal.strip(), email_institucional.strip(),
            matricula.strip(), cargo.strip(), setor.strip(), vinculo.strip(), data_admissao.strip(),
            banco.strip(), tipo_conta.strip(), agencia.strip(), conta.strip(), tipo_chave_pix.strip(), chave_pix.strip(),
            has_dep, dependentes_json,
            path_identificacao, path_residencia, path_bancario, json.dumps(paths_dependentes),
            'ENVIADO', data_hora_envio, ip_cliente
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
            "mensagem": "Recadastramento enviado com sucesso!"
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
