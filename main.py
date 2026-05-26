import os
import time
import requests
import urllib3
import re
import html 
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Desativa os avisos vermelhos de SSL no terminal gerados pelo Proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- CONFIGURAÇÃO DE PROXY DO ITPS ---
# Login genérico de serviço (Auditório) para a API acessar a internet
proxy_url = "http://auditorio.itps:auditorio2023@proxy.itps.gov-se:8080"

os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
os.environ['http_proxy'] = proxy_url
os.environ['https_proxy'] = proxy_url
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1,itps.se.gov.br'
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1,itps.se.gov.br'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VARIÁVEIS DE CACHE GLOBAL ---
cache_iose = {"dados": [], "ultima_atualizacao": 0}
TEMPO_CACHE = 3600  # O robô do Selenium só roda 1 vez por hora (3600 segundos)

# --- SCRAPING: DIÁRIO OFICIAL (IOSE) ---
def realizar_scraping_iose():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    resultados = []
    
    # Filtro automático pelo mês e ano atuais
    agora = datetime.now()
    mes_atual = f"{agora.month:02d}"
    ano_atual = str(agora.year)
    filtro_data = f"/{mes_atual}/{ano_atual}" 
    
    try:
        url_busca = "https://iose.se.gov.br/buscanova/#/p=1&q=ITPS"
        driver.get(url_busca)
        time.sleep(15) # Espera o site do governo carregar
        
        # TÁTICA NOVA: Achar os links (botões) primeiro
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'ver-flip')]")
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if not href: continue
                
                # Sobe na estrutura do site (até 5 níveis) para encontrar a "caixa" que envolve o botão e o texto
                container = link
                texto_caixa = ""
                for _ in range(5):
                    container = container.find_element(By.XPATH, "..")
                    if "Diário publicado em:" in container.text:
                        texto_caixa = container.text
                        break
                
                if texto_caixa:
                    # Achou a caixa! Agora pega a linha exata da data
                    linhas = texto_caixa.split('\n')
                    for linha in linhas:
                        if "Diário publicado em:" in linha:
                            partes = linha.split(" - ")
                            data_pub = partes[0].replace("Diário publicado em:", "").strip()
                            
                            # Verifica se é do mês atual (Filtro)
                            if data_pub.endswith(filtro_data):
                                titulo_pub = " - ".join(partes[1:])
                                
                                # A sua ideia: Adiciona o ?find=ITPS para já cair grifado no PDF
                                link_direto = href
                                if "?find=" not in link_direto:
                                    link_direto = f"{link_direto}?find=ITPS"
                                    
                                # Evita itens duplicados (caso o site tenha 2 botões iguais pro mesmo diário)
                                if not any(r['link'] == link_direto for r in resultados):
                                    resultados.append({"data": data_pub, "titulo": titulo_pub, "link": link_direto})
                            break # Já achou a data nesta caixa, pula pro próximo botão
            except Exception:
                # Se um botão específico der erro, ignora e vai pro próximo sem travar o código
                continue
                    
    except Exception as e:
        print(f"Erro Scraper IOSE: {e}")
    finally:
        driver.quit()
        
    return resultados[:10]

@app.get("/api/diario-oficial")
async def get_diario():
    agora = time.time()
    
    # Se temos dados guardados e passou menos de 1 hora, devolve o Cache instantaneamente
    if cache_iose["dados"] and (agora - cache_iose["ultima_atualizacao"] < TEMPO_CACHE):
        print("Entregando Diário Oficial direto da memória (CACHE) - Super rápido!")
        return {"resultado": cache_iose["dados"]}
        
    # Se o cache estiver vazio ou velho, inicia o robô pesado
    print("Iniciando o Robô Chrome para ler o Diário Oficial...")
    resultados = realizar_scraping_iose()
    
    # Atualiza a memória com os dados novos para os próximos usuários
    if resultados: 
        cache_iose["dados"] = resultados
        cache_iose["ultima_atualizacao"] = agora
        
    return {"resultado": resultados}


