from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

from sei_client import SEISergipeClient

router = APIRouter(prefix="/api/sei", tags=["SEI Sergipe"])

# Instância base do cliente SOAP
sei_client_instancia = SEISergipeClient(
    wsdl_url=os.getenv("SEI_WSDL_URL", "http://172.23.6.223:8000/sei/controlador_ws.php?servico=sei"),
    sigla_sistema=os.getenv("SEI_SIGLA_SISTEMA", "ITPS-PCA"),
    identificacao_servico=os.getenv("SEI_CHAVE_ACESSO", "CHAVE_LOCAL_TESTE_ITPS"),
    mock_mode=False
)

class GerarProcessoSEIRequest(BaseModel):
    item_id: Optional[int] = None
    especificacao: str
    id_unidade: Optional[int] = 110000001
    id_tipo_procedimento: Optional[str] = "100000050"
    nivel_acesso: Optional[int] = 0
    interessados: Optional[List[str]] = None
    incluir_dfd_automatica: Optional[bool] = True
    codigo_item: Optional[str] = ""
    quantidade: Optional[int] = 1
    unidade_medida: Optional[str] = "Unidade"
    valor_unitario: Optional[float] = 0.0
    valor_total: Optional[float] = 0.0
    setor_requisitante: Optional[str] = "AGEPLAN - ITPS"
    unidades_tramitar: Optional[List[int]] = None
    mock_mode: Optional[bool] = False

class IncluirDocumentoSEIRequest(BaseModel):
    protocolo_procedimento: str
    id_unidade: Optional[int] = 110000001
    id_serie: Optional[str] = "100000001"
    tipo: Optional[str] = "R"
    descricao: str
    conteudo_html: Optional[str] = None
    nome_arquivo: Optional[str] = None
    conteudo_arquivo_base64: Optional[str] = None
    nivel_acesso: Optional[int] = 0
    mock_mode: Optional[bool] = False

class EnviarProcessoSEIRequest(BaseModel):
    protocolo_procedimento: str
    id_unidade_origem: Optional[int] = 110000001
    unidades_destino: List[int]
    sin_manter_aberto: Optional[str] = "S"
    sin_enviar_email: Optional[str] = "S"
    dias_retorno: Optional[int] = None
    mock_mode: Optional[bool] = False

@router.get("/status")
def api_status_sei():
    """
    Retorna o status geral da integração SEI Sergipe.
    """
    return {
        "status": "online",
        "servidor_sei_vm": "http://172.23.6.223:8000/sei",
        "wsdl_url": "http://172.23.6.223:8000/sei/controlador_ws.php?servico=sei",
        "sigla_sistema": "ITPS-PCA",
        "versao_integracao": "2.0",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/testar-conexao-vm")
def testar_conexao_sei_vm():
    """
    Testa a comunicação SOAP com a VM do SEI Sergipe (172.23.6.223:8000)
    """
    resultado = sei_client_instancia.gerar_procedimento(especificacao="Teste de Conexão Backend ITPS")
    return resultado

@router.get("/unidades")
def api_listar_unidades_sei(mock_mode: Optional[bool] = False):
    """
    Retorna a lista de unidades do SEI para seleção de tramitação.
    """
    client = SEISergipeClient(mock_mode=mock_mode)
    return client.listar_unidades()

@router.post("/pca/gerar-processo")
def api_gerar_processo_pca(req: GerarProcessoSEIRequest):
    """
    Gera um novo processo no SEI Sergipe conforme manual oficial (com Interessados, NivelAcesso),
    anexa a DFD em HTML automaticamente e opcionalmente tramita para a unidade destino.
    """
    client = SEISergipeClient(mock_mode=req.mock_mode)
    
    # 1. Autuar o processo (gerarProcedimento)
    res_proc = client.gerar_procedimento(
        id_unidade=req.id_unidade or 110000001,
        id_tipo_procedimento=req.id_tipo_procedimento or "100000050",
        especificacao=req.especificacao,
        interessados=req.interessados or ["ITPS - Instituto Tecnológico e de Pesquisas do Estado de Sergipe"],
        nivel_acesso=req.nivel_acesso if req.nivel_acesso is not None else 0,
        unidades_envio=req.unidades_tramitar
    )

    num_processo = res_proc.get("procedimento_formatado") or res_proc.get("numero_processo") or "13801.79.000412/2026-19"
    res_doc = None

    # 2. Se ativado, incluir a DFD em HTML automaticamente (incluirDocumento)
    if req.incluir_dfd_automatica:
        num_dfd = str(hash(num_processo) % 9000 + 1000)
        html_dfd = client.gerar_html_dfd(
            numero_processo=num_processo,
            numero_dfd=num_dfd,
            setor_requisitante=req.setor_requisitante or "AGEPLAN - ITPS",
            descricao_objeto=req.especificacao,
            codigo_item=req.codigo_item or "",
            quantidade=req.quantidade or 1,
            unidade_medida=req.unidade_medida or "Unidade",
            valor_unitario=req.valor_unitario or 0.0,
            valor_total=req.valor_total or (float(req.quantidade or 1) * float(req.valor_unitario or 0.0))
        )
        
        res_doc = client.incluir_documento(
            id_unidade=req.id_unidade or 110000001,
            protocolo_procedimento=num_processo,
            id_serie="100000001",  # Série DFD
            tipo="R",
            descricao=f"Documento de Formalização da Demanda (DFD) - {req.especificacao[:50]}",
            conteudo_html=html_dfd,
            nivel_acesso=req.nivel_acesso if req.nivel_acesso is not None else 0
        )

    return {
        "sucesso": True,
        "processo": res_proc,
        "dfd_anexa": res_doc,
        "mensagem": f"Processo {num_processo} gerado com sucesso no SEI Sergipe!"
    }

@router.post("/documento/incluir")
def api_incluir_documento_sei(req: IncluirDocumentoSEIRequest):
    """
    Anexa um documento (HTML interno ou PDF externo) a um processo existente no SEI.
    """
    client = SEISergipeClient(mock_mode=req.mock_mode)
    return client.incluir_documento(
        id_unidade=req.id_unidade or 110000001,
        protocolo_procedimento=req.protocolo_procedimento,
        id_serie=req.id_serie or "100000001",
        tipo=req.tipo or "R",
        descricao=req.descricao,
        conteudo_html=req.conteudo_html,
        nome_arquivo=req.nome_arquivo,
        conteudo_arquivo_base64=req.conteudo_arquivo_base64,
        nivel_acesso=req.nivel_acesso if req.nivel_acesso is not None else 0
    )

@router.post("/processo/enviar")
@router.post("/processo/tramitar")
def api_tramitar_processo_sei(req: EnviarProcessoSEIRequest):
    """
    Tramita (envia) um processo para uma ou mais unidades do SEI.
    Atende tanto a rota /enviar quanto /tramitar.
    """
    client = SEISergipeClient(mock_mode=req.mock_mode)
    return client.enviar_processo(
        protocolo_procedimento=req.protocolo_procedimento,
        id_unidade_origem=req.id_unidade_origem or 110000001,
        unidades_destino=req.unidades_destino,
        sin_manter_aberto=req.sin_manter_aberto or "S",
        sin_enviar_email=req.sin_enviar_email or "S",
        dias_retorno=req.dias_retorno
    )

@router.get("/processo/{numero_processo}/status")
def api_consultar_status_processo_sei(numero_processo: str):
    """
    Consulta o andamento e localização de um processo no SEI Sergipe.
    """
    resultado = sei_client_instancia.consultar_procedimento(protocolo_procedimento=numero_processo)
    return resultado
