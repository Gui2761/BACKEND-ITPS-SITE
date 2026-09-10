/**
 * ==============================================================================
 * DASHBOARD EXECUTIVO - GEPROCON
 * Arquivo: script.js
 * Sincronizado diretamente com a Planilha Oficial do Google Sheets
 * ==============================================================================
 */

const GOOGLE_SPREADSHEET_ID = '19yu2sdrzcB62-2kpyQCMxDjwr0cvyNCapy8_L_3W-Fc';
const STORAGE_OBS_KEY = 'ITPS_GEPROCON_OBSERVACOES';
const STORAGE_CACHE_KEY = 'ITPS_GEPROCON_DATA_CACHE';

let rawData = [];
let currentFilteredData = [];
let currentObservacoes = [];

const POS_LABELS = {
  'chart_unidade': 'Valor por Unidade',
  'chart_status': 'Status Agrupado',
  'chart_rubrica': 'Saldo / Rubrica',
  'chart_top_proc': 'Processos'
};

window.onload = function() {
  reloadData();
};

/* =========================================================================
   CARREGAMENTO DE DADOS (GOOGLE SHEETS GViz EM TEMPO REAL)
   ========================================================================= */

async function reloadData() {
  const loader = document.getElementById('loader');
  const statusEl = document.getElementById('loaderStatus');
  const syncBadge = document.getElementById('syncStatusText');
  
  loader.style.display = 'flex';
  statusEl.innerText = 'Conectando à Planilha Google...';

  try {
    // 1. Carrega a aba Orçamentário
    statusEl.innerText = 'Consultando aba Orçamentário...';
    const orcTable = await fetchGoogleSheet('Orçamentário');
    const mapOrcamento = processarOrcamento(orcTable);

    // 2. Carrega as abas de processos
    const abasAlvo = ['SEMAC/FUNTEC', 'ITPS', 'INMETRO'];
    let dadosCombinados = [];

    for (const nomeAba of abasAlvo) {
      statusEl.innerText = `Baixando dados da aba ${nomeAba}...`;
      try {
        const table = await fetchGoogleSheet(nomeAba);
        const processosAba = processarAbaProcessos(table, nomeAba, mapOrcamento, dadosCombinados.length);
        dadosCombinados = dadosCombinados.concat(processosAba);
      } catch (errAba) {
        console.warn(`Aviso ao carregar aba ${nomeAba}:`, errAba);
      }
    }

    if (!dadosCombinados.length) {
      throw new Error('Nenhum processo foi retornado da planilha.');
    }

    // 3. Carrega observações (Google Sheets + localStorage)
    statusEl.innerText = 'Consolidando observações...';
    let obsGSheets = [];
    try {
      const obsTable = await fetchGoogleSheet('Observacoes');
      obsGSheets = processarObservacoes(obsTable);
    } catch (e) {
      console.log('Sem observações na planilha, buscando local:', e);
    }

    const localObs = getLocalObservacoes();
    // Mescla observações locais com as da planilha
    currentObservacoes = localObs.length > 0 ? localObs : obsGSheets;

    rawData = dadosCombinados;

    // Salva cache offline
    try {
      localStorage.setItem(STORAGE_CACHE_KEY, JSON.stringify({
        processos: rawData,
        observacoes: currentObservacoes,
        timestamp: Date.now()
      }));
    } catch (e) {}

    syncBadge.innerText = 'Google Sheets: Tempo Real';
    syncBadge.parentElement.style.background = '#f0fdf4';
    syncBadge.parentElement.style.borderColor = '#bbf7d0';
    syncBadge.parentElement.style.color = '#166534';

    onDataLoaded({ processos: rawData, observacoes: currentObservacoes });

  } catch (err) {
    console.error('Falha ao conectar com Google Sheets ao vivo:', err);
    statusEl.innerText = 'Buscando dados em cache local ou arquivo...';
    
    // 1. Tenta recuperar do cache local do navegador
    const cached = localStorage.getItem(STORAGE_CACHE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        rawData = parsed.processos || [];
        currentObservacoes = parsed.observacoes || [];
        
        syncBadge.innerText = 'Modo Cache (Navegador)';
        syncBadge.parentElement.style.background = '#fefce8';
        syncBadge.parentElement.style.borderColor = '#fef08a';
        syncBadge.parentElement.style.color = '#854d0e';

        onDataLoaded({ processos: rawData, observacoes: currentObservacoes });
        loader.style.display = 'none';
        return;
      } catch (e) {}
    }

    // 2. Tenta carregar o arquivo local ITPS.xlsx como fallback
    try {
      if (typeof XLSX !== 'undefined') {
        statusEl.innerText = 'Carregando arquivo de contingência ITPS.xlsx...';
        const fileResp = await fetch('ITPS.xlsx');
        if (fileResp.ok) {
          const ab = await fileResp.arrayBuffer();
          const wb = XLSX.read(ab, { type: 'array' });
          const processed = processarWorkbookXLSX(wb);
          if (processed && processed.length) {
            rawData = processed;
            syncBadge.innerText = 'Arquivo Local (ITPS.xlsx)';
            syncBadge.parentElement.style.background = '#fefce8';
            syncBadge.parentElement.style.borderColor = '#fef08a';
            syncBadge.parentElement.style.color = '#854d0e';
            onDataLoaded({ processos: rawData, observacoes: currentObservacoes });
            loader.style.display = 'none';
            return;
          }
        }
      }
    } catch (eXlsx) {
      console.warn('Fallback XLSX não concluído:', eXlsx);
    }

    loader.style.display = 'none';
    alert('Não foi possível carregar os dados em tempo real da Planilha Google: ' + err.message + '\n\nVerifique sua conexão de internet.');
  }
}

