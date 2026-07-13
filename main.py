import os
import time
import requests
import urllib3
import re
import html 
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Desativa os avisos vermelhos de SSL no terminal gerados pelo Proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from fastapi import FastAPI, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- CONFIGURAÇÃO DE PROXY DO ITPS ---
proxy_url = "http://auditorio.itps:auditorio2023@proxy.itps.gov-se:8080"

os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
os.environ['http_proxy'] = proxy_url
os.environ['https_proxy'] = proxy_url
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1,itps.se.gov.br,172.23.6.109'
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1,itps.se.gov.br,172.23.6.109'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÕES DE CONEXÃO POSTGRES ---
PG_HOST = "172.23.6.109"
PG_PORT = 5432
PG_USER = "geinform"
PG_PASSWORD = "intr@bd109"
PG_DB = "bd_intranet"

def get_contratos_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

def get_folha_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

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
        
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'ver-flip')]")
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if not href: continue
                
                container = link
                texto_caixa = ""
                for _ in range(5):
                    container = container.find_element(By.XPATH, "..")
                    if "Diário publicado em:" in container.text:
                        texto_caixa = container.text
                        break
                
                if texto_caixa:
                    linhas = texto_caixa.split('\n')
                    for linha in linhas:
                        if "Diário publicado em:" in linha:
                            partes = linha.split(" - ")
                            data_pub = partes[0].replace("Diário publicado em:", "").strip()
                            
                            if data_pub.endswith(filtro_data):
                                titulo_pub = " - ".join(partes[1:])
                                
                                link_direto = href
                                if "?find=" not in link_direto:
                                    link_direto = f"{link_direto}?find=ITPS"
                                    
                                if not any(r['link'] == link_direto for r in resultados):
                                    resultados.append({"data": data_pub, "titulo": titulo_pub, "link": link_direto})
                            break
            except Exception:
                continue
                    
    except Exception as e:
        print(f"Erro Scraper IOSE: {e}")
    finally:
        driver.quit()
        
    return resultados[:10]

@app.get("/api/diario-oficial")
async def get_diario():
    agora = time.time()
    
    if cache_iose["dados"] and (agora - cache_iose["ultima_atualizacao"] < TEMPO_CACHE):
        print("Entregando Diário Oficial direto da memória (CACHE) - Super rápido!")
        return {"resultado": cache_iose["dados"]}
        
    print("Iniciando o Robô Chrome para ler o Diário Oficial...")
    resultados = realizar_scraping_iose()
    
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
        cursor.execute("SELECT id, username, name, role FROM contratos.users WHERE username = %s AND password = %s", (req.username, req.password))
        user = cursor.fetchone()
        conn.close()
        if user:
            return dict(user)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.get("/api/contratos")
def contratos_listar():
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contratos.contratos ORDER BY id DESC")
        contratos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"contratos": contratos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/contratos")
