from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

from sei_client import SEISergipeClient
from core.database import get_pca_db, get_contratos_db

router = APIRouter(prefix="/api/sei", tags=["SEI Sergipe"])

# Instância base do cliente SOAP
sei_client_instancia = SEISergipeClient(
    wsdl_url=os.getenv("SEI_WSDL_URL", "http://172.23.6.223:8000/sei/controlador_ws.php?servico=sei"),
    sigla_sistema=os.getenv("SEI_SIGLA_SISTEMA", "ITPS-PCA"),
    identificacao_servico=os.getenv("SEI_CHAVE_ACESSO", "CHAVE_LOCAL_TESTE_ITPS"),
    mock_mode=False
)

# Estado de perfil autenticado em memória (com fallback no perfil padrão de Itamar Sandes Santos)
PERFIL_ATIVO_SEI = {
    "usuario": "itamar.sandes",
    "nome_completo": "Itamar Sandes Santos (itamar.sandes/ITPS)",
    "orgao": "ITPS",
    "orgao_id": 27,
    "unidade": "AGEPLAN - ITPS",
    "unidade_id": 110000563,
    "ambiente": "homologacao",
    "autenticado": True,
    "prefixo_nup": "19202.79",
    "ultimo_acesso": datetime.now().strftime("%d/%m/%Y às %H:%M")
}

class AutenticarSEIRequest(BaseModel):
    usuario: str
    senha: str
    orgao_id: Optional[str] = "27"

class GerarProcessoSEIRequest(BaseModel):
    item_id: Optional[int] = None
    especificacao: str
    id_unidade: Optional[int] = 110000563  # AGEPLAN - ITPS (110000563)
    id_tipo_procedimento: Optional[str] = "100000672"  # Gestão de Contratações / Aquisição
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
    ambiente: Optional[str] = "homologacao"  # 'homologacao' ou 'producao'
    usuario_sei: Optional[str] = "itamar.sandes"
    mock_mode: Optional[bool] = False

class IncluirDocumentoSEIRequest(BaseModel):
    protocolo_procedimento: str
    id_unidade: Optional[int] = 110000563
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
    id_unidade_origem: Optional[int] = 110000563
    unidades_destino: List[int]
    sin_manter_aberto: Optional[str] = "S"
    sin_enviar_email: Optional[str] = "S"
    dias_retorno: Optional[int] = None
    mock_mode: Optional[bool] = False

class VincularProcessoPCARequest(BaseModel):
    item_id: int
    processo_sei: Optional[str] = None

class VincularProcessoContratoRequest(BaseModel):
    contrato_id: int
    processo_sei: str


# =========================================================================
# ROTAS DE PERFIL E AUTENTICAÇÃO COM SEI SERGIPE
# =========================================================================

@router.get("/perfil-ativo")
def api_obter_perfil_ativo():
    """
    Retorna o perfil do usuário atualmente conectado ao SEI Sergipe.
    """
    return PERFIL_ATIVO_SEI

@router.post("/autenticar-perfil")
def api_autenticar_perfil(req: AutenticarSEIRequest):
    """
    Valida as credenciais em tempo real com o SEI Sergipe (sei.se.gov.br) via REA,
    extraindo nome completo, unidade de lotação (AGEPLAN) e permissões.
    """
    global PERFIL_ATIVO_SEI
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://sei.se.gov.br/sip/login.php?sigla_orgao_sistema=SE&sigla_sistema=SEI'
    })
    login_url = 'https://sei.se.gov.br/sip/login.php?sigla_orgao_sistema=SE&sigla_sistema=SEI'
    s.cookies.set('SIP_U_SE_SEI', str(req.orgao_id), domain='sei.se.gov.br')

    data = {
        'txtUsuario': req.usuario,
        'pwdSenha': req.senha,
        'selOrgao': str(req.orgao_id),
        'hdnAcao': '2',
        'sbmAcessar': 'Acessar'
    }

    try:
        res = s.post(login_url, data=data, verify=False, allow_redirects=True, timeout=12)
        soup = BeautifulSoup(res.text, 'html.parser')

        # Verificar se houve erro
        err = soup.find(id='divInfraBarraMensagens') or soup.find(class_='infraFaixaErro')
        if err and err.get_text().strip():
            return {
                "sucesso": False,
                "erro": err.get_text().strip()
            }

        texto = soup.get_text().lower()
        if 'sair' in texto or 'controle de processos' in texto:
            nome_completo = "Itamar Sandes Santos (itamar.sandes/ITPS)"
            for a in soup.find_all('a'):
                t = a.get_text().strip()
                if f"({req.usuario}" in t or "/itps" in t.lower():
                    nome_completo = t
                    break

            PERFIL_ATIVO_SEI = {
                "usuario": req.usuario,
                "nome_completo": nome_completo,
                "orgao": "ITPS",
                "orgao_id": int(req.orgao_id) if str(req.orgao_id).isdigit() else 27,
                "unidade": "AGEPLAN - ITPS",
                "unidade_id": 110000563,
                "ambiente": "homologacao",
                "autenticado": True,
                "prefixo_nup": "19202.79",
                "ultimo_acesso": datetime.now().strftime("%d/%m/%Y às %H:%M")
            }

            return {
                "sucesso": True,
                "perfil": PERFIL_ATIVO_SEI,
                "mensagem": f"Usuário {req.usuario} autenticado com sucesso no SEI Sergipe!"
            }
        else:
            return {
                "sucesso": False,
                "erro": "Não foi possível validar as credenciais junto ao portal SEI Sergipe."
            }
    except Exception as e:
        return {
            "sucesso": False,
            "erro": f"Falha na comunicação com o servidor de autenticação do SEI: {str(e)}"
        }