/**
 * Consulta o Google Sheets usando JSONP para evitar bloqueios de CORS e login
 */
function fetchGoogleSheet(sheetName) {
  return new Promise((resolve, reject) => {
    const cbName = 'gviz_cb_' + Math.random().toString(36).substring(2, 9);
    const script = document.createElement('script');
    const url = `https://docs.google.com/spreadsheets/d/${GOOGLE_SPREADSHEET_ID}/gviz/tq?tqx=responseHandler:${cbName}&sheet=${encodeURIComponent(sheetName)}&_=${Date.now()}`;
    
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error(`Tempo limite excedido para a aba "${sheetName}"`));
    }, 15000);

    function cleanup() {
      clearTimeout(timeout);
      delete window[cbName];
      if (script.parentNode) script.parentNode.removeChild(script);
    }

    window[cbName] = function(data) {
      cleanup();
      if (data && data.status === 'ok') {
        resolve(data.table);
      } else {
        reject(new Error(`Erro ao obter "${sheetName}"`));
      }
    };

    script.onerror = function() {
      cleanup();
      reject(new Error(`Falha de conexão com a aba "${sheetName}"`));
    };

    script.src = url;
    document.head.appendChild(script);
  });
}

/* =========================================================================
   FUNÇÕES DE LIMPEZA E TRATAMENTO DE DADOS (IDENTICAS AO CODE.GS)
   ========================================================================= */

function cleanNum(val) {
  if (typeof val === 'number') return isNaN(val) ? 0 : val;
  if (!val) return 0;
  let str = String(val).replace(/R\$\s?/gi, '').replace(/\s/g, '');
  if (str.includes(',') && str.includes('.')) {
    str = str.replace(/\./g, '').replace(',', '.');
  } else if (str.includes(',')) {
    str = str.replace(',', '.');
  }
  str = str.replace(/%/g, '');
  const num = parseFloat(str);
  return isNaN(num) ? 0 : num;
}

function processarOrcamento(table) {
  const mapOrcamento = {};
  if (!table || !table.rows) return mapOrcamento;

  const headers = (table.cols || []).map(c => String(c.label || '').trim().toLowerCase());
  const rows = table.rows.map(r => (r.c || []).map(cell => (cell ? cell.v : null)));

  const idxRubrica = headers.findIndex(h => h.includes('rubrica'));
  const idxFonte   = headers.findIndex(h => h.includes('fonte'));
  const idxValor   = headers.findIndex(h => h.includes('valor') || h.includes('orçamen') || h.includes('orcamento'));

  rows.forEach(r => {
    if (!r.some(cell => cell !== '' && cell !== null)) return;

    const rubrica = idxRubrica !== -1 && r[idxRubrica] ? String(r[idxRubrica]).trim() : (r[0] ? String(r[0]).trim() : '');
    const fonte   = idxFonte !== -1 && r[idxFonte] ? String(r[idxFonte]).trim() : (r[1] ? String(r[1]).trim() : '');
    const valor   = idxValor !== -1 ? cleanNum(r[idxValor]) : (r[2] ? cleanNum(r[2]) : 0);

    const keyExact = `${fonte.toLowerCase()}|${rubrica.toLowerCase()}`;
    const keyRubrica = rubrica.toLowerCase();

    if (keyExact) mapOrcamento[keyExact] = valor;
    if (keyRubrica && mapOrcamento[keyRubrica] === undefined) mapOrcamento[keyRubrica] = valor;
  });

  return mapOrcamento;
}

