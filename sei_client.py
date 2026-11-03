import os
import requests
import xml.etree.ElementTree as ET
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime


class SEISergipeClient:
    """
    Cliente SOAP de integração com o SEI Sergipe (VM 172.23.6.223).
    Implementa as operações oficiais do WSDL conforme manual do SEI:
    - gerarProcedimento
    - incluirDocumento
    - consultarProcedimento
    - enviarProcesso
    - listarUnidades
    """

    def __init__(
        self,
        wsdl_url: Optional[str] = None,
        sigla_sistema: str = "ITPS-PCA",
        identificacao_servico: str = "CHAVE_LOCAL_TESTE_ITPS",
        mock_mode: bool = False
    ):
        self.wsdl_url = wsdl_url or os.getenv(
            "SEI_WSDL_URL",
            "http://172.23.6.223:8000/sei/controlador_ws.php?servico=sei"
        )
        self.sigla_sistema = sigla_sistema or os.getenv("SEI_SIGLA_SISTEMA", "ITPS-PCA")
        self.identificacao_servico = identificacao_servico or os.getenv("SEI_CHAVE_ACESSO", "CHAVE_LOCAL_TESTE_ITPS")
        self.mock_mode = mock_mode

    def _enviar_soap(self, soap_action: str, soap_body: str) -> Dict[str, Any]:
        """Envia uma requisição SOAP genérica ao endpoint WSDL do SEI."""
        soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:sei="Sei">
   <soapenv:Header/>
   <soapenv:Body>
      {soap_body}
   </soapenv:Body>