# --- API: NOTÍCIAS DO ITPS (TRUQUE DO OPENGRAPH) ---
@app.get("/api/noticias")
async def get_noticias():
    url = "https://itps.se.gov.br/feed/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
            xml = response.text
            
            if "<item>" not in xml: 
                return {"resultado": []}
                
            itens = xml.split("<item>")[1:4] 
            resultados = []
            
            for item in itens:
                item_limpo = html.unescape(item)
                
                titulo = "Sem Título"
                match_t = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_limpo) or re.search(r'<title>(.*?)</title>', item_limpo)
                if match_t: titulo = match_t.group(1).strip()
                
                link = "#"
                match_l = re.search(r'<link>(.*?)</link>', item_limpo)
                if match_l: link = match_l.group(1).strip()
                
                # Visita a página da notícia e pega a foto de capa (og:image)
                imagem_url = "images/Itps.png"
                if link.startswith("http"):
                    try:
                        req_noticia = requests.get(link, headers=headers, timeout=5, verify=False)
                        match_og = re.search(r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\'](https?://[^"\'>]+)["\']', req_noticia.text, re.IGNORECASE)
                        if not match_og: 
                            match_og = re.search(r'<meta\s+content=["\'](https?://[^"\'>]+)["\']\s+(?:property|name)=["\']og:image["\']', req_noticia.text, re.IGNORECASE)
                            
                        if match_og:
                            imagem_url = match_og.group(1)
                    except:
                        pass
                
                data_formatada = ""
                match_d = re.search(r'<pubDate>(.*?)</pubDate>', item_limpo)
                if match_d:
                    try:
                        partes = match_d.group(1).strip().split(' ')
                        if len(partes) >= 4:
                            dia = partes[1]
                            mes_ing = partes[2].lower()
                            ano = partes[3]
                            mapa_meses = {'jan': 'janeiro', 'feb': 'fevereiro', 'mar': 'março', 'apr': 'abril', 'may': 'maio', 'jun': 'junho', 'jul': 'julho', 'aug': 'agosto', 'sep': 'setembro', 'oct': 'outubro', 'nov': 'novembro', 'dec': 'dezembro'}
                            mes_pt = mapa_meses.get(mes_ing, mes_ing)
                            data_formatada = f"{dia} de {mes_pt} de {ano}"
                    except:
                        data_formatada = match_d.group(1)
                        
                resultados.append({
                    "titulo": titulo, "link": link, "imagem": imagem_url, "data": data_formatada
                })
                
            return {"resultado": resultados}
            
    except Exception as e:
        print(f"ERRO AO LER NOTÍCIAS: {str(e)}")
        
    return {"resultado": []}


# ==============================================================================
# --- EXTENSÃO: PROXY DE BANCO DE DADOS PARA CONTRATOS E FOLHA DE PAGAMENTO ---
# ==============================================================================

# Detecção automática: Se estiver no Docker (Linux) usa caminhos mapeados, senão caminhos de rede Windows
if os.path.exists("/app/db_contratos") or os.name == 'posix':
    DB_CONTRATOS_PATH = "/app/db_contratos/banco_contratos.db"
    DB_FOLHA_PATH = "/app/db_folha/folha_itps_v8_rh_sync.db"
else:
    DB_CONTRATOS_PATH = r"\\172.23.6.7\ageplan\Banco de contratos\banco_contratos.db"
    DB_FOLHA_PATH = r"\\172.23.6.7\gerh\1- COAPE\FolhaITPS_Dados\folha_itps_v8_rh_sync.db"