function processarWorkbookXLSX(wb) {
  if (!wb) return [];
  const mapOrcamento = {};
  
  // Buscar aba orçamentário
  const sheetOrcName = wb.SheetNames.find(s => ['orçamentário', 'orcamento', 'tabela_2', 'orçamento'].includes(s.toLowerCase().trim())) || wb.SheetNames[4];
  if (sheetOrcName && wb.Sheets[sheetOrcName]) {
    const rawOrc = XLSX.utils.sheet_to_json(wb.Sheets[sheetOrcName], { header: 1 });
    if (rawOrc.length > 1) {
      const headers = (rawOrc[0] || []).map(h => String(h || '').trim().toLowerCase());
      const idxRubrica = headers.findIndex(h => h.includes('rubrica'));
      const idxFonte   = headers.findIndex(h => h.includes('fonte'));
      const idxValor   = headers.findIndex(h => h.includes('valor') || h.includes('orçamen') || h.includes('orcamento'));

      rawOrc.slice(1).forEach(r => {
        if (!r || !r.length) return;
        const rubrica = idxRubrica !== -1 && r[idxRubrica] ? String(r[idxRubrica]).trim() : String(r[0] || '').trim();
        const fonte   = idxFonte !== -1 && r[idxFonte] ? String(r[idxFonte]).trim() : String(r[1] || '').trim();
        const valor   = idxValor !== -1 ? cleanNum(r[idxValor]) : cleanNum(r[2]);
        const keyExact = `${fonte.toLowerCase()}|${rubrica.toLowerCase()}`;
        const keyRubrica = rubrica.toLowerCase();
        if (keyExact) mapOrcamento[keyExact] = valor;
        if (keyRubrica && mapOrcamento[keyRubrica] === undefined) mapOrcamento[keyRubrica] = valor;
      });
    }
  }

  // Buscar abas de processos
  const targetSheets = ['semacfuntec', 'semac/funtec', 'itps', 'inmetro'];
  let combined = [];

  wb.SheetNames.forEach(sheetName => {
    const sLow = sheetName.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (targetSheets.some(t => t.replace(/[^a-z0-9]/g, '') === sLow)) {
      const rawRows = XLSX.utils.sheet_to_json(wb.Sheets[sheetName], { header: 1 });
      if (rawRows.length > 1) {
        const headers = (rawRows[0] || []).map(h => String(h || '').trim().toLowerCase());
        const getIndex = (keywords) => headers.findIndex(h => keywords.some(k => h.includes(k)));
        const idxProc        = getIndex(['proc']);
        const idxUnidade     = getIndex(['unidade']);
        const idxEspec       = getIndex(['especific']);
        const idxFonte       = getIndex(['fonte']);
        const idxRubrica     = getIndex(['rubrica']);
        const idxStatus      = getIndex(['status']);
        const idxStatusAgrup = getIndex(['agrupado']);
        const idxOrcamento   = getIndex(['orçamen', 'orcamento']);
        const idxValor       = getIndex(['valor']);
        const idxSaldo       = getIndex(['saldo']);
        const idxExec        = getIndex(['executado', '%']);

        rawRows.slice(1).forEach((r, idx) => {
          if (!r || !r.some(cell => cell !== null && cell !== '')) return;
          const strPrimeira = String(r[0] || '').toLowerCase();
          if (strPrimeira.includes('proc') || strPrimeira.includes('nº')) return;

          const fonteStr = idxFonte !== -1 && r[idxFonte] ? String(r[idxFonte]).trim() : (sheetName.includes('INMETRO') ? 'INMETRO' : (sheetName.includes('ITPS') ? 'ITPS' : 'FUNTEC'));
          const rubricaStr = idxRubrica !== -1 && r[idxRubrica] ? String(r[idxRubrica]).trim() : 'Material de Consumo';

          const keyExact = `${fonteStr.toLowerCase()}|${rubricaStr.toLowerCase()}`;
          const keyRubrica = rubricaStr.toLowerCase();

          let valOrc = 0;
          if (mapOrcamento[keyExact] !== undefined) valOrc = mapOrcamento[keyExact];
          else if (mapOrcamento[keyRubrica] !== undefined) valOrc = mapOrcamento[keyRubrica];
          else valOrc = idxOrcamento !== -1 ? cleanNum(r[idxOrcamento]) : 0;

          const valValor = idxValor !== -1 ? cleanNum(r[idxValor]) : cleanNum(r[8]);
          const valSaldo = idxSaldo !== -1 ? cleanNum(r[idxSaldo]) : cleanNum(r[9]);
          let exec = 0;
          if (valOrc > 0) exec = (valValor / valOrc) * 100;
          else if (idxExec !== -1 && r[idxExec] !== null) {
            exec = cleanNum(r[idxExec]);
            if (typeof r[idxExec] === 'number' && r[idxExec] <= 1.0) exec *= 100;
          }

          combined.push({
            id: combined.length + 1,
            proc: idxProc !== -1 && r[idxProc] ? String(r[idxProc]) : `Linha ${idx + 2}`,
            unidade: idxUnidade !== -1 && r[idxUnidade] ? String(r[idxUnidade]).trim() : 'GEATEC',
            especificacao: idxEspec !== -1 && r[idxEspec] ? String(r[idxEspec]).trim() : '-',
            fonte: fonteStr,
            rubrica: rubricaStr,
            status: idxStatus !== -1 && r[idxStatus] ? String(r[idxStatus]).trim() : '-',
            statusAgrupado: idxStatusAgrup !== -1 && r[idxStatusAgrup] ? String(r[idxStatusAgrup]).trim() : 'Pendente',
            orcamentario: valOrc,
            valor: valValor,
            saldo: valSaldo,
            percentExec: exec
          });
        });
      }
    }
  });

  return combined;
}