</soapenv:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': soap_action
        }

        try:
            response = requests.post(
                self.wsdl_url,
                data=soap_envelope.encode('utf-8'),
                headers=headers,
                timeout=15
            )
            return {
                "sucesso": response.status_code == 200,
                "status_http": response.status_code,
                "resposta_xml": response.text,
                "mensagem": "Comunicação SOAP realizada" if response.status_code == 200 else f"Erro HTTP {response.status_code}"
            }
        except Exception as e:
            return {
                "sucesso": False,
                "status_http": 0,
                "erro": f"Erro de conexão SOAP: {str(e)}"
            }

    # =========================================================================
    # 1. gerarProcedimento — Autua (cria) um novo processo no SEI
    # Campos obrigatórios conforme manual oficial:
    #   - SiglaSistema, IdentificacaoServico, IdUnidade
    #   - Procedimento: IdTipoProcedimento, Especificacao, NivelAcesso
    #   - Interessados (array), Assuntos (array)
    # =========================================================================
    def gerar_procedimento(
        self,
        id_unidade: int = 110000001,
        id_tipo_procedimento: str = "100000050",
        especificacao: str = "Processo PCA ITPS",
        interessados: Optional[List[str]] = None,
        nivel_acesso: int = 0,
        id_hipotese_legal: Optional[str] = None,
        observacao: Optional[str] = None,
        unidades_envio: Optional[List[int]] = None,
        sin_manter_aberto: str = "S",
        sin_enviar_email: str = "N"
    ) -> Dict[str, Any]:
        """
        Método SOAP: gerarProcedimento
        Cria um novo processo administrativo no SEI Sergipe.
        """
        if self.mock_mode:
            import random
            num_random = random.randint(100000, 999999)
            id_proc = random.randint(10000, 99999)
            processo_formatado = f"13801.79.{num_random}/2027-19"
            return {
                "sucesso": True,
                "mock": True,
                "id_procedimento": str(id_proc),
                "procedimento_formatado": processo_formatado,
                "numero_processo": processo_formatado,
                "link_acesso": f"http://172.23.6.223:8000/sei/controlador.php?acao=procedimento_trabalhar&id_procedimento={id_proc}",
                "mensagem": "Processo gerado com sucesso (mock)!",
                "status_code": 200
            }

        # Montar bloco de Interessados
        interessados_list = interessados or ["ITPS - Instituto Tecnológico e de Pesquisas do Estado de Sergipe"]
        interessados_xml = ""
        for nome in interessados_list:
            interessados_xml += f"""
            <item>
               <Nome>{nome}</Nome>
            </item>"""

        # Montar bloco de UnidadesEnvio (tramitação automática pós-autuação)
        unidades_envio_xml = ""
        if unidades_envio:
            for uid in unidades_envio:
                unidades_envio_xml += f"<item>{uid}</item>"

        # Hipótese Legal (obrigatória se nível de acesso = Restrito ou Sigiloso)
        hipotese_xml = f"<IdHipoteseLegal>{id_hipotese_legal}</IdHipoteseLegal>" if id_hipotese_legal else ""

        observacao_xml = f"<Observacao>{observacao}</Observacao>" if observacao else ""

        soap_body = f"""<sei:gerarProcedimento>
         <SiglaSistema>{self.sigla_sistema}</SiglaSistema>
         <IdentificacaoServico>{self.identificacao_servico}</IdentificacaoServico>
         <IdUnidade>{id_unidade}</IdUnidade>
         <Procedimento>
            <IdTipoProcedimento>{id_tipo_procedimento}</IdTipoProcedimento>
            <Especificacao>{especificacao}</Especificacao>
            <NivelAcesso>{nivel_acesso}</NivelAcesso>
            {hipotese_xml}
            {observacao_xml}
            <Interessados>{interessados_xml}
            </Interessados>
            <Assuntos></Assuntos>
         </Procedimento>
         <Documentos></Documentos>
         <ProcedimentosRelacionados></ProcedimentosRelacionados>
         <UnidadesEnvio>{unidades_envio_xml}</UnidadesEnvio>
         <SinManterAbertoUnidade>{sin_manter_aberto}</SinManterAbertoUnidade>
         <SinEnviarEmailNotificacao>{sin_enviar_email}</SinEnviarEmailNotificacao>
      </sei:gerarProcedimento>"""

        resultado = self._enviar_soap("gerarProcedimento", soap_body)
        resultado["mock"] = False
        resultado["operacao"] = "gerarProcedimento"
        resultado["parametros_enviados"] = {
            "IdTipoProcedimento": id_tipo_procedimento,
            "Especificacao": especificacao,
            "NivelAcesso": nivel_acesso,
            "Interessados": interessados_list,
            "IdUnidade": id_unidade
        }
        return resultado

    # =========================================================================
    # 2. incluirDocumento — Anexa um documento a um processo existente
    # Tipos: 'R' = Gerado/Interno (HTML), 'E' = Externo (Upload PDF)
    # =========================================================================
    def incluir_documento(
        self,
        id_unidade: int = 110000001,
        protocolo_procedimento: str = "",
        id_serie: str = "100000001",
        tipo: str = "R",
        descricao: str = "Documento de Formalização da Demanda - DFD",
        conteudo_html: Optional[str] = None,
        nome_arquivo: Optional[str] = None,
        conteudo_arquivo_base64: Optional[str] = None,
        nivel_acesso: int = 0,
        data_documento: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Método SOAP: incluirDocumento
        Anexa um documento (DFD, ETP, Despacho, TR) a um processo no SEI.
        """
        if self.mock_mode:
            import random
            doc_id = random.randint(100000, 999999)
            return {
                "sucesso": True,
                "mock": True,
                "id_documento": str(doc_id),
                "numero_documento": str(random.randint(1000, 9999)),
                "link_acesso": f"http://172.23.6.223:8000/sei/controlador.php?acao=documento_visualizar&id_documento={doc_id}",
                "mensagem": f"Documento '{descricao}' incluído com sucesso no processo {protocolo_procedimento} (mock)!",
                "status_code": 200
            }

        data_doc = data_documento or datetime.now().strftime("%d/%m/%Y")

        # Conteúdo: HTML base64 para tipo 'R', ou binário base64 para tipo 'E'
        conteudo_xml = ""
        nome_arquivo_xml = ""
        if tipo == "R" and conteudo_html:
            conteudo_b64 = base64.b64encode(conteudo_html.encode('utf-8')).decode('utf-8')
            conteudo_xml = f"<Conteudo>{conteudo_b64}</Conteudo>"
        elif tipo == "E" and conteudo_arquivo_base64:
            conteudo_xml = f"<Conteudo>{conteudo_arquivo_base64}</Conteudo>"
            nome_arquivo_xml = f"<NomeArquivo>{nome_arquivo or 'documento.pdf'}</NomeArquivo>"

        soap_body = f"""<sei:incluirDocumento>
         <SiglaSistema>{self.sigla_sistema}</SiglaSistema>
         <IdentificacaoServico>{self.identificacao_servico}</IdentificacaoServico>
         <IdUnidade>{id_unidade}</IdUnidade>
         <Documento>
            <Tipo>{tipo}</Tipo>
            <IdProcedimento></IdProcedimento>
            <ProtocoloProcedimento>{protocolo_procedimento}</ProtocoloProcedimento>
            <IdSerie>{id_serie}</IdSerie>
            <Descricao>{descricao}</Descricao>
            <Data>{data_doc}</Data>
            <NivelAcesso>{nivel_acesso}</NivelAcesso>
            {conteudo_xml}
            {nome_arquivo_xml}
         </Documento>
      </sei:incluirDocumento>"""

        resultado = self._enviar_soap("incluirDocumento", soap_body)
        resultado["mock"] = False
        resultado["operacao"] = "incluirDocumento"
        resultado["parametros_enviados"] = {
            "ProtocoloProcedimento": protocolo_procedimento,
            "Tipo": tipo,
            "Descricao": descricao,
            "IdSerie": id_serie,
            "NivelAcesso": nivel_acesso
        }
        return resultado

    # =========================================================================
    # 3. consultarProcedimento — Retorna dados e andamentos do processo
    # =========================================================================
    def consultar_procedimento(
        self,
        protocolo_procedimento: str,
        id_unidade: int = 110000001,
        sin_retornar_assuntos: str = "S",
        sin_retornar_interessados: str = "S",
        sin_retornar_ultimo_andamento: str = "S",
        sin_retornar_unidades_aberto: str = "S"
    ) -> Dict[str, Any]:
        """
        Método SOAP: consultarProcedimento
        Retorna andamento, status e documentos do processo no SEI.
        """
        if self.mock_mode:
            return {
                "sucesso": True,
                "mock": True,
                "protocolo": protocolo_procedimento,
                "unidade_atual": "AGEPLAN - ITPS",
                "andamento_atual": "Processo em Instrução Inicial / Análise de Demanda PCA",
                "data_autuacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "interessados": ["ITPS - Instituto Tecnológico e de Pesquisas do Estado de Sergipe"],
                "status_code": 200
            }

        soap_body = f"""<sei:consultarProcedimento>
         <SiglaSistema>{self.sigla_sistema}</SiglaSistema>
         <IdentificacaoServico>{self.identificacao_servico}</IdentificacaoServico>
         <IdUnidade>{id_unidade}</IdUnidade>
         <ProtocoloProcedimento>{protocolo_procedimento}</ProtocoloProcedimento>
         <SinRetornarAssuntos>{sin_retornar_assuntos}</SinRetornarAssuntos>
         <SinRetornarInteressados>{sin_retornar_interessados}</SinRetornarInteressados>
         <SinRetornarObservacoes>N</SinRetornarObservacoes>
         <SinRetornarAndamentoGeracao>S</SinRetornarAndamentoGeracao>
         <SinRetornarAndamentoConclusao>N</SinRetornarAndamentoConclusao>
         <SinRetornarUltimoAndamento>{sin_retornar_ultimo_andamento}</SinRetornarUltimoAndamento>
         <SinRetornarUnidadesProcedimentoAberto>{sin_retornar_unidades_aberto}</SinRetornarUnidadesProcedimentoAberto>
         <SinRetornarProcedimentosRelacionados>N</SinRetornarProcedimentosRelacionados>
         <SinRetornarProcedimentosAnexados>N</SinRetornarProcedimentosAnexados>
      </sei:consultarProcedimento>"""

        resultado = self._enviar_soap("consultarProcedimento", soap_body)
        resultado["operacao"] = "consultarProcedimento"
        resultado["protocolo"] = protocolo_procedimento
        return resultado

    # =========================================================================
    # 4. enviarProcesso — Tramita o processo para outra unidade
    # =========================================================================
    def enviar_processo(
        self,
        protocolo_procedimento: str,
        id_unidade_origem: int = 110000001,
        unidades_destino: Optional[List[int]] = None,
        sin_manter_aberto: str = "S",
        sin_remover_anotacao: str = "N",
        sin_enviar_email: str = "S",
        data_retorno: Optional[str] = None,
        dias_retorno: Optional[int] = None,
        sin_dias_uteis: str = "S"
    ) -> Dict[str, Any]:
        """
        Método SOAP: enviarProcesso
        Tramita o processo de uma unidade para outra(s) no SEI.
        """
        if self.mock_mode:
            return {
                "sucesso": True,
                "mock": True,
                "protocolo": protocolo_procedimento,
                "unidades_destino": unidades_destino or [],
                "mensagem": f"Processo {protocolo_procedimento} tramitado com sucesso (mock)!",
                "status_code": 200
            }

        unidades_xml = ""
        for uid in (unidades_destino or []):
            unidades_xml += f"<item>{uid}</item>"

        retorno_xml = ""
        if data_retorno:
            retorno_xml = f"<DataRetornoProgramado>{data_retorno}</DataRetornoProgramado>"
        elif dias_retorno:
            retorno_xml = f"""<DiasRetornoProgramado>{dias_retorno}</DiasRetornoProgramado>
         <SinDiasUteisRetornoProgramado>{sin_dias_uteis}</SinDiasUteisRetornoProgramado>"""

        soap_body = f"""<sei:enviarProcesso>
         <SiglaSistema>{self.sigla_sistema}</SiglaSistema>
         <IdentificacaoServico>{self.identificacao_servico}</IdentificacaoServico>
         <IdUnidade>{id_unidade_origem}</IdUnidade>
         <ProtocoloProcedimento>{protocolo_procedimento}</ProtocoloProcedimento>
         <UnidadesDestino>{unidades_xml}</UnidadesDestino>
         <SinManterAbertoUnidade>{sin_manter_aberto}</SinManterAbertoUnidade>
         <SinRemoverAnotacao>{sin_remover_anotacao}</SinRemoverAnotacao>
         <SinEnviarEmailNotificacao>{sin_enviar_email}</SinEnviarEmailNotificacao>
         {retorno_xml}
      </sei:enviarProcesso>"""

        resultado = self._enviar_soap("enviarProcesso", soap_body)
        resultado["operacao"] = "enviarProcesso"
        resultado["protocolo"] = protocolo_procedimento
        resultado["unidades_destino"] = unidades_destino or []
        return resultado

    # =========================================================================
    # 5. listarUnidades — Retorna a árvore de unidades do órgão
    # =========================================================================
    def listar_unidades(
        self,
        id_tipo_procedimento: Optional[str] = None,
        id_serie: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Método SOAP: listarUnidades
        Retorna as unidades cadastradas no SEI do órgão.
        """
        if self.mock_mode:
            return {
                "sucesso": True,
                "mock": True,
                "unidades": [
                    {"id": 110000001, "sigla": "AGEPLAN", "descricao": "Assessoria de Gestão e Planejamento"},
                    {"id": 110000002, "sigla": "GECONF", "descricao": "Gerência de Contratos e Finanças"},
                    {"id": 110000003, "sigla": "GERAD", "descricao": "Gerência de Administração"},
                    {"id": 110000004, "sigla": "LABWIN", "descricao": "Laboratório de Águas e Efluentes"},
                    {"id": 110000005, "sigla": "METROLOGIA", "descricao": "Divisão de Metrologia Legal"},
                    {"id": 110000006, "sigla": "BROMATO", "descricao": "Laboratório de Bromatologia"},
                    {"id": 110000007, "sigla": "MICRO", "descricao": "Laboratório de Microbiologia"},
                    {"id": 110000008, "sigla": "GEAAD", "descricao": "Gerência de Apoio Administrativo"},
                    {"id": 110000009, "sigla": "PRESIDENCIA", "descricao": "Presidência do ITPS"},
                ],
                "status_code": 200
            }

        filtro_tipo = f"<IdTipoProcedimento>{id_tipo_procedimento}</IdTipoProcedimento>" if id_tipo_procedimento else "<IdTipoProcedimento></IdTipoProcedimento>"
        filtro_serie = f"<IdSerie>{id_serie}</IdSerie>" if id_serie else "<IdSerie></IdSerie>"

        soap_body = f"""<sei:listarUnidades>
         <SiglaSistema>{self.sigla_sistema}</SiglaSistema>
         <IdentificacaoServico>{self.identificacao_servico}</IdentificacaoServico>
         {filtro_tipo}
         {filtro_serie}
      </sei:listarUnidades>"""

        resultado = self._enviar_soap("listarUnidades", soap_body)
        resultado["operacao"] = "listarUnidades"
        return resultado

    # =========================================================================
    # UTILITÁRIO: Gera o HTML da DFD para inclusão como documento interno
    # =========================================================================
    def gerar_html_dfd(
        self,
        numero_processo: str,
        numero_dfd: str,
        setor_requisitante: str,
        descricao_objeto: str,
        codigo_item: str = "",
        quantidade: int = 1,
        unidade_medida: str = "Unidade",
        valor_unitario: float = 0.0,
        valor_total: float = 0.0,
        justificativa: str = "",
        responsavel: str = "GILVAN SILVA"
    ) -> str:
        """Gera o HTML do Documento de Formalização da Demanda (DFD) no formato oficial do SEI."""
        data_atual = datetime.now().strftime("%d/%m/%Y às %H:%M")
        return f"""<html>
<body style="font-family: Arial, sans-serif; font-size: 12px; color: #000;">
<div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
  <h3 style="margin: 0; font-size: 14px;">GOVERNO DO ESTADO DE SERGIPE</h3>
  <h4 style="margin: 2px 0; font-size: 12px;">INSTITUTO TECNOLÓGICO E DE PESQUISAS DO ESTADO DE SERGIPE - ITPS</h4>
  <p style="margin: 2px 0; font-size: 11px;">Rua Campo do Brito, 371 — Aracaju/SE | CNPJ: 13.801.791/0001-19</p>
</div>

<div style="text-align: center; margin-bottom: 16px;">
  <h2 style="margin: 0; font-size: 15px; text-decoration: underline;">DOCUMENTO DE FORMALIZAÇÃO DA DEMANDA — DFD Nº {numero_dfd}/2027</h2>
  <p style="margin: 4px 0; font-size: 12px;">PROCESSO SEI Nº: {numero_processo} | EXERCÍCIO: PCA 2027</p>
</div>

<p><strong>1. SETOR REQUISITANTE:</strong> {setor_requisitante}</p>
<p><strong>2. OBJETO DA CONTRATAÇÃO:</strong> {descricao_objeto}</p>
{f'<p><strong>3. CÓDIGO DO ITEM (CATMAT/CATSER):</strong> {codigo_item}</p>' if codigo_item else ''}

<h4 style="margin-top: 16px; font-size: 13px;">4. DETALHAMENTO DO ITEM:</h4>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 12px;">
  <thead>
    <tr style="background: #f1f5f9;">
      <th>Código</th><th>Descrição</th><th>Setor</th><th>Qtd</th><th>Unid.</th><th>Valor Unit.</th><th>Valor Total</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>{codigo_item or '—'}</td>
      <td>{descricao_objeto}</td>
      <td>{setor_requisitante}</td>
      <td>{quantidade}</td>
      <td>{unidade_medida}</td>
      <td>R$ {valor_unitario:,.2f}</td>
      <td><strong>R$ {valor_total:,.2f}</strong></td>
    </tr>
  </tbody>
</table>

<p><strong>5. VALOR TOTAL ESTIMADO:</strong> <strong>R$ {valor_total:,.2f}</strong></p>
<p><strong>6. JUSTIFICATIVA:</strong> {justificativa or 'Aquisição indispensável para a manutenção das atividades finalísticas do ITPS.'}</p>
<p><strong>7. ALINHAMENTO PEI:</strong> Meta PEI-2027 — Manter 100% dos laboratórios acreditados e operacionais.</p>

<hr style="margin-top: 32px; border: none; border-top: 1px dashed #999;">
<p style="font-size: 11px; color: #333;">
  <strong>Documento assinado eletronicamente por {responsavel}</strong>, em {data_atual}, conforme decreto estadual.<br>
  A autenticidade pode ser conferida em https://seisergipe.se.gov.br/autenticidade
</p>
</body>
</html>"""
