import time
import re
from datetime import datetime
import calendar
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

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

def buscar_licitacoes_comprasnet_se():
    agora_ts = time.time()
    # Para cache vamos depender da funcao do router depois, mas deixamos cache vazio por enquanto
    
    url = "https://sistema.comprasnet.se.gov.br/publico/ConsultaProcessos.aspx"
    items = []
    
    agora = datetime.now()
    ultimo_dia = calendar.monthrange(agora.year, agora.month)[1]
    inicio_mes = f"01/{agora.month:02d}/{agora.year}"
    fim_mes = f"{ultimo_dia:02d}/{agora.month:02d}/{agora.year}"

    def _extrair_itps_da_tabela(soup_page):
        """Extrai processos do ITPS da tabela de resultados da página atual."""
        encontrados = []
        tables = soup_page.find_all('table')
        print(f"  [DEBUG] _extrair: {len(tables)} tabelas no HTML")
        if not tables:
            return encontrados
        
        # Usar a tabela com mais linhas (a tabela de resultados)
        best_table = None
        best_rows = 0
        for t in tables:
            rows = t.find_all('tr')
            if len(rows) > best_rows:
                best_rows = len(rows)
                best_table = t
        
        if not best_table:
            print("  [DEBUG] _extrair: nenhuma tabela com linhas encontrada")
            return encontrados
        
        print(f"  [DEBUG] _extrair: usando tabela com {best_rows} linhas")
        
        for idx, tr in enumerate(best_table.find_all('tr')):
            tds = [td.text.strip() for td in tr.find_all(['td', 'th'])]
            if len(tds) < 4:
                continue
            # Pular cabeçalho
            if tds[1] == 'Órgão' or tds[2] == 'Edital':
                continue
            # Filtrar apenas ITPS
            if 'ITPS' not in tds[1].upper():
                continue
            
            edital_raw = tds[2]
            situacao_raw = tds[3]
            
            if ' - ' in edital_raw:
                parts = edital_raw.split(' - ', 1)
                numero = parts[0].strip()
                objeto = parts[1].strip()
            else:
                numero = edital_raw
                objeto = edital_raw
            
            situacao_clean = " ".join(situacao_raw.split())
            m_sit = re.match(r'^(Em disputa|Publicado|Homologado / Finalizado|Homologado|Finalizado|Adjudicação|Deserto|Processo revogado|Em negociação|Declaração de vencedor)\s*(.*)$', situacao_clean, re.I)
            if m_sit:
                situacao = m_sit.group(1).strip()
                prazo = m_sit.group(2).strip()
            else:
                situacao = situacao_clean
                prazo = ""
            
            modalidade_calc = "DISPENSA POR VALOR"
            if numero.upper().startswith("DE"):
                modalidade_calc = "DISPENSA EMERGENCIAL"
            elif "DL" in numero.upper():
                modalidade_calc = "DISPENSA DE LICITAÇÃO"
            elif "IN" in numero.upper():
                modalidade_calc = "INEXIGIBILIDADE DE LICITAÇÃO"

            # Extrair o ID do botão "Visualizar" da linha para clicar depois
            btn_id = None
            for inp in tr.find_all('input', {'type': 'image'}):
                inp_id = inp.get('id', '')
                if 'cmd' in inp_id.lower():
                    btn_id = inp_id
                    break

            encontrados.append({
                "orgao": "ITPS - INSTITUTO TECNOLÓGICO E DE PESQUISAS DO ESTADO DE SERGIPE",
                "edital": numero,
                "objeto": objeto,
                "modalidade": modalidade_calc,
                "periodo": f"{inicio_mes} até {fim_mes}",
                "situacao": situacao,
                "prazo": prazo,
                "link": "https://sistema.comprasnet.se.gov.br/publico/ConsultaProcessos.aspx",
                "_btn_id": btn_id  # ID do botão para capturar link direto
            })
            print(f"  [DEBUG] _extrair: encontrou {numero} - {situacao} (btn: {btn_id})")
        
        print(f"  [DEBUG] _extrair: total extraído = {len(encontrados)}")
        return encontrados

    def _capturar_links_diretos(driver_ref, processos):
        """Clica no botão 'Visualizar' de cada processo ITPS para capturar a URL direta."""
        for proc in processos:
            btn_id = proc.pop("_btn_id", None)
            if not btn_id:
                continue
            try:
                btn = driver_ref.find_elements(By.ID, btn_id)
                if not btn:
                    continue
                driver_ref.execute_script("arguments[0].click();", btn[0])
                time.sleep(3)
                
                # Capturar a URL da página de detalhes
                current_url = driver_ref.current_url
                if 'ProcessoDetalhes.aspx' in current_url:
                    proc["link"] = current_url
                    print(f"  [DEBUG] Link direto capturado para {proc['edital']}: {current_url}")
                
                # Voltar para a lista
                driver_ref.back()
                time.sleep(3)
            except Exception as e:
                print(f"  [DEBUG] Erro ao capturar link de {proc['edital']}: {e}")
                try:
                    driver_ref.back()
                    time.sleep(2)
                except:
                    pass

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        except:
            driver = webdriver.Chrome(options=chrome_options)

        try:
            driver.get(url)
            time.sleep(4)
            
            # === PESQUISA AVANÇADA NO COMPRASNET SE ===
            print("Comprasnet SE: Iniciando pesquisa avançada ao vivo...")
            btn_adv = driver.find_elements(By.ID, "PlaceHolder_ucConsulta_ucConsultaDispensas_cmdPesquisaAvancada")
            if btn_adv:
                driver.execute_script("arguments[0].click();", btn_adv[0])
                time.sleep(4)
                
            cmb_orgao = driver.find_elements(By.ID, "PlaceHolder_ucConsulta_ucConsultaDispensas_cmbOrgao")
            if cmb_orgao:
                sel_orgao = Select(cmb_orgao[0])
                sel_orgao.select_by_value("91") # ITPS
                time.sleep(4)
                
            txt_de = driver.find_elements(By.ID, "PlaceHolder_ucConsulta_ucConsultaDispensas_txtFiltroDataDe")
            if txt_de:
                txt_de[0].clear()
                txt_de[0].send_keys(inicio_mes)
                
            txt_ate = driver.find_elements(By.ID, "PlaceHolder_ucConsulta_ucConsultaDispensas_txtFiltroDataAte")
            if txt_ate:
                txt_ate[0].clear()
                txt_ate[0].send_keys(fim_mes)
                
            btn_pesq = driver.find_elements(By.ID, "PlaceHolder_ucConsulta_ucConsultaDispensas_cmdPesquisar")
            if btn_pesq:
                driver.execute_script("arguments[0].click();", btn_pesq[0])
                time.sleep(6)
                
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            page1_items = _extrair_itps_da_tabela(soup)
            
            # Capturar links diretos da página 1
            if page1_items:
                print(f"Comprasnet SE: Capturando links diretos da página 1 ({len(page1_items)} processos)...")
                _capturar_links_diretos(driver, page1_items)
            
            items = list(page1_items)
            
            # Se houver mais de uma página de resultados, iterar
            try:
                for page_num in range(2, 10):
                    page_links = driver.find_elements(By.XPATH, f"//a[text()='{page_num}']")
                    if page_links:
                        driver.execute_script("arguments[0].click();", page_links[0])
                        time.sleep(4)
                        soup_next = BeautifulSoup(driver.page_source, 'html.parser')
                        more_items = _extrair_itps_da_tabela(soup_next)
                        
                        # Capturar links diretos desta página
                        new_items = [mi for mi in more_items if not any(x["edital"] == mi["edital"] for x in items)]
                        if new_items:
                            print(f"Comprasnet SE: Capturando links diretos da página {page_num} ({len(new_items)} processos)...")
                            _capturar_links_diretos(driver, new_items)
                            items.extend(new_items)
                    else:
                        break
            except Exception as e_pag:
                print(f"Erro na paginação de resultados: {e_pag}")

        finally:
            driver.quit()
    except Exception as err:
        print("Erro ao raspar Comprasnet SE:", err)

    if items:
        # Limpar campos internos
        for item in items:
            item.pop("_btn_id", None)
        print(f"Comprasnet SE: {len(items)} processos raspados ao vivo com sucesso!")
        return items

    return []