function processarAbaProcessos(table, nomeAba, mapOrcamento, currentTotal) {
  if (!table || !table.rows) return [];

  const headers = (table.cols || []).map(c => String(c.label || '').trim().toLowerCase());
  const rows = table.rows.map(r => (r.c || []).map(cell => (cell ? cell.v : null)));

  const getIndex = (keywords) => headers.findIndex(h => keywords.some(k => h.includes(k)));

  const idxProc        = getIndex(['proc']);
  const idxUnidade     = getIndex(['unidade']);
  const idxEspec       = getIndex(['especific']);
  const idxFonte       = getIndex(['fonte']);
  const idxRubrica     = getIndex(['rubrica']);
  const idxStatus      = getIndex(['status']);
  const idxStatusAgrup = getIndex(['agrupado']);
  const idxOrcamento   = getIndex(['orçamen', 'orcamento']);
  const idxValor       = getIndex(['valor']);
  const idxSaldo       = getIndex(['saldo']);
  const idxExec        = getIndex(['executado', '%']);

  return rows
    .filter(r => r.some(cell => cell !== '' && cell !== null))
    .map((r, index) => {
      // Se a primeira linha tiver texto de cabeçalho repetido, ignora
      const strPrimeira = String(r[0] || '').toLowerCase();
      if (strPrimeira.includes('proc') || strPrimeira.includes('nº') || strPrimeira.includes('unidade')) {
        return null;
      }

      const fonteStr = idxFonte !== -1 && r[idxFonte] ? String(r[idxFonte]).trim() : (nomeAba.includes('INMETRO') ? 'INMETRO' : (nomeAba.includes('ITPS') ? 'ITPS' : 'FUNTEC'));
      const rubricaStr = idxRubrica !== -1 && r[idxRubrica] ? String(r[idxRubrica]).trim() : 'Material de Consumo';

      const keyExact = `${fonteStr.toLowerCase()}|${rubricaStr.toLowerCase()}`;
      const keyRubrica = rubricaStr.toLowerCase();

      let valOrcamentario = 0;
      if (mapOrcamento[keyExact] !== undefined) {
        valOrcamentario = mapOrcamento[keyExact];
      } else if (mapOrcamento[keyRubrica] !== undefined) {
        valOrcamentario = mapOrcamento[keyRubrica];
      } else {
        valOrcamentario = idxOrcamento !== -1 ? cleanNum(r[idxOrcamento]) : 0;
      }

      const valValor = idxValor !== -1 ? cleanNum(r[idxValor]) : (r[8] ? cleanNum(r[8]) : 0);
      const valSaldo = idxSaldo !== -1 ? cleanNum(r[idxSaldo]) : (r[9] ? cleanNum(r[9]) : 0);

      let exec = 0;
      if (valOrcamentario > 0) {
        exec = (valValor / valOrcamentario) * 100;
      } else if (idxExec !== -1 && r[idxExec] !== null) {
        exec = cleanNum(r[idxExec]);
        if (typeof r[idxExec] === 'number' && r[idxExec] <= 1.0) {
          exec = exec * 100;
        }
      }

      return {
        id: currentTotal + index + 1,
        proc: idxProc !== -1 && r[idxProc] ? String(r[idxProc]) : `Linha ${index + 2}`,
        unidade: idxUnidade !== -1 && r[idxUnidade] ? String(r[idxUnidade]).trim() : 'GEATEC',
        especificacao: idxEspec !== -1 && r[idxEspec] ? String(r[idxEspec]).trim() : '-',
        fonte: fonteStr,
        rubrica: rubricaStr,
        status: idxStatus !== -1 && r[idxStatus] ? String(r[idxStatus]).trim() : '-',
        statusAgrupado: idxStatusAgrup !== -1 && r[idxStatusAgrup] ? String(r[idxStatusAgrup]).trim() : 'Pendente',
        orcamentario: valOrcamentario,
        valor: valValor,
        saldo: valSaldo,
        percentExec: exec
      };
    })
    .filter(Boolean);
}

function processarObservacoes(table) {
  if (!table || !table.rows) return [];
  const rows = table.rows.map(r => (r.c || []).map(cell => (cell ? cell.v : null)));
  const observacoes = [];

  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const fonte = String(r[0] || '').trim();
    const pos = String(r[1] || '').trim();
    const txt = String(r[2] || '').trim();

    if (fonte && txt && !fonte.toLowerCase().includes('fonte')) {
      observacoes.push({
        fonte: fonte,
        posicao: pos,
        texto: txt
      });
    }
  }
  return observacoes;
}

/* =========================================================================
   RENDERIZAÇÃO DA INTERFACE E COMPONENTES VISUAIS
   ========================================================================= */

function onDataLoaded(response) {
  rawData = response.processos || [];
  currentObservacoes = response.observacoes || [];

  populateFilterOptions();
  applyFilters();
  document.getElementById('loader').style.display = 'none';
}

function populateFilterOptions() {
  const fontes = [...new Set(rawData.map(d => d.fonte).filter(Boolean))].sort();
  const rubricas = [...new Set(rawData.map(d => d.rubrica).filter(Boolean))].sort();

  const selectFonte = document.getElementById('filterFonte');
  const selectRubrica = document.getElementById('filterRubrica');

  const currentFonte = selectFonte.value;
  const currentRubrica = selectRubrica.value;

  selectFonte.innerHTML = '<option value="">(Todas)</option>';
  fontes.forEach(f => { selectFonte.innerHTML += `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`; });

  selectRubrica.innerHTML = '<option value="">(Todas)</option>';
  rubricas.forEach(r => { selectRubrica.innerHTML += `<option value="${escapeHtml(r)}">${escapeHtml(r)}</option>`; });

  selectFonte.value = currentFonte;
  selectRubrica.value = currentRubrica;
}

function resetFilters() {
  document.getElementById('filterFonte').value = '';
  document.getElementById('filterRubrica').value = '';
  clearSmartFilter();
  applyFilters();
}

function clearSmartFilter() {
  document.getElementById('smartFilterText').value = '';
  renderChartTopProc();
}

function applyFilters() {
  const selectedFonte = document.getElementById('filterFonte').value;
  const selectedRubrica = document.getElementById('filterRubrica').value;

  updateObservacoesDisplay(selectedFonte);

  currentFilteredData = rawData.filter(d => {
    const matchFonte = !selectedFonte || d.fonte === selectedFonte;
    const matchRubrica = !selectedRubrica || d.rubrica === selectedRubrica;
    return matchFonte && matchRubrica;
  });

  updateKPIs(currentFilteredData);
  renderChartUnidade(currentFilteredData);
  renderChartRubrica(currentFilteredData);
  renderChartStatus(currentFilteredData);
  renderChartTopProc();
}

function updateObservacoesDisplay(selectedFonte) {
  const positions = ['chart_unidade', 'chart_status', 'chart_rubrica', 'chart_top_proc'];
  
  positions.forEach(pos => {
    const el = document.getElementById('obs-' + pos.replace(/_/g, '-'));
    if (el) {
      el.style.display = 'none';
      el.innerHTML = '';
    }
  });

  if (!selectedFonte) return;

  const notas = currentObservacoes.filter(o => o.fonte === selectedFonte);

  notas.forEach(nota => {
    const el = document.getElementById('obs-' + (nota.posicao || '').replace(/_/g, '-'));
    if (el) {
      el.innerHTML = `<strong>Observação (${escapeHtml(selectedFonte)}):</strong> ${escapeHtml(nota.texto)}`;
      el.style.display = 'block';
    }
  });
}

