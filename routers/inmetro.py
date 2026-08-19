import os
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from core.database import get_folha_db

router = APIRouter()

INMETRO_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "inmetro_data.json")

def carregar_dados_inmetro():
    if os.path.exists(INMETRO_JSON_PATH):
        try:
            with open(INMETRO_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("Erro ao carregar inmetro_data.json:", e)
    return {}

def salvar_dados_inmetro(dados):
    try:
        dados["ultima_atualizacao"] = datetime.now().isoformat()
        with open(INMETRO_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("Erro ao salvar inmetro_data.json:", e)
        return False

@router.get("/api/inmetro/data")
def get_inmetro_data():
    data = carregar_dados_inmetro()
    if not data:
        raise HTTPException(status_code=404, detail="Dados do INMETRO não encontrados.")
    return data

@router.get("/api/dashboard-consolidado")
def get_dashboard_consolidado():
    data = carregar_dados_inmetro()
    if not data:
        data = {}

    inmetro_list = data.get("inmetro", [])
    contratos_list = data.get("contratos", [])
    pca_list = data.get("pca", [])
    folha_list = data.get("folha", [])
    labwin_list = data.get("labwin", [])

    tot_ver_plan = sum(item.get("planejado", 0) for item in inmetro_list)
    tot_ver_real = sum(item.get("realizado", 0) for item in inmetro_list)
    taxa_ver = round((tot_ver_real / tot_ver_plan * 100), 1) if tot_ver_plan > 0 else 0.0

    tot_contratos_valor = sum(item.get("valor", 0.0) for item in contratos_list)
    alertas_cnt = sum(1 for item in contratos_list if "Alerta" in item.get("status", ""))
    tot_contratos_cnt = len(contratos_list)

    tot_pca_valor = sum(item.get("valor", 0.0) for item in pca_list)
    tot_pca_itens = sum(item.get("itens_qtd", 0) for item in pca_list)

    tot_servidores = sum(item.get("servidores_qtd", 0) for item in folha_list)
    tot_folha_bruta = sum(item.get("custo_bruto", 0.0) for item in folha_list)

    tot_laudos = sum(item.get("laudos_qtd", 0) for item in labwin_list)
    tot_arrecadado_lab = sum(item.get("boletos_quitados", 0.0) for item in labwin_list)

    # Tenta obter dados exatos e dinâmicos do Banco de Dados Postgres (bd_intranet)
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        # 1. Consulta Folha Real
        cursor.execute("SELECT COUNT(*) as total_servidores, COALESCE(SUM(valor_sipes), 0) as total_sipes FROM folha.funcionarios")
        row_folha = cursor.fetchone()
        if row_folha and row_folha['total_servidores'] > 0:
            tot_servidores = row_folha['total_servidores']
            tot_folha_bruta = float(row_folha['total_sipes'])

        # 2. Consulta Contratos Real
        cursor.execute("SELECT COUNT(*) as total_contratos, COALESCE(SUM(valor), 0) as valor_global FROM contratos.contratos")
        row_contratos = cursor.fetchone()
        if row_contratos and row_contratos['total_contratos'] > 0:
            tot_contratos_cnt = row_contratos['total_contratos']
            tot_contratos_valor = float(row_contratos['valor_global'])

        # 3. Consulta PCA Real
        cursor.execute("SELECT COUNT(*) as total_itens, COALESCE(SUM(valor_total), 0) as valor_total_estimado FROM pca.itens")
        row_pca = cursor.fetchone()
        if row_pca and row_pca['total_itens'] > 0:
            tot_pca_itens = row_pca['total_itens']
            tot_pca_valor = float(row_pca['valor_total_estimado'])

        conn.close()
    except Exception as e:
        print("Aviso: Consulta direta ao Postgres do ITPS falhou, utilizando cache estruturado:", e)

    return {
        "orgao": "ITPS - Instituto Tecnológico e de Pesquisas do Estado de Sergipe",
        "data_atualizacao": data.get("ultima_atualizacao", datetime.now().isoformat()),
        "pilares": {
            "inmetro": {
                "total_verificacoes_planejadas": tot_ver_plan,
                "total_verificacoes_realizadas": tot_ver_real,
                "taxa_realizacao_verificacoes": taxa_ver
            },
            "contratos": {
                "total_ativos": tot_contratos_cnt,
                "valor_global": tot_contratos_valor,
                "alertas_vigencia": alertas_cnt
            },
            "pca": {
                "total_itens": tot_pca_itens,
                "valor_total_estimado": tot_pca_valor
            },
            "folha": {
                "total_servidores": tot_servidores,
                "custo_bruto_mensal": tot_folha_bruta
            },
            "labwin": {
                "total_laudos": tot_laudos,
                "valor_arrecadado": tot_arrecadado_lab,
                "taxa_recebimento_media": 95.5
            }
        },
        "detalhes": data
    }

class AdminItemSave(BaseModel):
    pilar: str  # 'inmetro', 'contratos', 'pca', 'folha'
    item: Dict[str, Any]

@router.post("/api/admin/salvar-item")
def admin_salvar_item(data_input: AdminItemSave):
    dados = carregar_dados_inmetro()
    pilar = data_input.pilar
    item = data_input.item

    if pilar not in dados:
        dados[pilar] = []

    # Procura por ID para atualizar ou cria novo ID
    lista = dados[pilar]
    item_id = item.get("id")
    
    if item_id:
        # Atualiza existente
        updated = False
        for i, existing in enumerate(lista):
            if existing.get("id") == item_id:
                lista[i] = item
                updated = True
                break
        if not updated:
            lista.append(item)
    else:
        # Cria novo ID
        max_id = max((x.get("id", 0) for x in lista), default=0)
        item["id"] = max_id + 1
        lista.append(item)

    salvar_dados_inmetro(dados)
    return {"success": True, "message": f"Item salvo no pilar '{pilar}' com sucesso!", "dados": dados}

class AdminItemDelete(BaseModel):
    pilar: str
    id: int

@router.post("/api/admin/deletar-item")
def admin_deletar_item(data_input: AdminItemDelete):
    dados = carregar_dados_inmetro()
    pilar = data_input.pilar
    item_id = data_input.id

    if pilar in dados:
        dados[pilar] = [x for x in dados[pilar] if x.get("id") != item_id]
        salvar_dados_inmetro(dados)

    return {"success": True, "message": f"Item {item_id} removido com sucesso!", "dados": dados}

@router.post("/api/admin/salvar-base-completa")
def admin_salvar_base_completa(novos_dados: Dict[str, Any]):
    salvar_dados_inmetro(novos_dados)
    return {"success": True, "message": "Base de dados completa atualizada com sucesso!", "dados": novos_dados}

@router.post("/api/inmetro/upload")
async def upload_inmetro_file(file: UploadFile = File(...)):
    if not file.filename.endswith(('.json', '.csv', '.xlsx')):
        raise HTTPException(status_code=400, detail="Apenas arquivos .json, .csv ou .xlsx são permitidos.")
    
    content = await file.read()
    if file.filename.endswith('.json'):
        try:
            novos_dados = json.loads(content.decode('utf-8'))
            salvar_dados_inmetro(novos_dados)
            return {"success": True, "message": "Base de dados atualizada via JSON!", "dados": novos_dados}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro ao processar JSON: {str(e)}")
    else:
        return {"success": True, "message": f"Arquivo {file.filename} recebido com sucesso!", "tamanho_bytes": len(content)}
