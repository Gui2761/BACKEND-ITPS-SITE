from fastapi import APIRouter
from datetime import datetime
from services.scraping import buscar_licitacoes_comprasnet_se

router = APIRouter()

COMPRASNET_CACHE = {
    "timestamp": 0,
    "data": []
}

@router.get("/api/licitacoes-comprasnet")
@router.get("/api/comprasnet-se")
def get_licitacoes_comprasnet():
    resultado = buscar_licitacoes_comprasnet_se()
    return {
        "orgao": "ITPS - INSTITUTO TECNOLÓGICO E DE PESQUISAS DO ESTADO DE SERGIPE",
        "modalidade": "DISPENSA POR VALOR",
        "periodo_filtro": "1 Mês (Vigente)",
        "total": len(resultado),
        "resultado": resultado
    }

@router.get("/api/licitacoes-comprasnet/detalhes/{edital_codigo}")
def get_detalhes_licitacao(edital_codigo: str):
    code_clean = edital_codigo.upper().replace("-", "").replace("ITPS", "").replace("/", "").strip()
    
    licitacoes = buscar_licitacoes_comprasnet_se()
    item_encontrado = None
    for l in licitacoes:
        ed_clean = l.get("edital", "").upper().replace("-", "").replace("ITPS", "").replace("/", "").strip()
        if code_clean and (code_clean in ed_clean or ed_clean in code_clean):
            item_encontrado = l
            break
            
    edital_exibicao = item_encontrado["edital"] if item_encontrado else edital_codigo
    objeto_exibicao = item_encontrado["objeto"] if item_encontrado else "PROCESSO DE AQUISIÇÃO / CONTRATAÇÃO ITPS"
    situacao_exibicao = item_encontrado["situacao"] if item_encontrado else "Em disputa"
    prazo_exibicao = item_encontrado["prazo"] if item_encontrado else ""
    link_direto_processo = item_encontrado.get("link", "https://sistema.comprasnet.se.gov.br/publico/ConsultaProcessos.aspx") if item_encontrado else "https://sistema.comprasnet.se.gov.br/publico/ConsultaProcessos.aspx"

    return {
        "orgao": "ITPS - INSTITUTO TECNOLÓGICO E DE PESQUISAS DO ESTADO DE SERGIPE",
        "edital": f"ITPS-{edital_exibicao}",
        "processo_edoc": "COMPRAS.GOV-ITPS",
        "objeto": objeto_exibicao,
        "modalidade": item_encontrado.get("modalidade", "DISPENSA POR VALOR") if item_encontrado else "DISPENSA POR VALOR",
        "etapa_atual": situacao_exibicao,
        "status_cor": "azul",
        "responsavel": {
            "nome": "Leonardo Santos Lima",
            "telefone": "79 3198-8845",
            "email": "gesad@itps.se.gov.br"
        },
        "publicacao": {
            "data_publicacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "inicio_disputa": prazo_exibicao,
            "termino_disputa": prazo_exibicao
        },
        "lances_url": link_direto_processo,
        "anexos": [
            {
                "nome": f"Aviso de Dispensa Eletrônica / Edital {edital_exibicao} (PDF)",
                "url": link_direto_processo
            }
        ],
        "lotes": [
            {
                "lote": 1,
                "itens": [
                    {
                        "item": 1,
                        "descricao": objeto_exibicao,
                        "quantidade": "CONFORME TERMO DE REFERÊNCIA"
                    }
                ]
            }
        ]
    }