def get_contratos_db():
    conn = sqlite3.connect(DB_CONTRATOS_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_folha_db():
    conn = sqlite3.connect(DB_FOLHA_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

class CategoryModel(BaseModel):
    name: str
    color: str
    group: str


# --- ENDPOINTS: CONTRATOS ---

@app.post("/api/contratos/login")
def contratos_login(req: ContratosLoginRequest):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, name, role FROM users WHERE username = ? AND password = ?", (req.username, req.password))
        user = cursor.fetchone()
        conn.close()
        if user:
            return dict(user)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.get("/api/contratos")
def contratos_listar():
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contratos ORDER BY id DESC")
        contratos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"contratos": contratos}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/contratos")
def contratos_criar(c: ContratoModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contratos (instituicao, tipo, objetivo, valor, valor_gasto, prazo, caminho_arquivo) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, c.caminho_arquivo)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"id": new_id, "success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/contratos/{id}")
def contratos_atualizar(id: int, c: ContratoModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contratos SET instituicao = ?, tipo = ?, objetivo = ?, valor = ?, valor_gasto = ?, prazo = ?, caminho_arquivo = ? WHERE id = ?",
            (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, c.caminho_arquivo, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/contratos/{id}")
def contratos_deletar(id: int):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Categorias
@app.get("/api/contratos/categories")
def contratos_categories_listar():
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories ORDER BY name ASC")
        categories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"categories": categories}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/contratos/categories")
def contratos_categories_criar(cat: CategoryModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO categories (name, color, 'group') VALUES (?, ?, ?)",
            (cat.name, cat.color, cat.group)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/contratos/categories/{id}")
def contratos_categories_atualizar(id: int, cat: CategoryModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE categories SET name = ?, color = ?, 'group' = ? WHERE id = ?",
            (cat.name, cat.color, cat.group, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/contratos/categories/{name}")
def contratos_categories_deletar(name: str):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")


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

@app.post("/api/folha/login")
def folha_login(req: FolhaLoginRequest):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, permissao FROM usuarios WHERE usuario = ? AND senha = ?", (req.usuario, req.senha))
        user = cursor.fetchone()
        conn.close()
        if user:
            return dict(user)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.get("/api/folha/funcionarios")
def folha_funcionarios_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM funcionarios ORDER BY nome ASC")
        funcionarios = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"funcionarios": funcionarios}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/folha/funcionarios")
def folha_funcionarios_criar(f: FuncionarioModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO funcionarios (nome, cpf, rg, vinculo, banco, agencia, conta, cargo_nome, locacao, percentual, valor_sipes, pensao, outros, acrescimos, tem_inss, tem_irrf, irrf_sipes_real, irrf_manual, dias_trabalhados, previdencia_rpps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f.nome, f.cpf, f.rg, f.vinculo, f.banco, f.agencia, f.conta, f.cargo_nome, f.locacao, f.percentual, f.valor_sipes, f.pensao, f.outros, f.acrescimos, f.tem_inss, f.tem_irrf, f.irrf_sipes_real, f.irrf_manual, f.dias_trabalhados, f.previdencia_rpps)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"id": new_id, "success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/folha/funcionarios/{id}")
def folha_funcionarios_atualizar(id: int, f: FuncionarioModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE funcionarios SET nome = ?, cpf = ?, rg = ?, vinculo = ?, banco = ?, agencia = ?, conta = ?, cargo_nome = ?, locacao = ?, percentual = ?, valor_sipes = ?, pensao = ?, outros = ?, acrescimos = ?, tem_inss = ?, tem_irrf = ?, irrf_sipes_real = ?, irrf_manual = ?, dias_trabalhados = ?, previdencia_rpps = ? WHERE id = ?",
            (f.nome, f.cpf, f.rg, f.vinculo, f.banco, f.agencia, f.conta, f.cargo_nome, f.locacao, f.percentual, f.valor_sipes, f.pensao, f.outros, f.acrescimos, f.tem_inss, f.tem_irrf, f.irrf_sipes_real, f.irrf_manual, f.dias_trabalhados, f.previdencia_rpps, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/folha/funcionarios/{id}")
def folha_funcionarios_deletar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM funcionarios WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Cargos
@app.get("/api/folha/cargos")
def folha_cargos_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cargos ORDER BY nome ASC")
        cargos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"cargos": cargos}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/folha/cargos")
def folha_cargos_criar(c: CargoModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cargos (nome, locacao, percentual_padrao) VALUES (?, ?, ?)",
            (c.nome, c.locacao, c.percentual_padrao)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"id": new_id, "success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/folha/cargos/{id}")
def folha_cargos_atualizar(id: int, c: CargoModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cargos SET nome = ?, locacao = ?, percentual_padrao = ? WHERE id = ?",
            (c.nome, c.locacao, c.percentual_padrao, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/folha/cargos/{id}")
def folha_cargos_deletar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cargos WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Configurações & Tabelas Fiscais
@app.get("/api/folha/config")
def folha_config_obter():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM config_geral")
        geral = {row['chave']: row['valor'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT * FROM config_inss ORDER BY limite ASC")
        inss = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM config_irrf ORDER BY limite ASC")
        irrf = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return {"geral": geral, "inss": inss, "irrf": irrf}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/folha/config/geral")
def folha_config_geral_salvar(c: ConfigGeralModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO config_geral (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (c.chave, c.valor)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/folha/config/inss/{id}")
def folha_config_inss_atualizar(id: int, c: ConfigInssModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE config_inss SET limite = ?, aliquota = ?, deducao = ? WHERE id = ?",
            (c.limite, c.aliquota, c.deducao, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/folha/config/irrf/{id}")
def folha_config_irrf_atualizar(id: int, c: ConfigIrrfModel):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE config_irrf SET limite = ?, aliquota = ?, deducao = ? WHERE id = ?",
            (c.limite, c.aliquota, c.deducao, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/folha/config/reset")
def folha_config_reset():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM config_inss")
        cursor.execute("DELETE FROM config_irrf")
        
        inss_defaults = [
            (1621.00, 7.5, 0.0),
            (2902.84, 9.0, 24.32),
            (4354.27, 12.0, 111.40),
            (8475.55, 14.0, 198.49)
        ]
        cursor.executemany("INSERT INTO config_inss (limite, aliquota, deducao) VALUES (?, ?, ?)", inss_defaults)
        
        irrf_defaults = [
            (2428.80, 0.0, 0.0),
            (2826.65, 7.5, 182.16),
            (3751.05, 15.0, 394.16),
            (4664.68, 22.5, 675.49),
            (999999999.00, 27.5, 908.73)
        ]
        cursor.executemany("INSERT INTO config_irrf (limite, aliquota, deducao) VALUES (?, ?, ?)", irrf_defaults)
        
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Fechamentos
@app.get("/api/folha/folhas")
def folha_historico_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folhas_salvas ORDER BY mes_ano DESC")
        folhas = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"folhas": folhas}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.get("/api/folha/folha-detalhes/{id}")
def folha_detalhes_listar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folha_historico_detalhe WHERE folha_salva_id = ? ORDER BY nome ASC", (id,))
        detalhes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"detalhes": detalhes}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/folha/fechar")
def folha_historico_fechar(req: FecharFolhaRequest):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        
        cursor.execute("BEGIN TRANSACTION")
        
        cursor.execute("SELECT id FROM folhas_salvas WHERE mes_ano = ?", (req.mes_ano,))
        antigo = cursor.fetchone()
        if antigo:
            antigo_id = antigo['id']
            cursor.execute("DELETE FROM folha_historico_detalhe WHERE folha_salva_id = ?", (antigo_id,))
            cursor.execute("DELETE FROM folhas_salvas WHERE id = ?", (antigo_id,))
            
        cursor.execute(
            "INSERT INTO folhas_salvas (mes_ano, data_fechamento, criado_por) VALUES (?, ?, ?)",
            (req.mes_ano, datetime.now().isoformat()[:19].replace('T', ' '), req.criado_por)
        )
        folha_id = cursor.lastrowid
        
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
            "INSERT INTO folha_historico_detalhe (folha_salva_id, funcionario_id, nome, cpf, cargo_nome, locacao, vinculo, percentual, valor_sipes, pensao, outros, acrescimos, bruto, inss, irrf, liquido, dias_trabalhados, previdencia_rpps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            detalhes_tuplas
        )
        
        cursor.execute("COMMIT")
        conn.close()
        return {"id": folha_id, "success": True}
    except sqlite3.Error as e:
        try:
            cursor.execute("ROLLBACK")
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/folha/folhas/{id}")
def folha_historico_deletar(id: int):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("DELETE FROM folha_historico_detalhe WHERE folha_salva_id = ?", (id,))
        cursor.execute("DELETE FROM folhas_salvas WHERE id = ?", (id,))
        cursor.execute("COMMIT")
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        try:
            cursor.execute("ROLLBACK")
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Auditoria (Logs)
@app.get("/api/folha/logs")
def folha_logs_listar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT 1000")
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"logs": logs}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/folha/logs")
def folha_logs_criar(req: LogRequest):
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO auditoria (usuario, acao, data_hora, detalhes) VALUES (?, ?, ?, ?)",
            (req.usuario, req.acao, datetime.now().isoformat()[:19].replace('T', ' '), req.detalhes)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/folha/logs")
def folha_logs_limpar():
    try:
        conn = get_folha_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM auditoria")
        conn.commit()
        conn.close()
        return {"success": True}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    # AVISO PARA TI: O host 0.0.0.0 permite que o servidor seja acessado por outras máquinas na rede local
    uvicorn.run(app, host="0.0.0.0", port=8000)