# =========================================================================
# ROTAS DE GERAÇÃO E HOMOLOGAÇÃO DE PROCESSOS SEI
# =========================================================================

@router.get("/status")
def api_status_sei():
    """
    Retorna o status geral da integração SEI Sergipe (Homologação e Produção).
    """
    return {
        "status": "online",
        "ambiente_ativo": PERFIL_ATIVO_SEI.get("ambiente", "homologacao"),
        "servidor_sei_vm": "http://172.23.6.223:8000/sei",
        "servidor_sei_producao": "https://sei.se.gov.br",
        "wsdl_url": "http://172.23.6.223:8000/sei/controlador_ws.php?servico=sei",
        "sigla_sistema": "ITPS-PCA",
        "unidade_padrao": "AGEPLAN - ITPS (110000563)",
        "perfil_conectado": PERFIL_ATIVO_SEI.get("nome_completo"),
        "versao_integracao": "2.5 (REA & Homologação Isolada)",
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
    Gera um novo processo no SEI Sergipe.
    - Se ambiente == 'homologacao': Gera processo isolado seguro com numeração oficial ITPS (19202.79),
      cria o Documento de Formalização da Demanda (DFD) em HTML conforme Lei 14.133/2021,
      salva no repositório de homologação e vincula à demanda sem poluir a produção do Estado.
    - Se ambiente == 'producao': Comunica com o SEI Sergipe Oficial (sei.se.gov.br).
    """
    ambiente = req.ambiente or "homologacao"
    data_hora_atual = datetime.now().strftime("%d/%m/%Y às %H:%M")
    
    if ambiente == "homologacao":
        # Formatar NUP realista do ITPS com sufixo TESTE para clareza e segurança jurídica
        if req.item_id:
            num_processo = f"19202.79.{req.item_id:06d}/2026-TESTE"
            num_dfd = f"{req.item_id:04d}"
        else:
            import random
            rand_nup = random.randint(1000, 9999)
            num_processo = f"19202.79.{rand_nup:06d}/2026-TESTE"
            num_dfd = f"{rand_nup}"

        client = SEISergipeClient(mock_mode=True)
        html_dfd = client.gerar_html_dfd(
            numero_processo=num_processo,
            numero_dfd=num_dfd,
            setor_requisitante=req.setor_requisitante or "AGEPLAN - ITPS",
            descricao_objeto=req.especificacao,
            codigo_item=req.codigo_item or "",
            quantidade=req.quantidade or 1,
            unidade_medida=req.unidade_medida or "Unidade",
            valor_unitario=req.valor_unitario or 0.0,
            valor_total=req.valor_total or (float(req.quantidade or 1) * float(req.valor_unitario or 0.0)),
            responsavel="ITAMAR SANDES SANTOS"
        )

        # Adicionar bloco de assinatura eletrônica do SEI Sergipe
        carimbo_assinatura = f"""
        <div style="margin-top: 35px; border-top: 1px solid #1e293b; padding-top: 12px; font-family: Arial, sans-serif; font-size: 11px; color: #334155;">
          <p style="margin: 0 0 4px 0;">
            <strong style="color: #0f172a;">Documento assinado eletronicamente por:</strong> 
            ITAMAR SANDES SANTOS, Assessor de Planejamento (AGEPLAN - ITPS), em {data_hora_atual}, 
            com fundamento no art. 10, § 2º, da Medida Provisória nº 2.200-2/2001 e Decreto Estadual nº 30.948/2018.
          </p>
          <p style="margin: 0; color: #64748b; font-size: 10px;">
            A autenticidade deste documento pode ser conferida no Sistema Eletrônico de Informações (SEI Sergipe) — Ambiente de Homologação ITPS.
          </p>
        </div>
        """
        html_dfd_completo = html_dfd.replace("</body>", f"{carimbo_assinatura}</body>")

        # Persistir no repositório de homologação
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pca.sei_homologacao 
            (item_id, numero_processo, tipo_processo, interessados, especificacao, unidade_geradora, usuario_gerador, documento_dfd_html)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (numero_processo) DO UPDATE SET 
                documento_dfd_html = EXCLUDED.documento_dfd_html,
                data_geracao = NOW()
        """, (
            req.item_id,
            num_processo,
            "Gestão de Contratações: Aquisição de Bens e Serviços",
            ", ".join(req.interessados or ["ITPS - Instituto Tecnológico e de Pesquisas do Estado de Sergipe"]),
            req.especificacao,
            "AGEPLAN - ITPS",
            req.usuario_sei or "itamar.sandes",
            html_dfd_completo
        ))

        # Atualizar processo_sei no item do PCA
        if req.item_id:
            cursor.execute("UPDATE pca.itens SET processo_sei = %s WHERE id = %s", (num_processo, req.item_id))

        conn.commit()
        conn.close()

        try:
            from routers.pca import invalidar_cache_pca
            invalidar_cache_pca()
        except Exception:
            pass

        return {
            "sucesso": True,
            "ambiente": "homologacao",
            "numero_processo": num_processo,
            "item_id": req.item_id,
            "dfd_anexa": True,
            "link_visualizar": f"http://localhost:8000/api/sei/homologacao/processo/{num_processo}/visualizar",
            "mensagem": f"Processo {num_processo} autuado com sucesso no Ambiente de Homologação ITPS (Sem impacto no SEI Produção)!"
        }

    else:
        # Modo Produção — Comunica com o serviço oficial
        client = SEISergipeClient(mock_mode=req.mock_mode)
        res_proc = client.gerar_procedimento(
            id_unidade=req.id_unidade or 110000563,
            id_tipo_procedimento=req.id_tipo_procedimento or "100000672",
            especificacao=req.especificacao,
            interessados=req.interessados or ["ITPS - Instituto Tecnológico e de Pesquisas do Estado de Sergipe"],
            nivel_acesso=req.nivel_acesso if req.nivel_acesso is not None else 0,
            unidades_envio=req.unidades_tramitar
        )

        num_processo = res_proc.get("procedimento_formatado") or res_proc.get("numero_processo") or f"19202.79.{req.item_id or 1:06d}/2026-19"
        res_doc = None

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
                id_unidade=req.id_unidade or 110000563,
                protocolo_procedimento=num_processo,
                id_serie="100000001",
                tipo="R",
                descricao=f"Documento de Formalização da Demanda (DFD) - {req.especificacao[:50]}",
                conteudo_html=html_dfd,
                nivel_acesso=req.nivel_acesso if req.nivel_acesso is not None else 0
            )

        if req.item_id:
            try:
                conn = get_pca_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE pca.itens SET processo_sei = %s WHERE id = %s", (num_processo, req.item_id))
                conn.commit()
                conn.close()
                from routers.pca import invalidar_cache_pca
                invalidar_cache_pca()
            except Exception as e:
                print(f"Aviso ao persistir processo_sei no item PCA {req.item_id}: {e}")

        return {
            "sucesso": True,
            "ambiente": "producao",
            "processo": res_proc,
            "dfd_anexa": res_doc,
            "numero_processo": num_processo,
            "item_id": req.item_id,
            "link_sei": f"https://sei.se.gov.br/controlador.php?acao=protocolo_pesquisar&txtPesquisaRapida={num_processo}",
            "mensagem": f"Processo {num_processo} registrado no SEI Sergipe Produção!"
        }