function updateKPIs(data) {
  const totalProc = data.length;
  
  const totalEmpenho = data
    .filter(d => (d.statusAgrupado || '').toLowerCase().includes('empenho') || (d.status || '').toLowerCase().includes('empenho'))
    .reduce((sum, d) => sum + (d.valor || 0), 0);

  const totalLiquidado = data
    .filter(d => (d.statusAgrupado || '').toLowerCase().includes('liquida') || (d.status || '').toLowerCase().includes('liquida'))
    .reduce((sum, d) => sum + (d.valor || 0), 0);

  const totalPago = data
    .filter(d => (d.statusAgrupado || '').toLowerCase().includes('pago') || (d.status || '').toLowerCase().includes('pago'))
    .reduce((sum, d) => sum + (d.valor || 0), 0);

  document.getElementById('kpiTotalProc').innerText = totalProc.toLocaleString('pt-BR');
  document.getElementById('kpiEmpenho').innerText = formatBRL(totalEmpenho);
  document.getElementById('kpiLiquidado').innerText = formatBRL(totalLiquidado);
  document.getElementById('kpiPago').innerText = formatBRL(totalPago);
}

// Gráfico 1: Unidade Criadora
function renderChartUnidade(data) {
  const container = document.getElementById('chartUnidade');
  if (!data.length) { container.innerHTML = '<div class="no-data">Sem dados</div>'; return; }

  const map = {};
  data.forEach(d => { map[d.unidade] = (map[d.unidade] || 0) + (d.valor || 0); });

  const keys = Object.keys(map).sort((a,b) => map[b] - map[a]).slice(0, 5);
  const maxVal = Math.max(...Object.values(map)) || 1;

  let html = '<div class="bar-list">';
  keys.forEach((k, idx) => {
    const val = map[k];
    const pct = Math.min(100, Math.max(6, (val / maxVal) * 100));
    const color = idx === 0 ? '#2563eb' : '#3b82f6';
    html += `
      <div class="bar-row">
        <div class="bar-label" title="${escapeHtml(k)}">${escapeHtml(k)}</div>
        <div class="bar-track"><div class="bar-fill" style="width: ${pct}%; background: ${color};"></div></div>
        <div style="width: 100px; text-align: right; font-weight: 700;">${formatBRL(val)}</div>
      </div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

// Gráfico 2: Divergente + Tabela Resumo por Rubrica (CENTRALIZADO)
function renderChartRubrica(data) {
  const container = document.getElementById('chartRubrica');
  if (!data.length) { 
    container.innerHTML = '<div class="no-data">Sem dados para os filtros selecionados</div>'; 
    return; 
  }

  const map = {};

  data.forEach(d => {
    const r = d.rubrica || 'Geral';
    const key = `${d.fonte || ''}|${r}`;

    if (!map[r]) map[r] = { valor: 0, orcamentoMap: {} };
    
    map[r].valor += (d.valor || 0);
    map[r].orcamentoMap[key] = d.orcamentario || 0;
  });

  const keys = Object.keys(map);

  let maxScaleVal = 0;
  keys.forEach(k => {
    const item = map[k];
    const orcTotal = Object.values(item.orcamentoMap).reduce((a,b) => a + b, 0);
    const saldo = orcTotal - item.valor;
    maxScaleVal = Math.max(maxScaleVal, item.valor, Math.abs(saldo));
  });
  if (maxScaleVal === 0) maxScaleVal = 1;

  let totalOrcamento = 0;
  let totalValor = 0;

  let html = `
    <div style="width: 100%; max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px;">
      
      <div style="display: flex; justify-content: center; gap: 24px; font-size: 11px; font-weight: 700; background: #f8fafc; padding: 8px; border-radius: 6px; border: 1px solid #e2e8f0; width: 100%;">
        <span style="color: #2563eb; display: flex; align-items: center; gap: 6px;">
          <span style="width: 12px; height: 12px; background: #2563eb; border-radius: 2px;"></span> R$ Valor disponível (Saldo)
        </span>
        <span style="color: #dc2626; display: flex; align-items: center; gap: 6px;">
          <span style="width: 12px; height: 12px; background: #dc2626; border-radius: 2px;"></span> R$ Valor Utilizado
        </span>
      </div>

      <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 24px; align-items: center; justify-content: center; width: 100%;">
        
        <div style="display: flex; flex-direction: column; gap: 18px; width: 100%;">`;

  keys.forEach(k => {
    const item = map[k];
    const orcamento = Object.values(item.orcamentoMap).reduce((a,b) => a + b, 0);
    const valorUtilizado = item.valor;
    const saldoCalculado = orcamento - valorUtilizado;

    totalOrcamento += orcamento;
    totalValor += valorUtilizado;

    const pctSaldo = Math.min(100, (Math.abs(saldoCalculado) / maxScaleVal) * 80);
    const pctValor = Math.min(100, (valorUtilizado / maxScaleVal) * 80);

    html += `
      <div style="display: flex; align-items: center; gap: 10px; font-size: 11px;">
        <div style="width: 130px; font-weight: 700; color: #334155; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(k)}">
          ${escapeHtml(k)}
        </div>

        <div style="flex: 1; display: flex; height: 30px; position: relative; background: #fafafa; border-radius: 4px; padding: 2px 0;">
          
          <div style="flex: 1; display: flex; align-items: center; justify-content: flex-end; padding-right: 2px; border-right: 2px solid #334155;">
            <span style="font-size: 11px; font-weight: 800; color: #2563eb; margin-right: 8px; white-space: nowrap;">
              ${formatBRL(saldoCalculado)}
            </span>
            <div style="height: 20px; width: ${pctSaldo}%; background: #2563eb; border-radius: 3px 0 0 3px; min-width: ${saldoCalculado !== 0 ? '4px' : '0px'};"></div>
          </div>

          <div style="flex: 1; display: flex; align-items: center; justify-content: flex-start; padding-left: 2px;">
            <div style="height: 20px; width: ${pctValor}%; background: #dc2626; border-radius: 0 3px 3px 0; min-width: ${valorUtilizado > 0 ? '4px' : '0px'};"></div>
            <span style="font-size: 11px; font-weight: 800; color: #dc2626; margin-left: 8px; white-space: nowrap;">
              ${formatBRL(valorUtilizado)}
            </span>
          </div>

        </div>
      </div>`;
  });

  const totalSaldoAll = totalOrcamento - totalValor;
  const totalExecAll = totalOrcamento > 0 ? (totalValor / totalOrcamento) * 100 : 0;

  html += `
        </div>

        <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); width: 100%;">
          <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
            <thead>
              <tr style="background: #1e293b; color: #ffffff;">
                <th style="padding: 9px 10px; text-align: left; font-weight: 700;">Rubrica</th>
                <th style="padding: 9px 10px; text-align: right; font-weight: 700;">R$ Orçamentário</th>
                <th style="padding: 9px 10px; text-align: right; font-weight: 700;">R$ Valor</th>
                <th style="padding: 9px 10px; text-align: right; font-weight: 700;">R$ Saldo</th>
                <th style="padding: 9px 10px; text-align: right; font-weight: 700;">% Execução</th>
              </tr>
            </thead>
            <tbody>`;

  keys.forEach(k => {
    const item = map[k];
    const orcamento = Object.values(item.orcamentoMap).reduce((a,b) => a + b, 0);
    const valorUtilizado = item.valor;
    const saldo = orcamento - valorUtilizado;
    const execPct = orcamento > 0 ? (valorUtilizado / orcamento) * 100 : 0;

    html += `
      <tr style="border-bottom: 1px solid #e2e8f0;">
        <td style="padding: 9px 10px; font-weight: 600; color: #334155;">${escapeHtml(k)}</td>
        <td style="padding: 9px 10px; text-align: right; color: #475569;">${formatBRL(orcamento)}</td>
        <td style="padding: 9px 10px; text-align: right; font-weight: 600; color: #0f172a;">${formatBRL(valorUtilizado)}</td>
        <td style="padding: 9px 10px; text-align: right; font-weight: 700; color: ${saldo < 0 ? '#dc2626' : '#2563eb'};">${formatBRL(saldo)}</td>
        <td style="padding: 9px 10px; text-align: right; font-weight: 700; color: ${execPct > 100 ? '#dc2626' : '#16a34a'};">${execPct.toFixed(2)}%</td>
      </tr>`;
  });

  html += `
            </tbody>
            <tfoot>
              <tr style="background: #f1f5f9; font-weight: 800; border-top: 2px solid #cbd5e1;">
                <td style="padding: 10px; color: #0f172a;">Total</td>
                <td style="padding: 10px; text-align: right; color: #0f172a;">${formatBRL(totalOrcamento)}</td>
                <td style="padding: 10px; text-align: right; color: #0f172a;">${formatBRL(totalValor)}</td>
                <td style="padding: 10px; text-align: right; color: ${totalSaldoAll < 0 ? '#dc2626' : '#2563eb'};">${formatBRL(totalSaldoAll)}</td>
                <td style="padding: 10px; text-align: right; color: #0f172a;">${totalExecAll.toFixed(2)}%</td>
              </tr>
            </tfoot>
          </table>
        </div>

      </div>
    </div>`;

  container.innerHTML = html;
}

// Gráfico 3: Status Agrupado
function renderChartStatus(data) {
  const container = document.getElementById('chartStatus');
  if (!data.length) { container.innerHTML = '<div class="no-data">Sem dados</div>'; return; }

  const map = {};

  data.forEach(d => {
    const stAgrupado = (d.statusAgrupado || '').toLowerCase();
    const st = (d.status || '').toLowerCase();
    let key = '';

    if (stAgrupado.includes('pago') || st.includes('pago')) {
      key = 'Processo pago';
    } else if (stAgrupado.includes('liquida') || st.includes('liquida')) {
      key = 'Valor Liquidado';
    } else if (stAgrupado.includes('empenho') || st.includes('empenho')) {
      key = 'Com empenho';
    } else if (stAgrupado.includes('licita') || st.includes('licita')) {
      key = 'Em Licitação';
    } else if (stAgrupado.includes('analise') || st.includes('analise') || stAgrupado.includes('análise') || st.includes('análise')) {
      key = 'Em análise documental';
    } else {
      key = d.statusAgrupado || d.status || 'Outros';
    }

    map[key] = (map[key] || 0) + (Number(d.valor) || 0);
  });

  const getStatusRank = (statusStr) => {
    const s = statusStr.toLowerCase();
    if (s.includes('analise') || s.includes('análise')) return 1;
    if (s.includes('licita')) return 2;
    if (s.includes('empenho')) return 3;
    if (s.includes('liquida')) return 4;
    if (s.includes('pago')) return 5;
    return 99;
  };

  const keys = Object.keys(map).sort((a, b) => getStatusRank(a) - getStatusRank(b));
  const maxVal = Math.max(...Object.values(map)) || 1;

  const statusColors = { 
    1: '#f59e0b',
    2: '#8b5cf6',
    3: '#2563eb',
    4: '#f59e0b',
    5: '#10b981',
    99: '#64748b'
  };

  let html = '<div class="col-chart">';
  keys.forEach((k) => {
    const val = map[k];
    const heightPct = Math.min(100, Math.max(12, (val / maxVal) * 100));
    const rank = getStatusRank(k);
    const color = statusColors[rank] || '#3b82f6';

    html += `
      <div class="col-item">
        <div style="font-size: 9px; font-weight: 700; white-space: nowrap;">${formatBRL(val)}</div>
        <div class="col-bar-container">
          <div class="col-bar" style="height: ${heightPct}%; background: ${color};"></div>
        </div>
        <div class="col-lbl" title="${escapeHtml(k)}">${escapeHtml(k)}</div>
      </div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

// Gráfico 4: Tabela de Processos (Aplica o Filtro Inteligente Local incluindo Unidade)
function renderChartTopProc() {
  const container = document.getElementById('chartTopProc');
  const baseData = currentFilteredData || [];

  if (!baseData.length) { 
    container.innerHTML = '<div class="no-data">Sem dados para os filtros selecionados</div>'; 
    return; 
  }

  const smartField = document.getElementById('smartFilterField').value;
  const smartText = (document.getElementById('smartFilterText').value || '').trim().toLowerCase();

  const badge = document.getElementById('activeFilterBadge');
  const badgeText = document.getElementById('activeFilterText');

  if (smartText) {
    const fieldLabels = {
      'all': 'Geral',
      'proc': 'Nº Proc.',
      'unidade': 'Unidade',
      'espec': 'Espec.',
      'valor': 'Valor'
    };
    badgeText.innerText = `${fieldLabels[smartField] || 'Filtro'}: "${smartText}"`;
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }

  const filteredProc = baseData.filter(d => {
    if (!smartText) return true;

    const procStr = String(d.proc || '').toLowerCase();
    const unidadeStr = String(d.unidade || '').toLowerCase();
    const especStr = String(d.especificacao || '').toLowerCase();
    const valStr = String(d.valor || '').toLowerCase();
    const valBRL = formatBRL(d.valor || 0).toLowerCase();

    if (smartField === 'proc') {
      return procStr.includes(smartText);
    } else if (smartField === 'unidade') {
      return unidadeStr.includes(smartText);
    } else if (smartField === 'espec') {
      return especStr.includes(smartText);
    } else if (smartField === 'valor') {
      return valStr.includes(smartText) || valBRL.includes(smartText);
    } else {
      return procStr.includes(smartText) || 
             unidadeStr.includes(smartText) || 
             especStr.includes(smartText) || 
             valStr.includes(smartText) || 
             valBRL.includes(smartText);
    }
  });

  if (!filteredProc.length) {
    container.innerHTML = '<div class="no-data" style="padding: 20px;">Nenhum processo encontrado para esta busca na tabela.</div>';
    return;
  }

  const sorted = [...filteredProc].sort((a, b) => (b.valor || 0) - (a.valor || 0));

  let html = `
    <div class="scrollable-proc-container">
      <table class="custom-table">
        <thead>
          <tr>
            <th style="white-space: nowrap;">Nº Processo</th>
            <th style="white-space: nowrap;">Fonte de Recurso</th>
            <th style="white-space: nowrap;">Unidade</th>
            <th>Especificação</th>
            <th style="text-align: right; white-space: nowrap;">Valor R$</th>
            <th style="white-space: nowrap;">Rubrica</th>
            <th style="text-align: center; white-space: nowrap;">% Rubrica</th>
          </tr>
        </thead>
        <tbody>`;

  sorted.forEach(item => {
    const realPct = Number(item.percentExec || 0);
    const barWidth = Math.min(100, Math.max(0, realPct));

    const execColor = realPct > 100 
      ? '#ef4444' 
      : realPct >= 80 
        ? '#10b981' 
        : realPct >= 40 
          ? '#f59e0b' 
          : '#3b82f6';

    const especLimpa = item.especificacao || '-';

    html += `
      <tr onclick="openDetailModal(${item.id})" title="Clique para abrir detalhes completos">
        <td style="font-weight:700; color:#2563eb; white-space: nowrap;">${escapeHtml(item.proc)}</td>
        <td style="white-space: nowrap;">${escapeHtml(item.fonte || '-')}</td>
        <td style="white-space: nowrap;">${escapeHtml(item.unidade || '-')}</td>
        <td style="max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${escapeHtml(truncarTexto(especLimpa, 45))}
        </td>
        <td style="font-weight:600; text-align: right; white-space: nowrap;">${formatBRL(item.valor)}</td>
        <td style="font-weight:600; color:#475569; white-space: nowrap;">${escapeHtml(item.rubrica || '-')}</td>
        <td style="min-width: 120px;">
          <div style="display:flex; align-items:center; gap:6px;">
            <div style="flex:1; background:#e2e8f0; height:6px; border-radius:3px; overflow:hidden;">
              <div style="width:${barWidth}%; background:${execColor}; height:100%;"></div>
            </div>
            <span style="font-size:10px; font-weight:700; color:${execColor}; min-width:36px; text-align:right;">${realPct.toFixed(0)}%</span>
          </div>
        </td>
      </tr>`;
  });

  html += '</tbody></table></div>';
  container.innerHTML = html;
}

function truncarTexto(str, max = 45) {
  if (!str) return '-';
  const s = String(str).trim();
  return s.length > max ? s.substring(0, max) + '...' : s;
}

/* =========================================================================
   MODAL DE DETALHES DO PROCESSO
   ========================================================================= */

function openDetailModal(id) {
  const proc = rawData.find(d => d.id === id);
  if (!proc) return;

  const procFonte = (proc.fonte || '').trim();
  const procRubrica = (proc.rubrica || '').trim();

  let totalGastoFonteRubrica = 0;
  let orcamentoFonteRubrica = Number(proc.orcamentario) || 0;

  rawData.forEach(item => {
    const itemFonte = (item.fonte || '').trim();
    const itemRubrica = (item.rubrica || '').trim();

    if (itemFonte.toLowerCase() === procFonte.toLowerCase() && 
        itemRubrica.toLowerCase() === procRubrica.toLowerCase()) {
      totalGastoFonteRubrica += (Number(item.valor) || 0);
      if (item.orcamentario && item.orcamentario > 0) {
        orcamentoFonteRubrica = Number(item.orcamentario);
      }
    }
  });

  const saldoDisponivel = orcamentoFonteRubrica - totalGastoFonteRubrica;
  const pctExecucao = orcamentoFonteRubrica > 0 ? (totalGastoFonteRubrica / orcamentoFonteRubrica) * 100 : 0;

  document.getElementById('modalProcNumero').innerText = `Processo ${proc.proc || '-'}`;
  document.getElementById('modalProcSub').innerText = `${proc.unidade || 'Unidade'} • ${procFonte || 'Fonte'}`;

  document.getElementById('modalProcNumText').innerText = proc.proc || '-';
  document.getElementById('modalProcFonte').innerText = procFonte || '-';
  document.getElementById('modalProcUnidade').innerText = proc.unidade || '-';
  document.getElementById('modalProcRubrica').innerText = procRubrica || '-';
  document.getElementById('modalProcStatus').innerText = proc.status || '-';
  document.getElementById('modalProcStatusAgrupado').innerText = proc.statusAgrupado || '-';

  document.getElementById('modalProcOrcado').innerText = formatBRL(orcamentoFonteRubrica);
  document.getElementById('modalProcValor').innerText = formatBRL(proc.valor);
  
  const elSaldo = document.getElementById('modalProcSaldo');
  elSaldo.innerText = formatBRL(saldoDisponivel);
  elSaldo.style.color = saldoDisponivel < 0 ? '#dc2626' : '#2563eb';

  const elExec = document.getElementById('modalProcExec');
  elExec.innerText = `${pctExecucao.toFixed(2)}% (Total Gasto: ${formatBRL(totalGastoFonteRubrica)})`;
  elExec.style.color = pctExecucao > 100 ? '#dc2626' : '#16a34a';

  document.getElementById('modalProcEspec').innerText = proc.especificacao || 'Nenhuma especificação cadastrada.';

  document.getElementById('procDetailModal').style.display = 'flex';
}

function closeProcModal(event) {
  if (event && event.target !== event.currentTarget) return;
  document.getElementById('procDetailModal').style.display = 'none';
}

/* =========================================================================
   MODAL DE OBSERVAÇÕES
   ========================================================================= */

function getLocalObservacoes() {
  try {
    const data = localStorage.getItem(STORAGE_OBS_KEY);
    return data ? JSON.parse(data) : [];
  } catch (e) {
    return [];
  }
}

function setLocalObservacoes(obsList) {
  try {
    localStorage.setItem(STORAGE_OBS_KEY, JSON.stringify(obsList));
  } catch (e) {}
}

function openObsModal() {
  const fontes = [...new Set(rawData.map(d => d.fonte).filter(Boolean))].sort();
  const select = document.getElementById('newObsFonte');
  select.innerHTML = fontes.map(f => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join('');

  renderObsTable();
  document.getElementById('obsModal').style.display = 'flex';
}

function closeObsModal() {
  document.getElementById('obsModal').style.display = 'none';
}

function renderObsTable() {
  const tbody = document.getElementById('obsTableBody');
  tbody.innerHTML = currentObservacoes.map((obs, idx) => `
    <tr>
      <td style="padding:8px; border-bottom:1px solid #f1f5f9;"><b>${escapeHtml(obs.fonte)}</b></td>
      <td style="padding:8px; border-bottom:1px solid #f1f5f9;">${escapeHtml(POS_LABELS[obs.posicao] || obs.posicao)}</td>
      <td style="padding:8px; border-bottom:1px solid #f1f5f9; max-width:260px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(obs.texto)}">${escapeHtml(obs.texto)}</td>
      <td style="padding:8px; border-bottom:1px solid #f1f5f9; text-align:center;">
        <button onclick="removeObs(${idx})" style="background:#ef4444; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;">✕</button>
      </td>
    </tr>
  `).join('');
}

function addObs() {
  const fonte = document.getElementById('newObsFonte').value;
  const posicao = document.getElementById('newObsPosicao').value;
  const texto = document.getElementById('newObsTexto').value.trim();

  if (!fonte) {
    alert('Selecione uma Fonte de Recurso.');
    return;
  }
  if (!texto) {
    alert('Digite o texto da observação.');
    return;
  }

  const index = currentObservacoes.findIndex(o => o.fonte === fonte && o.posicao === posicao);
  if (index >= 0) {
    currentObservacoes[index].texto = texto;
  } else {
    currentObservacoes.push({ fonte, posicao, texto });
  }

  document.getElementById('newObsTexto').value = '';
  renderObsTable();
}

function removeObs(index) {
  currentObservacoes.splice(index, 1);
  renderObsTable();
}

function saveObsFromUI() {
  setLocalObservacoes(currentObservacoes);
  closeObsModal();
  applyFilters();
}

/* =========================================================================
   UTILITÁRIOS
   ========================================================================= */

function formatBRL(val) {
  return (val || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function escapeHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