def contratos_criar(c: ContratoModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contratos.contratos (instituicao, tipo, objetivo, valor, valor_gasto, prazo, caminho_arquivo) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, c.caminho_arquivo)
        )
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return {"id": new_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/contratos/{id}")
def contratos_atualizar(id: int, c: ContratoModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contratos.contratos SET instituicao = %s, tipo = %s, objetivo = %s, valor = %s, valor_gasto = %s, prazo = %s, caminho_arquivo = %s WHERE id = %s",
            (c.instituicao, c.tipo, c.objetivo, c.valor, c.valor_gasto, c.prazo, c.caminho_arquivo, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/contratos/{id}")
def contratos_deletar(id: int):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.contratos WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

# Categorias
@app.get("/api/contratos/categories")
def contratos_categories_listar():
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contratos.categories ORDER BY name ASC")
        categories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/contratos/categories")
def contratos_categories_criar(cat: CategoryModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        
        # Duplicidade tratada via verificação elegante em Python
        cursor.execute("SELECT 1 FROM contratos.categories WHERE name = %s", (cat.name,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(
                "INSERT INTO contratos.categories (name, color, \"group\") VALUES (%s, %s, %s)",
                (cat.name, cat.color, cat.group)
            )
            conn.commit()
            
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.put("/api/contratos/categories/{id}")
def contratos_categories_atualizar(id: int, cat: CategoryModel):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contratos.categories SET name = %s, color = %s, \"group\" = %s WHERE id = %s",
            (cat.name, cat.color, cat.group, id)
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.delete("/api/contratos/categories/{name}")
def contratos_categories_deletar(name: str):
    try:
        conn = get_contratos_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.categories WHERE name = %s", (name,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
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
        cursor.execute("SELECT id, usuario, permissao FROM folha.usuarios WHERE usuario = %s AND senha = %s", (req.usuario, req.senha))
        user = cursor.fetchone()
        conn.close()
        if user:
            return dict(user)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.get("/api/folha/funcionarios")
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

@app.post("/api/folha/funcionarios")
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

@app.put("/api/folha/funcionarios/{id}")
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

@app.delete("/api/folha/funcionarios/{id}")
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
@app.get("/api/folha/cargos")
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

@app.post("/api/folha/cargos")
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

@app.put("/api/folha/cargos/{id}")
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

@app.delete("/api/folha/cargos/{id}")
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
@app.get("/api/folha/config")
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

@app.post("/api/folha/config/geral")
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

@app.put("/api/folha/config/inss/{id}")
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

@app.put("/api/folha/config/irrf/{id}")
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

@app.post("/api/folha/config/reset")
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
@app.get("/api/folha/folhas")
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

@app.get("/api/folha/folha-detalhes/{id}")
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

@app.post("/api/folha/fechar")
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

@app.delete("/api/folha/folhas/{id}")
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
@app.get("/api/folha/logs")
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

@app.post("/api/folha/logs")
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

@app.delete("/api/folha/logs")
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


# ==============================================================================
# --- EXTENSÃO: PROXY DE BANCO DE DADOS PARA PCA (PLANO DE CONTRATAÇÕES ANUAL) ---
# ==============================================================================

# Usamos a mesma conexão Postgres global já configurada acima
def get_pca_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

def check_global_lock():
    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT liberacao_fim FROM pca.configuracoes WHERE id = 1")
        row = cursor.fetchone()
        if row:
            lib_fim = row['liberacao_fim']
            if lib_fim is None or datetime.now() > lib_fim:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="O período de edição do PCA não está ativo ou expirou. Contate o administrador."
                )
    finally:
        conn.close()

def check_user_lock(username: str):
    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT edit_locked FROM contratos.users WHERE username = %s", (username,))
        row = cursor.fetchone()
        if row and row['edit_locked']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seu acesso de edição foi bloqueado após a finalização do planejamento."
            )
    finally:
        conn.close()

def check_user_individual_release(username: str) -> bool:
    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT individual_release FROM contratos.users WHERE username = %s", (username,))
        row = cursor.fetchone()
        if row and row['individual_release']:
            return True
        return False
    except Exception:
        return False
    finally:
        conn.close()

def registrar_log_pca(usuario: str, acao: str, detalhes: str = ""):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pca.logs (usuario, acao, detalhes, data_hora) VALUES (%s, %s, %s, %s)",
            (usuario, acao, detalhes, datetime.now().isoformat()[:19].replace('T', ' '))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao registrar log PCA: {e}")

def init_pca_db_tables():
    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        # Criar tabelas de parâmetros se não existirem
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pca.laboratorios (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pca.categorias (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pca.tipos_recurso (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE NOT NULL
            );
        """)
        conn.commit()

        # Popular com valores iniciais se estiverem vazias
        cursor.execute("SELECT COUNT(*) as count FROM pca.laboratorios")
        if cursor.fetchone()['count'] == 0:
            labs = [
                'Química de Águas', 'Inorgânica', 'Microbiologia', 'Solos', 
                'Bromatologia', 'Orgânica', 'Qualidade', 'Geconf', 'GEAAD / Insumos Gerais'
            ]
            for lab in labs:
                cursor.execute("INSERT INTO pca.laboratorios (nome) VALUES (%s) ON CONFLICT DO NOTHING", (lab,))
        
        cursor.execute("SELECT COUNT(*) as count FROM pca.categorias")
        if cursor.fetchone()['count'] == 0:
            cats = ['Laboratórios', 'PCA', 'GEAAD']
            for cat in cats:
                cursor.execute("INSERT INTO pca.categorias (nome) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))

        cursor.execute("SELECT COUNT(*) as count FROM pca.tipos_recurso")
        if cursor.fetchone()['count'] == 0:
            recursos = ['Material de Consumo', 'Equipamento', 'Serviço']
            for rec in recursos:
                cursor.execute("INSERT INTO pca.tipos_recurso (nome) VALUES (%s) ON CONFLICT DO NOTHING", (rec,))
        
        # Autopopular usuários padrão dos setores e criar tabela de configurações
        try:
            cursor.execute("ALTER TABLE contratos.users ADD COLUMN IF NOT EXISTS edit_locked BOOLEAN DEFAULT FALSE;")
            cursor.execute("ALTER TABLE contratos.users ADD COLUMN IF NOT EXISTS individual_release BOOLEAN DEFAULT FALSE;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pca.configuracoes (
                    id INT PRIMARY KEY,
                    liberacao_fim TIMESTAMP NULL
                );
            """)
            cursor.execute("INSERT INTO pca.configuracoes (id, liberacao_fim) VALUES (1, NULL) ON CONFLICT (id) DO NOTHING;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pca.logs (
                    id SERIAL PRIMARY KEY,
                    usuario VARCHAR(255) NOT NULL,
                    acao VARCHAR(100) NOT NULL,
                    detalhes TEXT,
                    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("SELECT username FROM contratos.users")
            existing_usernames = {row['username'] for row in cursor.fetchall()}
            
            setores_users = [
                {'username': 'quimica_aguas', 'name': 'Química de Águas', 'role': 'editor'},
                {'username': 'inorganica', 'name': 'Inorgânica', 'role': 'editor'},
                {'username': 'microbiologia', 'name': 'Microbiologia', 'role': 'editor'},
                {'username': 'solos', 'name': 'Solos', 'role': 'editor'},
                {'username': 'bromatologia', 'name': 'Bromatologia', 'role': 'editor'},
                {'username': 'organica', 'name': 'Orgânica', 'role': 'editor'},
                {'username': 'qualidade', 'name': 'Qualidade', 'role': 'editor'},
                {'username': 'geconf', 'name': 'Geconf', 'role': 'editor'},
                {'username': 'geaad', 'name': 'GEAAD / Insumos Gerais', 'role': 'editor'},
            ]
            
            for su in setores_users:
                if su['username'] not in existing_usernames:
                    cursor.execute(
                        "INSERT INTO contratos.users (username, password, name, role) VALUES (%s, %s, %s, %s)",
                        (su['username'], 'itps123', su['name'], su['role'])
                    )
        except Exception as u_err:
            print("Erro ao autopopular logins de setores:", u_err)

        conn.commit()
    except Exception as e:
        print("Erro ao inicializar tabelas do PCA:", e)
        conn.rollback()
    finally:
        conn.close()

# Inicializa as tabelas do PCA ao rodar o backend unificado
init_pca_db_tables()

# --- MODELOS PYDANTIC: PCA ---
class ItemPCAInput(BaseModel):
    origem_pasta: Optional[str] = "Manual"
    origem_arquivo: Optional[str] = "Inserção Direta"
    laboratorio: Optional[str] = "Geral"
    setor: Optional[str] = "Geral"
    categoria_item: Optional[str] = "Material de Consumo"
    tipo: Optional[str] = ""
    codigo: Optional[str] = ""
    item: str
    unidade: Optional[str] = ""
    quantidade: float
    valor_unitario: float
    ano: Optional[int] = 2027

class PCALoginRequest(BaseModel):
    username: str
    password: str

class PCAUserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: str

class PCANameInput(BaseModel):
    nome: str

class PCACopiarAnoRequest(BaseModel):
    de_ano: int
    para_ano: int

class PCAConfigInput(BaseModel):
    liberacao_fim: Optional[str] = None

# --- ENDPOINTS: PCA ---

@app.get("/api/pca")
def listar_itens(busca: Optional[str] = None, pasta: Optional[str] = None, laboratorio: Optional[str] = None, categoria_item: Optional[str] = None, ano: Optional[int] = None):
    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM pca.itens WHERE 1=1"
        params = []
        
        if busca:
            query += " AND (item ILIKE %s OR tipo ILIKE %s OR codigo ILIKE %s OR setor ILIKE %s)"
            params.extend([f"%{busca}%", f"%{busca}%", f"%{busca}%", f"%{busca}%"])
            
        if pasta:
            query += " AND origem_pasta = %s"
            params.append(pasta)

        if laboratorio:
            query += " AND laboratorio = %s"
            params.append(laboratorio)

        if categoria_item:
            query += " AND categoria_item = %s"
            params.append(categoria_item)

        if ano:
            query += " AND ano = %s"
            params.append(ano)
            
        query += " ORDER BY id DESC"
        
        cursor.execute(query, params)
        itens = [dict(row) for row in cursor.fetchall()]
        
        stats_query = "SELECT COUNT(*) as total_itens, SUM(valor_total) as valor_total_consolidado FROM pca.itens WHERE 1=1"
        stats_params = []
        
        if busca:
            stats_query += " AND (item ILIKE %s OR tipo ILIKE %s OR codigo ILIKE %s OR setor ILIKE %s)"
            stats_params.extend([f"%{busca}%", f"%{busca}%", f"%{busca}%", f"%{busca}%"])
        if pasta:
            stats_query += " AND origem_pasta = %s"
            stats_params.append(pasta)
        if laboratorio:
            stats_query += " AND laboratorio = %s"
            stats_params.append(laboratorio)
        if categoria_item:
            stats_query += " AND categoria_item = %s"
            stats_params.append(categoria_item)
        if ano:
            stats_query += " AND ano = %s"
            stats_params.append(ano)

        cursor.execute(stats_query, stats_params)
        stats = dict(cursor.fetchone())
        
        pasta_query = "SELECT origem_pasta, SUM(valor_total) as valor FROM pca.itens WHERE 1=1"
        pasta_params = []
        if ano:
            pasta_query += " AND ano = %s"
            pasta_params.append(ano)
        pasta_query += " GROUP BY origem_pasta"
        cursor.execute(pasta_query, pasta_params)
        por_pasta = [dict(r) for r in cursor.fetchall()]

        cat_query = "SELECT categoria_item, SUM(valor_total) as valor FROM pca.itens WHERE 1=1"
        cat_params = []
        if ano:
            cat_query += " AND ano = %s"
            cat_params.append(ano)
        cat_query += " GROUP BY categoria_item"
        cursor.execute(cat_query, cat_params)
        por_categoria = [dict(r) for r in cursor.fetchall()]

        lab_query = "SELECT laboratorio, SUM(valor_total) as valor, COUNT(*) as count FROM pca.itens WHERE 1=1"
        lab_params = []
        if ano:
            lab_query += " AND ano = %s"
            lab_params.append(ano)
        lab_query += " GROUP BY laboratorio ORDER BY valor DESC"
        cursor.execute(lab_query, lab_params)
        por_laboratorio = [dict(r) for r in cursor.fetchall()]
        
        conn.close()
        return {
            "itens": itens,
            "estatisticas": {
                "total_itens": stats.get("total_itens", 0) or 0,
                "valor_total": stats.get("valor_total_consolidado", 0.0) or 0.0,
                "distribuicao_pasta": por_pasta,
                "distribuicao_categoria": por_categoria,
                "distribuicao_laboratorio": por_laboratorio
            }
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.post("/api/pca", status_code=201)
def criar_item(input_data: ItemPCAInput, x_user_role: Optional[str] = Header(None), x_username: Optional[str] = Header(None)):
    if x_user_role != "admin":
        is_released = False
        if x_username:
            is_released = check_user_individual_release(x_username)
        if not is_released:
            check_global_lock()
        if x_username:
            check_user_lock(x_username)

    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        valor_total = input_data.quantidade * input_data.valor_unitario
        cursor.execute(
            """
            INSERT INTO pca.itens 
            (origem_pasta, origem_arquivo, laboratorio, setor, categoria_item, tipo, codigo, item, unidade, quantidade, valor_unitario, valor_total, data_sincronizacao, ano)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                input_data.origem_pasta,
                input_data.origem_arquivo,
                input_data.laboratorio,
                input_data.setor,
                input_data.categoria_item,
                input_data.tipo,
                input_data.codigo,
                input_data.item,
                input_data.unidade,
                input_data.quantidade,
                input_data.valor_unitario,
                valor_total,
                datetime.now(),
                input_data.ano or 2027
            )
        )
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        registrar_log_pca(x_username or "desconhecido", "Criou item", f"Item #{new_id}: {input_data.item}")
        return {"id": new_id, "success": True, "message": "Item criado com sucesso!"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao inserir item: {str(e)}")

@app.put("/api/pca/{id}")
def atualizar_item(id: int, input_data: ItemPCAInput, x_user_role: Optional[str] = Header(None), x_username: Optional[str] = Header(None)):
    if x_user_role != "admin":
        is_released = False
        if x_username:
            is_released = check_user_individual_release(x_username)
        if not is_released:
            check_global_lock()
        if x_username:
            check_user_lock(x_username)

    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        valor_total = input_data.quantidade * input_data.valor_unitario
        cursor.execute(
            """
            UPDATE pca.itens 
            SET origem_pasta = %s, origem_arquivo = %s, laboratorio = %s, setor = %s, categoria_item = %s,
                tipo = %s, codigo = %s, item = %s, unidade = %s, quantidade = %s, valor_unitario = %s, valor_total = %s, ano = %s
            WHERE id = %s
            """,
            (
                input_data.origem_pasta,
                input_data.origem_arquivo,
                input_data.laboratorio,
                input_data.setor,
                input_data.categoria_item,
                input_data.tipo,
                input_data.codigo,
                input_data.item,
                input_data.unidade,
                input_data.quantidade,
                input_data.valor_unitario,
                valor_total,
                input_data.ano or 2027,
                id
            )
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        
        if affected == 0:
            raise HTTPException(status_code=404, detail="Item não encontrado.")
        
        registrar_log_pca(x_username or "desconhecido", "Editou item", f"Item #{id}: {input_data.item}")
        return {"success": True, "message": "Item atualizado com sucesso!"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar item: {str(e)}")

@app.delete("/api/pca/{id}")
def deletar_item(id: int, x_user_role: Optional[str] = Header(None), x_username: Optional[str] = Header(None)):
    if x_user_role != "admin":
        is_released = False
        if x_username:
            is_released = check_user_individual_release(x_username)
        if not is_released:
            check_global_lock()
        if x_username:
            check_user_lock(x_username)

    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM pca.itens WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        
        if affected == 0:
            raise HTTPException(status_code=404, detail="Item não encontrado.")
        
        registrar_log_pca(x_username or "desconhecido", "Excluiu item", f"Item #{id}")
        return {"success": True, "message": "Item excluído com sucesso!"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir item: {str(e)}")

@app.post("/api/pca/login")
def pca_login(req: PCALoginRequest):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, name, role, edit_locked, individual_release FROM contratos.users WHERE username = %s AND password = %s", (req.username, req.password))
        user = cursor.fetchone()
        conn.close()
        if user:
            registrar_log_pca(req.username, "Login", "Acesso ao sistema")
            return dict(user)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Banco de Dados: {str(e)}")

@app.get("/api/pca/users")
def list_users():
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, name, role, edit_locked, individual_release FROM contratos.users ORDER BY id DESC")
        users = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar usuários: {str(e)}")

@app.post("/api/pca/users", status_code=201)
def create_user(u: PCAUserCreate):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contratos.users (username, password, name, role) VALUES (%s, %s, %s, %s) RETURNING id",
            (u.username, u.password, u.name, u.role)
        )
        new_id = cursor.fetchone()['id']
        
        if u.role != 'admin':
            cursor.execute("INSERT INTO pca.laboratorios (nome) VALUES (%s) ON CONFLICT DO NOTHING", (u.name,))
            
        conn.commit()
        conn.close()
        registrar_log_pca("admin", "Criou usuário", f"Usuário: {u.username} (ID #{new_id}, Papel: {u.role})")
        return {"id": new_id, "success": True, "message": "Usuário criado com sucesso!"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao criar usuário: {str(e)}")

@app.delete("/api/pca/users/{id}")
def delete_user(id: int):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos.users WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        registrar_log_pca("admin", "Excluiu usuário", f"Usuário ID #{id}")
        return {"success": True, "message": "Usuário excluído com sucesso!"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir usuário: {str(e)}")

class PCAUserUpdate(BaseModel):
    username: str
    name: str
    role: str
    edit_locked: Optional[bool] = False
    individual_release: Optional[bool] = False
    password: Optional[str] = None

@app.put("/api/pca/users/{id}")
def update_user(id: int, u: PCAUserUpdate):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        if u.password and u.password.strip():
            cursor.execute(
                "UPDATE contratos.users SET username = %s, name = %s, role = %s, edit_locked = %s, individual_release = %s, password = %s WHERE id = %s",
                (u.username, u.name, u.role, u.edit_locked, u.individual_release, u.password, id)
            )
        else:
            cursor.execute(
                "UPDATE contratos.users SET username = %s, name = %s, role = %s, edit_locked = %s, individual_release = %s WHERE id = %s",
                (u.username, u.name, u.role, u.edit_locked, u.individual_release, id)
            )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        detalhes_log = f"Usuário: {u.username} (Papel: {u.role}"
        if u.edit_locked:
            detalhes_log += ", Bloqueado"
        if u.individual_release:
            detalhes_log += ", Liberação Individual"
        detalhes_log += ")"
        registrar_log_pca("admin", "Editou usuário", detalhes_log)
        return {"success": True, "message": "Usuário atualizado com sucesso!"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar usuário: {str(e)}")

@app.post("/api/pca/users/{id}/lock")
def lock_user_planning(id: int):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE contratos.users SET edit_locked = TRUE WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        registrar_log_pca(f"user_id_{id}", "Finalizou planejamento", f"Usuário ID #{id} finalizou seu planejamento")
        return {"success": True, "message": "Planejamento finalizado com sucesso!"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao finalizar planejamento: {str(e)}")

# --- PARAMETROS DINAMICOS: LABORATORIOS ---

@app.get("/api/pca/laboratorios")
def list_laboratorios():
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM pca.laboratorios ORDER BY nome ASC")
        labs = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return labs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar laboratórios: {str(e)}")

@app.post("/api/pca/laboratorios", status_code=201)
def create_laboratorio(item: PCANameInput):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pca.laboratorios (nome) VALUES (%s) RETURNING id", (item.nome,))
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return {"id": new_id, "success": True}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao criar laboratório: {str(e)}")

@app.delete("/api/pca/laboratorios/{id}")
def delete_laboratorio(id: int):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pca.laboratorios WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Laboratório não encontrado")
        return {"success": True}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir laboratório: {str(e)}")

# --- PARAMETROS DINAMICOS: CATEGORIAS ---

@app.get("/api/pca/categorias")
def list_categorias():
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM pca.categorias ORDER BY nome ASC")
        cats = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return cats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar categorias: {str(e)}")

@app.post("/api/pca/categorias", status_code=201)
def create_categoria(item: PCANameInput):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pca.categorias (nome) VALUES (%s) RETURNING id", (item.nome,))
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return {"id": new_id, "success": True}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao criar categoria: {str(e)}")

@app.delete("/api/pca/categorias/{id}")
def delete_categoria(id: int):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pca.categorias WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Categoria não encontrada")
        return {"success": True}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir categoria: {str(e)}")

# --- PARAMETROS DINAMICOS: TIPOS DE RECURSO ---

@app.get("/api/pca/tipos-recurso")
def list_tipos_recurso():
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM pca.tipos_recurso ORDER BY nome ASC")
        recursos = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return recursos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar tipos de recurso: {str(e)}")

@app.post("/api/pca/tipos-recurso", status_code=201)
def create_tipo_recurso(item: PCANameInput):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pca.tipos_recurso (nome) VALUES (%s) RETURNING id", (item.nome,))
        new_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return {"id": new_id, "success": True}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao criar tipo de recurso: {str(e)}")

@app.delete("/api/pca/tipos-recurso/{id}")
def delete_tipo_recurso(id: int):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pca.tipos_recurso WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Tipo de recurso não encontrado")
        return {"success": True}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir tipo de recurso: {str(e)}")

@app.post("/api/pca/copiar-ano")
def copiar_ano(req: PCACopiarAnoRequest):
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM pca.itens WHERE ano = %s", (req.de_ano,))
        count = cursor.fetchone()['count']
        if count == 0:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Não existem itens cadastrados no ano de {req.de_ano} para copiar.")
            
        cursor.execute("DELETE FROM pca.itens WHERE ano = %s", (req.para_ano,))
        
        cursor.execute(
            """
            INSERT INTO pca.itens 
            (origem_pasta, origem_arquivo, laboratorio, setor, categoria_item, tipo, codigo, item, unidade, quantidade, valor_unitario, valor_total, data_sincronizacao, ano)
            SELECT origem_pasta, origem_arquivo, laboratorio, setor, categoria_item, tipo, codigo, item, unidade, quantidade, valor_unitario, valor_total, NOW(), %s
            FROM pca.itens
            WHERE ano = %s
            """,
            (req.para_ano, req.de_ano)
        )
        copied_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        registrar_log_pca("admin", "Copiou ano", f"{copied_count} itens copiados de {req.de_ano} para {req.para_ano}")
        return {
            "success": True,
            "message": f"Sucesso! {copied_count} itens copiados de {req.de_ano} para {req.para_ano}."
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro ao copiar itens de ano: {str(e)}")

@app.get("/api/pca/config")
def get_global_config():
    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT @liberacao_fim FROM pca.configuracoes WHERE id = 1" if False else "SELECT liberacao_fim FROM pca.configuracoes WHERE id = 1")
        row = cursor.fetchone()
        if row:
            lib_fim = row['liberacao_fim']
            is_active = False
            if lib_fim is not None:
                is_active = datetime.now() < lib_fim
            return {
                "liberacao_fim": lib_fim.isoformat() if lib_fim else None,
                "is_globally_released": is_active
            }
        return {"liberacao_fim": None, "is_globally_released": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter configuração: {str(e)}")
    finally:
        conn.close()

@app.post("/api/pca/config")
def update_global_config(cfg: PCAConfigInput):
    conn = get_pca_db()
    cursor = conn.cursor()
    try:
        val = None
        if cfg.liberacao_fim:
            try:
                val = datetime.fromisoformat(cfg.liberacao_fim.replace('Z', ''))
            except Exception:
                raise HTTPException(status_code=400, detail="Formato de data inválido. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)")
        
        cursor.execute("UPDATE pca.configuracoes SET liberacao_fim = %s WHERE id = 1", (val,))
        conn.commit()
        registrar_log_pca("admin", "Alterou configuração", f"Prazo de liberação: {cfg.liberacao_fim or 'Removido'}")
        return {"success": True, "message": "Configuração atualizada com sucesso!"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar configuração: {str(e)}")
    finally:
        conn.close()
# --- LOGS DE AUDITORIA DO PCA ---

@app.get("/api/pca/logs")
def pca_logs_listar(x_user_role: Optional[str] = Header(None)):
    if x_user_role != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores podem ver os logs.")
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pca.logs ORDER BY id DESC LIMIT 500")
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar logs: {str(e)}")

@app.delete("/api/pca/logs")
def pca_logs_limpar(x_user_role: Optional[str] = Header(None)):
    if x_user_role != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores podem limpar os logs.")
    try:
        conn = get_pca_db()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE pca.logs RESTART IDENTITY CASCADE")
        conn.commit()
        conn.close()
        return {"success": True, "message": "Logs limpos com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao limpar logs: {str(e)}")

import json
import uuid

# --- DYNAMIC MURAL DE AVISOS MODEL & ENDPOINTS ---
class AvisoInput(BaseModel):
    titulo: str
    conteudo: str
    prioridade: str  # "urgente", "informativo", "geral"
    codigo_acesso: str

AVISOS_FILE = "avisos.json"

def ler_avisos() -> List[Dict[str, Any]]:
    if not os.path.exists(AVISOS_FILE):
        exemplo = [
            {
                "id": str(uuid.uuid4()),
                "titulo": "Bem-vindo à Nova Intranet!",
                "conteudo": "Este é o novo Mural de Avisos dinâmico do ITPS. Aqui o setor de TI e RH divulgará comunicados oficiais rapidamente.",
                "prioridade": "geral",
                "data_criacao": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
        ]
        with open(AVISOS_FILE, "w", encoding="utf-8") as f:
            json.dump(exemplo, f, ensure_ascii=False, indent=4)
        return exemplo
    
    try:
        with open(AVISOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def salvar_avisos(avisos: List[Dict[str, Any]]):
    with open(AVISOS_FILE, "w", encoding="utf-8") as f:
        json.dump(avisos, f, ensure_ascii=False, indent=4)

@app.get("/api/avisos")
async def get_avisos():
    return {"resultado": ler_avisos()}

@app.post("/api/avisos")
async def post_aviso(aviso_in: AvisoInput):
    if aviso_in.codigo_acesso != "itps123":
        raise HTTPException(status_code=403, detail="Código de acesso incorreto!")
    
    avisos = ler_avisos()
    novo_aviso = {
        "id": str(uuid.uuid4()),
        "titulo": aviso_in.titulo,
        "conteudo": aviso_in.conteudo,
        "prioridade": aviso_in.prioridade,
        "data_criacao": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    avisos.insert(0, novo_aviso)
    salvar_avisos(avisos)
    return {"success": True, "aviso": novo_aviso}

@app.delete("/api/avisos/{aviso_id}")
async def delete_aviso(aviso_id: str, codigo_acesso: str):
    if codigo_acesso != "itps123":
        raise HTTPException(status_code=403, detail="Código de acesso incorreto!")
    
    avisos = ler_avisos()
    novos_avisos = [a for a in avisos if a["id"] != aviso_id]
    
    if len(novos_avisos) == len(avisos):
        raise HTTPException(status_code=404, detail="Aviso não encontrado!")
        
    salvar_avisos(novos_avisos)
    return {"success": True, "message": "Aviso removido com sucesso!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)