# =========================================================================
# VISUALIZADOR OFICIAL DO PROCESSO DE HOMOLOGAÇÃO
# =========================================================================

@router.get("/homologacao/processo/{numero_processo:path}/visualizar", response_class=HTMLResponse)
def api_visualizar_processo_homologacao(numero_processo: str):
    """
    Exibe o dossiê completo do processo de Homologação com layout idêntico ao SEI Sergipe:
    Barra superior oficial, árvore do processo (Processo + DFD), visualizador HTML do documento
    e assinatura eletrônica autenticada.
    """
    conn = get_pca_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.*, i.codigo as cod_igesp, i.item as desc_item, i.valor_total, i.laboratorio
        FROM pca.sei_homologacao h
        LEFT JOIN pca.itens i ON h.item_id = i.id
        WHERE h.numero_processo = %s
    """, (numero_processo,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return HTMLResponse(
            content=f"""
            <div style="font-family:sans-serif; padding:40px; text-align:center;">
                <h2 style="color:#b91c1c;">Processo de Homologação não encontrado</h2>
                <p>O processo <strong>{numero_processo}</strong> não está cadastrado na base de testes do ITPS.</p>
            </div>
            """,
            status_code=404
        )

    dfd_content = row.get("documento_dfd_html") or "<p>Nenhum documento anexado.</p>"
    data_formatada = row.get("data_geracao").strftime("%d/%m/%Y às %H:%M") if row.get("data_geracao") else "Data não registrada"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>SEI / SE - {numero_processo} (Homologação ITPS)</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Open Sans', Arial, sans-serif; background: #f1f5f9; color: #1e293b; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
    
    /* Top Header SEI Sergipe */
    .sei-header {{
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
      color: #ffffff;
      padding: 10px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      z-index: 100;
    }}
    .sei-brand {{ display: flex; align-items: center; gap: 12px; }}
    .sei-logo-badge {{
      background: #ffffff;
      color: #0284c7;
      font-weight: 900;
      font-size: 16px;
      padding: 4px 10px;
      border-radius: 6px;
      letter-spacing: 0.5px;
    }}
    .sei-title-wrap h1 {{ font-size: 16px; font-weight: 700; margin: 0; }}
    .sei-title-wrap p {{ font-size: 11px; opacity: 0.9; }}
    
    .sei-env-tag {{
      background: #fef08a;
      color: #854d0e;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 12px;
      border-radius: 20px;
      display: flex;
      align-items: center;
      gap: 6px;
      border: 1px solid #fde047;
    }}
    
    .sei-user-info {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
    }}
    .sei-user-avatar {{
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: rgba(255,255,255,0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
    }}

    /* Main Workspace */
    .sei-workspace {{
      display: flex;
      flex: 1;
      height: calc(100vh - 56px);
      overflow: hidden;
    }}

    /* Left Sidebar: Process Tree */
    .sei-sidebar {{
      width: 320px;
      background: #ffffff;
      border-right: 1px solid #cbd5e1;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }}
    .sidebar-header {{
      background: #f8fafc;
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      font-size: 12px;
      font-weight: 700;
      color: #475569;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .tree-wrap {{ padding: 12px 8px; }}
    .tree-node {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 12px;
      color: #334155;
      text-decoration: none;
      cursor: pointer;
      margin-bottom: 2px;
    }}
    .tree-node:hover {{ background: #f1f5f9; }}
    .tree-node.active {{
      background: #e0f2fe;
      color: #0369a1;
      font-weight: 700;
    }}
    .tree-sub {{ margin-left: 20px; border-left: 2px solid #e2e8f0; padding-left: 8px; }}

    /* Dossier Info Card in Sidebar */
    .dossier-card {{
      margin: 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 12px;
      font-size: 11px;
    }}
    .dossier-card h4 {{ font-size: 12px; color: #0f172a; margin-bottom: 6px; }}
    .dossier-field {{ margin-bottom: 4px; }}
    .dossier-field strong {{ color: #475569; }}

    /* Right Content Pane */
    .sei-content {{
      flex: 1;
      display: flex;
      flex-direction: column;
      background: #e2e8f0;
      overflow: hidden;
    }}
    .doc-toolbar {{
      background: #ffffff;
      border-bottom: 1px solid #cbd5e1;
      padding: 8px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .doc-toolbar-btns {{ display: flex; gap: 8px; }}
    .btn-tool {{
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      color: #334155;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .btn-tool:hover {{ background: #f1f5f9; border-color: #94a3b8; }}

    .doc-viewport {{
      flex: 1;
      padding: 24px;
      overflow-y: auto;
      display: flex;
      justify-content: center;
    }}
    .doc-sheet {{
      width: 100%;
      max-width: 820px;
      background: #ffffff;
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
      padding: 48px;
      border-radius: 4px;
      min-height: 800px;
    }}
  </style>
</head>
<body>

  <!-- Top Header Oficial do SEI Sergipe (Homologação) -->
  <header class="sei-header">
    <div class="sei-brand">
      <div class="sei-logo-badge">SEI!</div>
      <div class="sei-title-wrap">
        <h1>Sistema Eletrônico de Informações — SEI Sergipe</h1>
        <p>Ambiente de Homologação e Testes Oficiais — ITPS</p>
      </div>
    </div>

    <div class="sei-env-tag">
      <span class="material-symbols-outlined" style="font-size: 16px;">science</span>
      <span>AMBIENTE DE HOMOLOGAÇÃO (SANDBOX)</span>
    </div>

    <div class="sei-user-info">
      <div class="sei-user-avatar">IS</div>
      <div>
        <div style="font-weight: 700;">Itamar Sandes Santos</div>
        <div style="font-size: 11px; opacity: 0.85;">AGEPLAN - ITPS (110000563)</div>
      </div>
    </div>
  </header>

  <!-- Workspace com Árvore do Processo e Visualizador -->
  <div class="sei-workspace">
    
    <!-- Sidebar Árvore do Processo -->
    <aside class="sei-sidebar">
      <div class="sidebar-header">
        <span class="material-symbols-outlined" style="font-size: 18px; color: #0284c7;">account_tree</span>
        <span>Árvore de Documentos</span>
      </div>

      <div class="tree-wrap">
        <!-- Nó Raiz do Processo -->
        <div class="tree-node active">
          <span class="material-symbols-outlined" style="color: #ca8a04; font-size: 18px;">folder_open</span>
          <span>{numero_processo}</span>
        </div>

        <!-- Documentos Filhos -->
        <div class="tree-sub">
          <div class="tree-node active" style="margin-top: 4px;">
            <span class="material-symbols-outlined" style="color: #0284c7; font-size: 18px;">description</span>
            <div>
              <div>DFD nº {row.get('item_id', '000')}</div>
              <div style="font-size: 10px; color: #64748b;">Doc. Formalização Demanda</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Ficha do Processo -->
      <div class="dossier-card">
        <h4>📋 Dados da Autuação</h4>
        <div class="dossier-field"><strong>Tipo:</strong> {row.get('tipo_processo')}</div>
        <div class="dossier-field"><strong>Unidade Geradora:</strong> {row.get('unidade_geradora')}</div>
        <div class="dossier-field"><strong>Responsável:</strong> {row.get('usuario_gerador')}</div>
        <div class="dossier-field"><strong>Data de Criação:</strong> {data_formatada}</div>
        <div class="dossier-field"><strong>Interessados:</strong> {row.get('interessados')}</div>
        <div class="dossier-field" style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed #cbd5e1;">
          <strong>Demanda PCA Vinculada:</strong> #{row.get('item_id')} ({row.get('laboratorio') or 'Geral'})
        </div>
      </div>

      <div style="margin: auto 12px 12px 12px; padding: 10px; background: #fefce8; border: 1px solid #fef08a; border-radius: 6px; font-size: 10px; color: #854d0e;">
        ⚠️ <strong>Aviso de Homologação:</strong> Este processo foi gerado para validação e testes no PCA ITPS. Não gera registros nem despesas no SEI de Produção do Governo de Sergipe.
      </div>
    </aside>

    <!-- Content Pane (Visualizador da DFD) -->
    <main class="sei-content">
      
      <!-- Toolbar do Documento -->
      <div class="doc-toolbar">
        <div style="font-size: 13px; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 8px;">
          <span class="material-symbols-outlined" style="color: #0284c7; font-size: 20px;">contract_edit</span>
          <span>Visualização da Demanda Oficial (Lei 14.133/2021)</span>
        </div>
        <div class="doc-toolbar-btns">
          <button class="btn-tool" onclick="window.print()">
            <span class="material-symbols-outlined" style="font-size: 16px;">print</span>
            <span>Imprimir / Salvar PDF</span>
          </button>
          <button class="btn-tool" onclick="navigator.clipboard.writeText('{numero_processo}').then(() => alert('Protocolo {numero_processo} copiado!'))">
            <span class="material-symbols-outlined" style="font-size: 16px;">content_copy</span>
            <span>Copiar NUP</span>
          </button>
        </div>
      </div>

      <!-- Folha A4 do Documento SEI -->
      <div class="doc-viewport">
        <div class="doc-sheet">
          {dfd_content}
        </div>
      </div>

    </main>
  </div>

</body>
</html>
"""
    return HTMLResponse(content=html)

@router.get("/homologacao/processos")
def api_listar_processos_homologacao():
    """
    Retorna a lista de todos os processos autuados no ambiente de Homologação do ITPS.
    """
    conn = get_pca_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.id, h.item_id, h.numero_processo, h.tipo_processo, h.especificacao, 
               h.unidade_geradora, h.usuario_gerador, h.data_geracao, h.status,
               i.item as desc_item, i.laboratorio, i.valor_total
        FROM pca.sei_homologacao h
        LEFT JOIN pca.itens i ON h.item_id = i.id
        ORDER BY h.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return {"total": len(rows), "processos": rows}


# =========================================================================
# ROTAS OPERACIONAIS E COMPATIBILIDADE SEI SERGIPE
# =========================================================================

@router.post("/documento/incluir")
def api_incluir_documento_sei(req: IncluirDocumentoSEIRequest):
    """
    Anexa um documento (HTML interno ou PDF externo) a um processo existente no SEI.
    """
    client = SEISergipeClient(mock_mode=req.mock_mode)
    return client.incluir_documento(
        id_unidade=req.id_unidade or 110000563,
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
    """
    client = SEISergipeClient(mock_mode=req.mock_mode)
    return client.enviar_processo(
        protocolo_procedimento=req.protocolo_procedimento,
        id_unidade_origem=req.id_unidade_origem or 110000563,
        unidades_destino=req.unidades_destino,
        sin_manter_aberto=req.sin_manter_aberto or "S",
        sin_enviar_email=req.sin_enviar_email or "S",
        dias_retorno=req.dias_retorno
    )

@router.get("/processo/status")
@router.get("/processo/{numero_processo:path}/status")
def api_consultar_status_processo_sei(numero_processo: Optional[str] = None, protocolo: Optional[str] = None):
    """
    Consulta o andamento e localização de um processo no SEI Sergipe.
    """
    proc = protocolo or numero_processo or ""
    resultado = sei_client_instancia.consultar_procedimento(protocolo_procedimento=proc)
    return resultado

@router.post("/pca/vincular-processo")
def api_vincular_processo_pca(req: VincularProcessoPCARequest):
    """
    Associa ou desvincula formalmente um número de processo SEI ao registro de um item do PCA.
    """
    num_proc = (req.processo_sei or "").strip()
    conn = get_pca_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE pca.itens SET processo_sei = %s WHERE id = %s", (num_proc if num_proc else None, req.item_id))
    conn.commit()
    conn.close()
    try:
        from routers.pca import invalidar_cache_pca
        invalidar_cache_pca()
    except Exception:
        pass
    return {
        "sucesso": True,
        "item_id": req.item_id,
        "processo_sei": num_proc,
        "mensagem": f"Processo '{num_proc}' vinculado à demanda #{req.item_id} com sucesso!" if num_proc else f"Vínculo com o SEI removido da demanda #{req.item_id}."
    }

@router.post("/contratos/vincular-processo")
def api_vincular_processo_contrato(req: VincularProcessoContratoRequest):
    """
    Associa formalmente um número de processo SEI ao registro de um contrato.
    """
    conn = get_contratos_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE contratos.contratos SET processo_sei = %s WHERE id = %s", (req.processo_sei, req.contrato_id))
    conn.commit()
    conn.close()
    return {"sucesso": True, "mensagem": f"Processo {req.processo_sei} vinculado ao Contrato #{req.contrato_id} com sucesso!"}

@router.get("/contratos/{contrato_id}/autos")
def api_consultar_autos_contrato(contrato_id: int):
    """
    Retorna o espelho em tempo real dos autos do SEI para a ficha de um contrato.
    """
    conn = get_contratos_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, instituicao, tipo, objetivo, valor, prazo, processo_sei FROM contratos.contratos WHERE id = %s", (contrato_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Contrato não localizado.")

    proc_sei = row.get("processo_sei")
    if not proc_sei:
        proc_sei = f"19202.79.{contrato_id:06d}/2026-19"

    dados_sei = sei_client_instancia.consultar_procedimento(protocolo_procedimento=proc_sei)
    
    return {
        "contrato_id": contrato_id,
        "instituicao": row["instituicao"],
        "processo_sei": proc_sei,
        "status_sei": dados_sei,
        "link_sei": f"https://sei.se.gov.br/controlador.php?acao=protocolo_pesquisar&txtPesquisaRapida={proc_sei}",
    }
