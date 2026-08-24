/**
 * ========================================================
 * JAVASCRIPT - PAINEL ADMINISTRATIVO DE RECADASTRAMENTO (GERH)
 * Padrão Visual Contratos/PCA com Modais Modernos de Confirmação
 * ========================================================
 */

// URL base do Backend FastAPI (Apache faz proxy reverso /api/ → localhost:8000)
const API_BASE_URL = window.location.origin;

// Chaves de Armazenamento Local
const STORAGE_AUTH_KEY = 'ITPS_GERH_ADMIN_TOKEN';
const STORAGE_USER_KEY = 'ITPS_GERH_ADMIN_USER';
const STORAGE_SAVED_USER = 'ITPS_GERH_SAVED_USER';
const STORAGE_SAVED_PASS = 'ITPS_GERH_SAVED_PASS';
const STORAGE_REMEMBER = 'ITPS_GERH_REMEMBER_CREDENTIALS';

let paginaAtual = 1;
let itensPorPagina = 20;
let totalRegistros = 0;
let totalPaginas = 1;
let timeoutBusca = null;
let listaRegistros = [];
let servidorSelecionado = null;
let modoEdicaoAtivo = false;
let dependentesEmEdicao = [];
let intervalAutoRefresh = null;
let callbackConfirmacaoPendente = null;

document.addEventListener('DOMContentLoaded', () => {
  carregarCredenciaisMemorizadas();
  verificarSessaoAdmin();
  iniciarAutoRefresh();
});

function iniciarAutoRefresh() {
  if (intervalAutoRefresh) clearInterval(intervalAutoRefresh);
  // Atualiza automaticamente a cada 8 segundos em segundo plano
  intervalAutoRefresh = setInterval(() => {
    autoAtualizarPainel();
  }, 8000);

  // Atualiza imediatamente quando a janela/aba ganha foco
  window.addEventListener('focus', () => {
    autoAtualizarPainel();
  });
}

function autoAtualizarPainel() {
  const overlay = document.getElementById('loginOverlay');
  const modal = document.getElementById('modalDetalhes');
  const modalDoc = document.getElementById('modalDocViewer');
  const modalConf = document.getElementById('modalConfirmacao');

  // Não atualiza se estiver na tela de login ou com qualquer modal aberto
  if (overlay && !overlay.classList.contains('hidden')) return;
  if (modal && !modal.classList.contains('hidden')) return;
  if (modalDoc && !modalDoc.classList.contains('hidden')) return;
  if (modalConf && !modalConf.classList.contains('hidden')) return;

  carregarDados(true);
}

/* ========================================================
   1. AUTENTICAÇÃO E MEMORIZAÇÃO DE CREDENCIAIS
   ======================================================== */

function carregarCredenciaisMemorizadas() {
  const remember = localStorage.getItem(STORAGE_REMEMBER) !== 'false';
  const savedUser = localStorage.getItem(STORAGE_SAVED_USER) || 'gerh';
  const savedPass = localStorage.getItem(STORAGE_SAVED_PASS) || 'itps123';

  const chkRemember = document.getElementById('chkLembrarCredenciais');
  const inputUser = document.getElementById('loginUsuario');
  const inputPass = document.getElementById('loginSenha');

  if (chkRemember) chkRemember.checked = remember;

  if (remember) {
    if (inputUser && savedUser) inputUser.value = savedUser;
    if (inputPass && savedPass) inputPass.value = savedPass;
  }
}

function salvarCredenciaisLocais(usuario, senha, lembrar) {
  if (lembrar) {
    localStorage.setItem(STORAGE_REMEMBER, 'true');
    localStorage.setItem(STORAGE_SAVED_USER, usuario);
    localStorage.setItem(STORAGE_SAVED_PASS, senha);
  } else {
    localStorage.setItem(STORAGE_REMEMBER, 'false');
    localStorage.removeItem(STORAGE_SAVED_USER);
    localStorage.removeItem(STORAGE_SAVED_PASS);
  }
}

function verificarSessaoAdmin() {
  const token = localStorage.getItem(STORAGE_AUTH_KEY) || sessionStorage.getItem(STORAGE_AUTH_KEY);
  const user = localStorage.getItem(STORAGE_USER_KEY) || sessionStorage.getItem(STORAGE_USER_KEY);

  const overlay = document.getElementById('loginOverlay');
  const appWrapper = document.getElementById('adminAppWrapper');

  if (token && user) {
    if (overlay) overlay.classList.add('hidden');
    if (appWrapper) appWrapper.classList.remove('admin-app-hidden');
    
    const sessionName = document.getElementById('sessionUserName');
    if (sessionName) sessionName.innerHTML = `<i class="fa-solid fa-circle-user"></i> ${user}`;
    
    carregarDados();
  } else {
    if (overlay) overlay.classList.remove('hidden');
    if (appWrapper) appWrapper.classList.add('admin-app-hidden');
    
    const inputUser = document.getElementById('loginUsuario');
    if (inputUser && !inputUser.value) inputUser.focus();
  }
}

async function realizarLogin(e) {
  if (e) e.preventDefault();

  const usuarioInput = document.getElementById('loginUsuario').value.trim();
  const senhaInput = document.getElementById('loginSenha').value.trim();
  const lembrar = document.getElementById('chkLembrarCredenciais')?.checked ?? true;
  const btnSubmit = document.getElementById('btnLoginSubmit');
  const errorMsg = document.getElementById('loginErrorMsg');
  const errorText = document.getElementById('loginErrorText');

  if (!usuarioInput || !senhaInput) {
    if (errorMsg) errorMsg.classList.remove('hidden');
    if (errorText) errorText.textContent = 'Informe o login e a senha.';
    return;
  }

  if (btnSubmit) {
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Entrando...`;
  }
  if (errorMsg) errorMsg.classList.add('hidden');

  try {
    const response = await fetch(`${API_BASE_URL}/api/recadastramento/admin/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario: usuarioInput, senha: senhaInput })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.detail || 'Usuário ou senha incorretos.');
    }

    // Salva sessão
    sessionStorage.setItem(STORAGE_AUTH_KEY, data.token);
    sessionStorage.setItem(STORAGE_USER_KEY, data.usuario || 'GERH / RH');
    localStorage.setItem(STORAGE_AUTH_KEY, data.token);
    localStorage.setItem(STORAGE_USER_KEY, data.usuario || 'GERH / RH');

    // Salva ou remove credenciais de login e senha conforme o checkbox
    salvarCredenciaisLocais(usuarioInput, senhaInput, lembrar);

    showToast('Acesso autorizado! Carregando painel...', 'success');
    verificarSessaoAdmin();

  } catch (err) {
    console.error('Erro no login:', err);
    if (errorMsg) errorMsg.classList.remove('hidden');
    if (errorText) errorText.textContent = err.message || 'Credenciais inválidas. Tente novamente.';
  } finally {
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = `<span>Entrar</span>`;
    }
  }
}

function solicitarLogout() {
  abrirModalConfirmacao({
    titulo: 'Encerrar Sessão',
    mensagem: 'Deseja sair do painel administrativo do GERH com segurança?',
    detalhe: 'Sua sessão atual será encerrada no navegador.',
    tipo: 'warning',
    icone: 'fa-solid fa-power-off',
    textoBotao: 'Sim, Encerrar Sessão',
    classeBotao: 'btn-danger',
    onConfirmar: () => {
      localStorage.removeItem(STORAGE_AUTH_KEY);
      localStorage.removeItem(STORAGE_USER_KEY);
      sessionStorage.removeItem(STORAGE_AUTH_KEY);
      sessionStorage.removeItem(STORAGE_USER_KEY);
      showToast('Sessão encerrada com sucesso.', 'info');
      carregarCredenciaisMemorizadas();
      verificarSessaoAdmin();
    }
  });
}

function toggleSenhaVisivel(inputId) {
  const input = document.getElementById(inputId);
  const icon = document.getElementById(`toggleIcon_${inputId}`);
  if (!input) return;

  if (input.type === 'password') {
    input.type = 'text';
    if (icon) icon.className = 'fa-regular fa-eye-slash';
  } else {
    input.type = 'password';
    if (icon) icon.className = 'fa-regular fa-eye';
  }
}

/* ========================================================
   2. CARREGAMENTO E BUSCA DE DADOS
   ======================================================== */

async function carregarDados(silencioso = false) {
  const loading = document.getElementById('tableLoading');
  if (!silencioso && loading) loading.classList.remove('hidden');

  try {
    const busca = document.getElementById('filtroBusca').value.trim();
    const status = document.getElementById('filtroStatus').value;
    const escolaridade = document.getElementById('filtroEscolaridade').value;
    const dataInicio = document.getElementById('filtroDataInicio').value;
    const dataFim = document.getElementById('filtroDataFim').value;

    const params = new URLSearchParams({
      page: paginaAtual,
      page_size: itensPorPagina
    });

    if (busca) params.append('busca', busca);
    if (status && status !== 'TODOS') params.append('status', status);
    if (escolaridade && escolaridade !== 'TODAS') params.append('escolaridade', escolaridade);
    if (dataInicio) params.append('data_inicio', dataInicio);
    if (dataFim) params.append('data_fim', dataFim);

    const response = await fetch(`${API_BASE_URL}/api/recadastramento/admin/listar?${params.toString()}`);
    if (!response.ok) throw new Error(`Erro HTTP ${response.status} ao consultar API.`);

    const data = await response.json();
    if (data.success) {
      listaRegistros = data.items || [];
      totalRegistros = data.total || 0;
      totalPaginas = data.total_pages || 1;
      
      atualizarMetricas(data.metricas);
      renderizarTabela(listaRegistros);
      renderizarPaginacao();
    }
  } catch (error) {
    if (!silencioso) {
      console.error('Erro ao carregar dados:', error);
      showToast(`Erro ao carregar registros: ${error.message}`, 'error');
    }
  } finally {
    if (loading) loading.classList.add('hidden');
  }
}

function atualizarMetricas(m) {
  if (!m) return;
  document.getElementById('kpiTotalGeral').textContent = m.total_geral || 0;
  document.getElementById('kpiHoje').textContent = m.total_hoje || 0;
  document.getElementById('kpiEnviados').textContent = m.total_enviados || 0;
  document.getElementById('kpiAprovados').textContent = m.total_aprovados || 0;
  document.getElementById('kpiDependentes').textContent = m.total_com_dependentes || 0;
}

/* ========================================================
   3. RENDERIZAÇÃO DA TABELA
   ======================================================== */

function renderizarTabela(itens) {
  const tbody = document.getElementById('tableBody');
  const emptyState = document.getElementById('emptyState');
  const badgeTotal = document.getElementById('badgeTotalRegistros');

  if (badgeTotal) {
    badgeTotal.textContent = `${totalRegistros} registro(s)`;
  }

  if (!tbody) return;
  tbody.innerHTML = '';

  if (!itens || itens.length === 0) {
    if (emptyState) emptyState.classList.remove('hidden');
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');

  itens.forEach(item => {
    const tr = document.createElement('tr');
    
    // Iniciais para Avatar
    const partesNome = (item.nome_completo || 'S').trim().split(' ');
    const iniciais = partesNome.length > 1
      ? (partesNome[0][0] + partesNome[partesNome.length - 1][0]).toUpperCase()
      : partesNome[0].substring(0, 2).toUpperCase();

    // Foto 3x4
    let avatarHtml = `<div class="avatar-circle">${iniciais}</div>`;
    if (item.doc_foto3x4_path) {
      avatarHtml = `<div class="avatar-circle"><img src="${API_BASE_URL}/${item.doc_foto3x4_path}" alt="Foto 3x4" onerror="this.parentElement.innerHTML='${iniciais}'"></div>`;
    }

    // WhatsApp limpo
    const whatsLimpo = (item.whatsapp || '').replace(/\D/g, '');
    const whatsLink = whatsLimpo ? `https://wa.me/55${whatsLimpo}` : '#';

    // Status Badge
    const statusClass = obterClasseStatus(item.status);

    // Documentos anexados
    const docsHtml = gerarChipsDocumentos(item);

    // Dados Funcionais atribuídos pelo RH
    let funcHtml = '';
    if (item.cargo || item.setor || item.vinculo) {
      funcHtml = `
        <div class="func-cell">
          <span class="func-cargo">${item.cargo || 'Cargo a definir'}</span>
          <span class="func-setor"><i class="fa-solid fa-briefcase"></i> ${item.setor || 'Setor não informado'}</span>
          ${item.vinculo ? `<small class="text-muted" style="font-size:0.75rem;">${item.vinculo}</small>` : ''}
        </div>
      `;
    } else {
      funcHtml = `<span class="badge-func-empty"><i class="fa-solid fa-triangle-exclamation"></i> Pendente RH</span>`;
    }

    // Dependentes count
    const qtdDep = (item.dependentes && item.dependentes.length > 0) ? item.dependentes.length : 0;
    const depBadge = qtdDep > 0 
      ? `<span class="status-pill status-em-analise"><i class="fa-solid fa-users"></i> ${qtdDep} dep.</span>`
      : `<span class="text-muted" style="font-size: 0.8rem;">Nenhum</span>`;

    tr.innerHTML = `
      <td><span class="protocol-cell">${item.protocolo || '-'}</span></td>
      <td>
        <div class="servidor-cell">
          ${avatarHtml}
          <div class="servidor-info">
            <span class="servidor-nome">${item.nome_completo || '-'}</span>
            <span class="servidor-cpf">CPF: ${item.cpf || '-'}</span>
          </div>
        </div>
      </td>
      <td>
        <div class="contact-cell">
          <a href="${whatsLink}" target="_blank" class="contact-link contact-whatsapp" title="Abrir WhatsApp Web">
            <i class="fa-brands fa-whatsapp"></i> ${item.whatsapp || '-'}
          </a>
          <a href="mailto:${item.email_pessoal}" class="contact-link" title="Enviar e-mail">
            <i class="fa-regular fa-envelope"></i> ${item.email_pessoal || '-'}
          </a>
        </div>
      </td>
      <td>${funcHtml}</td>
      <td>
        <strong>${item.escolaridade || '-'}</strong>
        ${item.curso_formacao ? `<br><small class="text-muted">${item.curso_formacao}</small>` : ''}
      </td>
      <td>
        <span>${item.cidade || '-'}/${item.uf || '-'}</span>
        ${item.bairro ? `<br><small class="text-muted">${item.bairro}</small>` : ''}
      </td>
      <td>${depBadge}</td>
      <td><div class="docs-chips-row">${docsHtml}</div></td>
      <td><span style="font-size: 0.82rem; white-space: nowrap;">${item.data_envio_formatada || '-'}</span></td>
      <td><span class="status-pill ${statusClass}">${item.status || 'ENVIADO'}</span></td>
      <td>
        <div class="action-buttons-cell">
          <button type="button" class="btn-action-icon" onclick="abrirFichaDetalhada(${item.id})" title="Ver ficha e editar dados">
            <i class="fa-solid fa-user-pen"></i>
          </button>
          <button type="button" class="btn-action-icon btn-delete" onclick="solicitarExclusao(${item.id}, '${item.protocolo}', '${item.nome_completo}')" title="Excluir cadastro">
            <i class="fa-regular fa-trash-can"></i>
          </button>
        </div>
      </td>
    `;

    tbody.appendChild(tr);
  });
}

function obterClasseStatus(status) {
  const s = (status || '').toUpperCase();
  if (s.includes('APROV')) return 'status-aprovado';
  if (s.includes('ANÁLISE') || s.includes('ANALISE')) return 'status-em-analise';
  if (s.includes('PEND')) return 'status-pendente';
  return 'status-enviado';
}

function gerarChipsDocumentos(item) {
  let html = '';
  if (item.doc_foto3x4_path) {
    html += `<span class="doc-chip" onclick="abrirVisualizadorDoc('${item.doc_foto3x4_path}', 'Foto 3x4 - ${item.nome_completo}')" title="Foto 3x4"><i class="fa-solid fa-camera"></i> Foto</span>`;
  }
  if (item.doc_identificacao_path) {
    html += `<span class="doc-chip" onclick="abrirVisualizadorDoc('${item.doc_identificacao_path}', 'RG/CNH - ${item.nome_completo}')" title="RG/CNH"><i class="fa-solid fa-id-card"></i> RG/CNH</span>`;
  }
  if (item.doc_residencia_path) {
    html += `<span class="doc-chip" onclick="abrirVisualizadorDoc('${item.doc_residencia_path}', 'Comprovante Residência - ${item.nome_completo}')" title="Residência"><i class="fa-solid fa-house"></i> Resid.</span>`;
  }
  if (item.doc_titulo_path) {
    html += `<span class="doc-chip" onclick="abrirVisualizadorDoc('${item.doc_titulo_path}', 'Título de Eleitor - ${item.nome_completo}')" title="Título de Eleitor"><i class="fa-solid fa-check-to-slot"></i> Título</span>`;
  }
  if (item.doc_ctps_path) {
    html += `<span class="doc-chip" onclick="abrirVisualizadorDoc('${item.doc_ctps_path}', 'CTPS - ${item.nome_completo}')" title="Carteira de Trabalho"><i class="fa-solid fa-address-book"></i> CTPS</span>`;
  }
  if (item.doc_escolaridade_path) {
    html += `<span class="doc-chip" onclick="abrirVisualizadorDoc('${item.doc_escolaridade_path}', 'Diploma/Escolaridade - ${item.nome_completo}')" title="Comprovante de Escolaridade"><i class="fa-solid fa-graduation-cap"></i> Diploma</span>`;
  }
  if (item.doc_dependentes_paths && item.doc_dependentes_paths.length > 0) {
    html += `<span class="doc-chip" onclick="abrirVisualizadorDoc('${item.doc_dependentes_paths[0]}', 'Doc. Dependente - ${item.nome_completo}')" title="Documentos dos Dependentes"><i class="fa-solid fa-folder-open"></i> Dep. (${item.doc_dependentes_paths.length})</span>`;
  }
  return html || '<span class="text-muted" style="font-size: 0.75rem;">Nenhum</span>';
}

/* ========================================================
   4. PAGINAÇÃO E FILTROS
   ======================================================== */

function renderizarPaginacao() {
  const info = document.getElementById('paginationInfo');
  const btnPrev = document.getElementById('btnPagePrev');
  const btnNext = document.getElementById('btnPageNext');
  const pageNumbers = document.getElementById('pageNumbers');

  const inicio = totalRegistros > 0 ? (paginaAtual - 1) * itensPorPagina + 1 : 0;
  const fim = Math.min(paginaAtual * itensPorPagina, totalRegistros);

  if (info) {
    info.textContent = `Mostrando ${inicio} - ${fim} de ${totalRegistros} registros`;
  }

  if (btnPrev) btnPrev.disabled = (paginaAtual <= 1);
  if (btnNext) btnNext.disabled = (paginaAtual >= totalPaginas);

  if (pageNumbers) {
    pageNumbers.innerHTML = '';
    const maxBtns = 5;
    let startPage = Math.max(1, paginaAtual - Math.floor(maxBtns / 2));
    let endPage = Math.min(totalPaginas, startPage + maxBtns - 1);

    if (endPage - startPage + 1 < maxBtns) {
      startPage = Math.max(1, endPage - maxBtns + 1);
    }

    for (let p = startPage; p <= endPage; p++) {
      const btn = document.createElement('button');
      btn.className = `page-number-btn ${p === paginaAtual ? 'active' : ''}`;
      btn.textContent = p;
      btn.onclick = () => irParaPagina(p);
      pageNumbers.appendChild(btn);
    }
  }
}

function irParaPagina(p) {
  if (p >= 1 && p <= totalPaginas && p !== paginaAtual) {
    paginaAtual = p;
    carregarDados();
  }
}

function paginaAnterior() {
  if (paginaAtual > 1) {
    paginaAtual--;
    carregarDados();
  }
}

function proximaPagina() {
  if (paginaAtual < totalPaginas) {
    paginaAtual++;
    carregarDados();
  }
}

function mudarPageSize(novoTamanho) {
  itensPorPagina = parseInt(novoTamanho, 10);
  paginaAtual = 1;
  carregarDados();
}

function aplicarFiltros() {
  paginaAtual = 1;
  carregarDados();
}

function debounceBusca() {
  clearTimeout(timeoutBusca);
  const input = document.getElementById('filtroBusca');
  const btnClear = document.getElementById('btnClearSearch');
  if (btnClear) {
    if (input.value.trim().length > 0) {
      btnClear.classList.remove('hidden');
    } else {
      btnClear.classList.add('hidden');
    }
  }

  timeoutBusca = setTimeout(() => {
    paginaAtual = 1;
    carregarDados();
  }, 350);
}

function limparBuscaTexto() {
  const input = document.getElementById('filtroBusca');
  input.value = '';
  document.getElementById('btnClearSearch').classList.add('hidden');
  aplicarFiltros();
}

function limparTodosFiltros() {
  document.getElementById('filtroBusca').value = '';
  document.getElementById('filtroStatus').value = 'TODOS';
  document.getElementById('filtroEscolaridade').value = 'TODAS';
  document.getElementById('filtroDataInicio').value = '';
  document.getElementById('filtroDataFim').value = '';
  document.getElementById('btnClearSearch').classList.add('hidden');
  aplicarFiltros();
}

function filtrarPorStatusRapido(st) {
  document.getElementById('filtroStatus').value = st;
  aplicarFiltros();
}

function filtrarHojeRapido() {
  const hoje = new Date().toISOString().split('T')[0];
  document.getElementById('filtroDataInicio').value = hoje;
  document.getElementById('filtroDataFim').value = hoje;
  aplicarFiltros();
}

function filtrarDependentesRapido() {
  document.getElementById('filtroBusca').value = '';
  document.getElementById('filtroStatus').value = 'TODOS';
  aplicarFiltros();
}

/* ========================================================
   5. MODAL: FICHA COMPLETA & MODO DE EDIÇÃO
   ======================================================== */

async function abrirFichaDetalhada(id) {
  const modal = document.getElementById('modalDetalhes');
  const modalBody = document.getElementById('modalBodyContent');
  if (modal) modal.classList.remove('hidden');

  modoEdicaoAtivo = false;
  atualizarBotaoModoEdicao();

  if (modalBody) {
    modalBody.innerHTML = `
      <div style="text-align: center; padding: 3rem;">
        <div class="spinner-wheel" style="margin: 0 auto 1rem;"></div>
        <p>Carregando ficha cadastral...</p>
      </div>
    `;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/recadastramento/admin/detalhes/${id}`);
    if (!response.ok) throw new Error('Não foi possível carregar os detalhes do servidor.');

    const data = await response.json();
    if (!data.success) throw new Error(data.detail || 'Erro ao carregar dados.');

    servidorSelecionado = data.servidor;
    dependentesEmEdicao = JSON.parse(JSON.stringify(servidorSelecionado.dependentes || []));
    
    renderizarFichaVisualizacao(servidorSelecionado);

  } catch (err) {
    console.error('Erro modal:', err);
    if (modalBody) modalBody.innerHTML = `<div class="empty-state"><p class="text-danger">${err.message}</p></div>`;
  }
}

function alternarModoEdicao() {
  if (!servidorSelecionado) return;
  modoEdicaoAtivo = !modoEdicaoAtivo;
  atualizarBotaoModoEdicao();

  if (modoEdicaoAtivo) {
    dependentesEmEdicao = JSON.parse(JSON.stringify(servidorSelecionado.dependentes || []));
    renderizarFichaEdicao(servidorSelecionado);
  } else {
    renderizarFichaVisualizacao(servidorSelecionado);
  }
}

function atualizarBotaoModoEdicao() {
  const btn = document.getElementById('btnToggleModoEdicao');
  const btnText = document.getElementById('btnToggleEditText');
  if (!btn || !btnText) return;

  if (modoEdicaoAtivo) {
    btn.classList.add('modo-ativo');
    btn.innerHTML = `<i class="fa-solid fa-eye"></i> <span>Ver Modo Leitura</span>`;
  } else {
    btn.classList.remove('modo-ativo');
    btn.innerHTML = `<i class="fa-solid fa-pen-to-square"></i> <span>Editar Dados da Pessoa</span>`;
  }
}

/* 5.1 RENDERIZAÇÃO NO MODO LEITURA (VISUALIZAÇÃO) */
function renderizarFichaVisualizacao(s) {
  document.getElementById('modalNomeServidor').textContent = s.nome_completo || 'Ficha do Servidor';
  document.getElementById('modalProtocolo').textContent = s.protocolo || '-';
  document.getElementById('modalDataEnvio').textContent = s.data_envio_formatada || '-';

  // Dependentes Tabela
  let depHtml = '<p class="text-muted">Nenhum dependente cadastrado.</p>';
  if (s.dependentes && s.dependentes.length > 0) {
    depHtml = `
      <div class="table-responsive" style="margin-top: 0.5rem;">
        <table class="data-table" style="background: #FFFFFF;">
          <thead>
            <tr>
              <th>#</th>
              <th>Nome Completo</th>
              <th>Parentesco</th>
              <th>Data Nasc.</th>
              <th>CPF</th>
            </tr>
          </thead>
          <tbody>
    `;
    s.dependentes.forEach((d, idx) => {
      depHtml += `
        <tr>
          <td><strong>${idx + 1}</strong></td>
          <td><strong>${d.nome || '-'}</strong></td>
          <td><span class="status-pill status-em-analise">${d.parentesco || '-'}</span></td>
          <td>${formatarDataIso(d.data_nascimento)}</td>
          <td>${d.cpf || '-'}</td>
        </tr>
      `;
    });
    depHtml += `</tbody></table></div>`;
  }

  // Galeria de Documentos Anexados
  const docsList = [
    { title: 'Foto 3x4 (Rosto)', path: s.doc_foto3x4_path, icon: 'fa-camera' },
    { title: 'RG, CPF e/ou CNH', path: s.doc_identificacao_path, icon: 'fa-id-card' },
    { title: 'Comprovante Residência', path: s.doc_residencia_path, icon: 'fa-house' },
    { title: 'Título de Eleitor', path: s.doc_titulo_path, icon: 'fa-check-to-slot' },
    { title: 'Carteira de Trabalho (CTPS)', path: s.doc_ctps_path, icon: 'fa-address-book' },
    { title: 'Comprovante Escolaridade', path: s.doc_escolaridade_path, icon: 'fa-graduation-cap' }
  ];

  let docsCardsHtml = '';
  docsList.forEach(d => {
    if (d.path) {
      const fileUrl = `${API_BASE_URL}/${d.path}`;
      const fileName = obterNomeArquivo(d.path);
      docsCardsHtml += `
        <div class="modal-doc-card">
          <div class="doc-card-top">
            <i class="fa-solid ${d.icon} doc-card-icon"></i>
            <div class="doc-card-info">
              <span class="doc-card-title" title="${d.title}">${d.title}</span>
              <span class="doc-card-filename" title="${fileName}">${fileName}</span>
            </div>
          </div>
          <div class="doc-card-actions">
            <button type="button" class="btn-view-doc" onclick="abrirVisualizadorDoc('${d.path}', '${d.title}')">
              <i class="fa-regular fa-eye"></i> Visualizar
            </button>
            <a href="${fileUrl}" target="_blank" download class="btn-download-doc" title="Baixar arquivo (${fileName})">
              <i class="fa-solid fa-download"></i>
            </a>
          </div>
        </div>
      `;
    }
  });

  if (s.doc_dependentes_paths && s.doc_dependentes_paths.length > 0) {
    s.doc_dependentes_paths.forEach((path, idx) => {
      const fileUrl = `${API_BASE_URL}/${path}`;
      const fileName = obterNomeArquivo(path);
      docsCardsHtml += `
        <div class="modal-doc-card">
          <div class="doc-card-top">
            <i class="fa-solid fa-folder-open doc-card-icon" style="color:#0284C7;"></i>
            <div class="doc-card-info">
              <span class="doc-card-title" title="Doc. Dependente #${idx + 1}">Doc. Dependente #${idx + 1}</span>
              <span class="doc-card-filename" title="${fileName}">${fileName}</span>
            </div>
          </div>
          <div class="doc-card-actions">
            <button type="button" class="btn-view-doc" onclick="abrirVisualizadorDoc('${path}', 'Doc. Dependente #${idx + 1}')">
              <i class="fa-regular fa-eye"></i> Visualizar
            </button>
            <a href="${fileUrl}" target="_blank" download class="btn-download-doc" title="Baixar arquivo (${fileName})">
              <i class="fa-solid fa-download"></i>
            </a>
          </div>
        </div>
      `;
    });
  }

  const modalBody = document.getElementById('modalBodyContent');
  modalBody.innerHTML = `
    <div class="ficha-sections-grid">
      
      <!-- 💼 1. BLOCO DE DADOS FUNCIONAIS -->
      <div class="ficha-card-block ficha-card-rh-edit">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-briefcase" style="color:#2563EB;"></i> 1. Dados Funcionais & Lotação</h4>
          <span class="rh-badge-exclusive"><i class="fa-solid fa-lock-open"></i> Preenchimento do RH</span>
        </div>
        <div class="ficha-grid-fields">
          <div class="ficha-field-item"><span class="field-lbl">Matrícula</span><span class="field-val">${s.matricula || 'Pendente de Atribuição'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Cargo / Função</span><span class="field-val">${s.cargo || 'Não informado'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Setor / Lotação</span><span class="field-val">${s.setor || 'Não informado'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Tipo de Vínculo</span><span class="field-val">${s.vinculo || 'Não informado'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Data de Admissão</span><span class="field-val">${formatarDataIso(s.data_admissao)}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Status Cadastral</span><span class="field-val"><span class="status-pill ${obterClasseStatus(s.status)}">${s.status || 'ENVIADO'}</span></span></div>
          <div class="ficha-field-item col-span-full"><span class="field-lbl">Observações e Parecer do RH</span><span class="field-val">${s.observacoes || 'Nenhuma observação registrada.'}</span></div>
        </div>
      </div>

      <!-- 2. Dados Pessoais & Escolaridade -->
      <div class="ficha-card-block">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-user"></i> 2. Identificação & Dados Pessoais</h4>
          <button type="button" class="btn-toggle-edit" onclick="alternarModoEdicao()" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;">
            <i class="fa-solid fa-pen"></i> Editar
          </button>
        </div>
        <div class="ficha-grid-fields">
          <div class="ficha-field-item"><span class="field-lbl">Nome Completo</span><span class="field-val">${s.nome_completo || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">CPF</span><span class="field-val">${s.cpf || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">RG / Órgão Emissor</span><span class="field-val">${s.rg || '-'} (${s.rg_orgao || '-'}/${s.rg_uf || '-'})</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Data de Nascimento</span><span class="field-val">${formatarDataIso(s.data_nascimento)}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Sexo / Gênero</span><span class="field-val">${s.sexo || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Estado Civil</span><span class="field-val">${s.estado_civil || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Nome da Mãe</span><span class="field-val">${s.nome_mae || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Nome do Pai</span><span class="field-val">${s.nome_pai || 'Não informado'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Título de Eleitor</span><span class="field-val">${s.titulo_eleitor || '-'} (Zona: ${s.titulo_zona || '-'}, Seção: ${s.titulo_secao || '-'})</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Carteira de Trabalho (CTPS)</span><span class="field-val">${s.ctps_numero ? s.ctps_numero + ' / Série: ' + s.ctps_serie : 'Não informada'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Escolaridade</span><span class="field-val">${s.escolaridade || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Curso / Formação</span><span class="field-val">${s.curso_formacao || 'Não informado'}</span></div>
        </div>
      </div>

      <!-- 3. Endereço & Contato -->
      <div class="ficha-card-block">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-location-dot"></i> 3. Endereço Residencial e Contatos</h4>
        </div>
        <div class="ficha-grid-fields">
          <div class="ficha-field-item"><span class="field-lbl">Logradouro / Número</span><span class="field-val">${s.logradouro || '-'}, Nº ${s.numero || 'S/N'} ${s.complemento ? '(' + s.complemento + ')' : ''}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Bairro</span><span class="field-val">${s.bairro || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">Cidade / UF</span><span class="field-val">${s.cidade || '-'}/${s.uf || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">CEP</span><span class="field-val">${s.cep || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">WhatsApp / Celular</span><span class="field-val"><a href="https://wa.me/55${(s.whatsapp||'').replace(/\D/g,'')}" target="_blank" class="contact-whatsapp"><i class="fa-brands fa-whatsapp"></i> ${s.whatsapp || '-'}</a></span></div>
          <div class="ficha-field-item"><span class="field-lbl">E-mail Pessoal</span><span class="field-val">${s.email_pessoal || '-'}</span></div>
          <div class="ficha-field-item"><span class="field-lbl">E-mail Institucional</span><span class="field-val">${s.email_institucional || 'Não possui'}</span></div>
        </div>
      </div>

      <!-- 4. Dependentes -->
      <div class="ficha-card-block">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-people-roof"></i> 4. Dependentes Cadastrados</h4>
        </div>
        ${depHtml}
      </div>

      <!-- 5. Documentação Anexada -->
      <div class="ficha-card-block">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-paperclip"></i> 5. Documentos Anexados (Checklist Oficial GERH)</h4>
        </div>
        <div class="modal-docs-grid">
          ${docsCardsHtml || '<p class="text-muted">Nenhum arquivo anexado.</p>'}
        </div>
      </div>

    </div>
  `;
}

/* 5.2 RENDERIZAÇÃO NO MODO EDIÇÃO TOTAL */
function renderizarFichaEdicao(s) {
  const modalBody = document.getElementById('modalBodyContent');

  let dependentesEditRows = '';
  dependentesEmEdicao.forEach((d, idx) => {
    dependentesEditRows += `
      <div class="dep-edit-row" id="depRow_${idx}">
        <input type="text" class="edit-input" placeholder="Nome Completo do Dependente" value="${d.nome || ''}" onchange="atualizarCampoDep(${idx}, 'nome', this.value)">
        <select class="edit-select" onchange="atualizarCampoDep(${idx}, 'parentesco', this.value)">
          <option value="Filho(a)" ${d.parentesco === 'Filho(a)' ? 'selected' : ''}>Filho(a)</option>
          <option value="Cônjuge / Companheiro(a)" ${d.parentesco === 'Cônjuge / Companheiro(a)' ? 'selected' : ''}>Cônjuge</option>
          <option value="Pai / Mãe" ${d.parentesco === 'Pai / Mãe' ? 'selected' : ''}>Pai / Mãe</option>
          <option value="Enteado(a)" ${d.parentesco === 'Enteado(a)' ? 'selected' : ''}>Enteado(a)</option>
          <option value="Menor sob Guarda / Tutela" ${d.parentesco === 'Menor sob Guarda / Tutela' ? 'selected' : ''}>Menor sob Guarda</option>
          <option value="Outro" ${d.parentesco === 'Outro' ? 'selected' : ''}>Outro</option>
        </select>
        <input type="date" class="edit-input" value="${d.data_nascimento || ''}" onchange="atualizarCampoDep(${idx}, 'data_nascimento', this.value)">
        <input type="text" class="edit-input" placeholder="CPF do Dependente" value="${d.cpf || ''}" onchange="atualizarCampoDep(${idx}, 'cpf', this.value)">
        <button type="button" class="btn-del-dep" onclick="removerDependenteEdicao(${idx})" title="Remover este dependente">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      </div>
    `;
  });

  modalBody.innerHTML = `
    <form id="formEdicaoCompleta" onsubmit="salvarEdicaoCompleta(event)" class="ficha-sections-grid">
      
      <!-- BARRA DE AÇÃO FIXA DE SALVAMENTO -->
      <div class="edit-actions-bar">
        <div class="edit-actions-info">
          <i class="fa-solid fa-pen-nib fa-lg text-blue"></i>
          <span>Modo de Edição Cadastral Ativo — Altere os dados necessários e clique em Salvar</span>
        </div>
        <div class="edit-actions-buttons">
          <button type="button" class="btn-cancel-edit" onclick="alternarModoEdicao()">Cancelar</button>
          <button type="submit" class="btn-save-full-edit" id="btnSalvarEdicaoGeral">
            <i class="fa-solid fa-floppy-disk"></i> Salvar Todas as Alterações
          </button>
        </div>
      </div>

      <!-- 1. DADOS FUNCIONAIS DO RH -->
      <div class="ficha-card-block ficha-card-rh-edit">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-briefcase" style="color:#2563EB;"></i> 1. Dados Funcionais & Lotação (GERH)</h4>
          <span class="rh-badge-exclusive"><i class="fa-solid fa-lock-open"></i> Controle RH</span>
        </div>
        <div class="edit-form-grid">
          <div class="edit-input-group">
            <label class="edit-lbl">Matrícula</label>
            <input type="text" id="edit_matricula" class="edit-input" value="${s.matricula || ''}" placeholder="Ex: 12345-6">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Cargo / Função Nomeada</label>
            <input type="text" id="edit_cargo" class="edit-input" value="${s.cargo || ''}" placeholder="Cargo do servidor">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Setor / Lotação</label>
            <select id="edit_setor" class="edit-select">
              <option value="">Selecione o setor...</option>
              <optgroup label="Diretorias">
                <option value="Diretoria Presidente (DIRPRES)" ${s.setor === 'Diretoria Presidente (DIRPRES)' ? 'selected' : ''}>Diretoria Presidente (DIRPRES)</option>
                <option value="Diretoria Técnica (DIRTEC)" ${s.setor === 'Diretoria Técnica (DIRTEC)' ? 'selected' : ''}>Diretoria Técnica (DIRTEC)</option>
                <option value="Diretoria Administrativa e Financeira (DIRAF)" ${s.setor === 'Diretoria Administrativa e Financeira (DIRAF)' ? 'selected' : ''}>Diretoria Administrativa e Financeira (DIRAF)</option>
              </optgroup>
              <optgroup label="Laboratórios e Ensaios">
                <option value="Química de Água" ${s.setor === 'Química de Água' ? 'selected' : ''}>Laboratório de Química de Água</option>
                <option value="Inorgânica" ${s.setor === 'Inorgânica' ? 'selected' : ''}>Laboratório de Química Inorgânica</option>
                <option value="Microbiologia" ${s.setor === 'Microbiologia' ? 'selected' : ''}>Laboratório de Microbiologia</option>
                <option value="Solos" ${s.setor === 'Solos' ? 'selected' : ''}>Laboratório de Análise de Solos</option>
                <option value="Alimentos" ${s.setor === 'Alimentos' ? 'selected' : ''}>Laboratório de Alimentos</option>
              </optgroup>
              <optgroup label="Metrologia Legal e Qualidade">
                <option value="Gerência de Metrologia Legal (GERMET)" ${s.setor === 'Gerência de Metrologia Legal (GERMET)' ? 'selected' : ''}>Gerência de Metrologia Legal (GERMET)</option>
                <option value="Fiscalização Metrológica" ${s.setor === 'Fiscalização Metrológica' ? 'selected' : ''}>Fiscalização Metrológica</option>
                <option value="Controle de Qualidade" ${s.setor === 'Controle de Qualidade' ? 'selected' : ''}>Controle de Qualidade</option>
              </optgroup>
              <optgroup label="Setores Administrativos e Apoio">
                <option value="Recursos Humanos (GERH)" ${s.setor === 'Recursos Humanos (GERH)' ? 'selected' : ''}>Recursos Humanos (GERH)</option>
                <option value="Informática e Tecnologia (GEINFORM)" ${s.setor === 'Informática e Tecnologia (GEINFORM)' ? 'selected' : ''}>Informática e Tecnologia (GEINFORM)</option>
                <option value="Compras e Licitações (GECOMP)" ${s.setor === 'Compras e Licitações (GECOMP)' ? 'selected' : ''}>Compras e Licitações (GECOMP)</option>
                <option value="Contabilidade e Finanças (GECONF)" ${s.setor === 'Contabilidade e Finanças (GECONF)' ? 'selected' : ''}>Contabilidade e Finanças (GECONF)</option>
                <option value="Assessoria Jurídica (ASJUR)" ${s.setor === 'Assessoria Jurídica (ASJUR)' ? 'selected' : ''}>Assessoria Jurídica (ASJUR)</option>
                <option value="Comunicação Social (ASCOM)" ${s.setor === 'Comunicação Social (ASCOM)' ? 'selected' : ''}>Comunicação Social (ASCOM)</option>
                <option value="Protocolo e Arquivo Geral" ${s.setor === 'Protocolo e Arquivo Geral' ? 'selected' : ''}>Protocolo e Arquivo Geral</option>
              </optgroup>
              <option value="Outro Setor" ${s.setor === 'Outro Setor' ? 'selected' : ''}>Outro Setor</option>
            </select>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Tipo de Vínculo</label>
            <select id="edit_vinculo" class="edit-select">
              <option value="">Selecione o vínculo...</option>
              <option value="Cargo em Comissão (Comissionado)" ${s.vinculo === 'Cargo em Comissão (Comissionado)' ? 'selected' : ''}>Cargo em Comissão (Comissionado)</option>
              <option value="Efetivo / Estatutário" ${s.vinculo === 'Efetivo / Estatutário' ? 'selected' : ''}>Efetivo / Estatutário</option>
              <option value="Emprego Público" ${s.vinculo === 'Emprego Público' ? 'selected' : ''}>Emprego Público</option>
              <option value="Contrato Temporário (PSS)" ${s.vinculo === 'Contrato Temporário (PSS)' ? 'selected' : ''}>Contrato Temporário (PSS)</option>
              <option value="Estagiário(a)" ${s.vinculo === 'Estagiário(a)' ? 'selected' : ''}>Estagiário(a)</option>
              <option value="Terceirizado(a)" ${s.vinculo === 'Terceirizado(a)' ? 'selected' : ''}>Terceirizado(a)</option>
              <option value="Cedido de Outro Órgão" ${s.vinculo === 'Cedido de Outro Órgão' ? 'selected' : ''}>Cedido de Outro Órgão</option>
              <option value="Bolsista / Pesquisador" ${s.vinculo === 'Bolsista / Pesquisador' ? 'selected' : ''}>Bolsista / Pesquisador</option>
            </select>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Data de Admissão</label>
            <input type="date" id="edit_data_admissao" class="edit-input" value="${s.data_admissao || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Status</label>
            <select id="edit_status" class="edit-select">
              <option value="ENVIADO" ${s.status === 'ENVIADO' ? 'selected' : ''}>ENVIADO (Aguardando)</option>
              <option value="EM ANÁLISE" ${s.status === 'EM ANÁLISE' ? 'selected' : ''}>EM ANÁLISE</option>
              <option value="APROVADO" ${s.status === 'APROVADO' ? 'selected' : ''}>APROVADO / HOMOLOGADO</option>
              <option value="PENDENTE" ${s.status === 'PENDENTE' ? 'selected' : ''}>PENDENTE / INCOMPLETO</option>
            </select>
          </div>
          <div class="edit-input-group col-span-full">
            <label class="edit-lbl">Observações e Parecer do RH</label>
            <textarea id="edit_observacoes" class="edit-textarea" rows="2" placeholder="Observações internas...">${s.observacoes || ''}</textarea>
          </div>
        </div>
      </div>

      <!-- 2. IDENTIFICAÇÃO & DADOS PESSOAIS -->
      <div class="ficha-card-block">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-user"></i> 2. Identificação & Dados Pessoais</h4>
        </div>
        <div class="edit-form-grid">
          <div class="edit-input-group col-span-2">
            <label class="edit-lbl">Nome Completo *</label>
            <input type="text" id="edit_nome_completo" class="edit-input" value="${s.nome_completo || ''}" required>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">CPF *</label>
            <input type="text" id="edit_cpf" class="edit-input" value="${s.cpf || ''}" required>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">RG</label>
            <input type="text" id="edit_rg" class="edit-input" value="${s.rg || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Órgão Emissor / UF</label>
            <div style="display:flex; gap:0.4rem;">
              <input type="text" id="edit_rg_orgao" class="edit-input" style="flex:2;" placeholder="SSP" value="${s.rg_orgao || ''}">
              <input type="text" id="edit_rg_uf" class="edit-input" style="flex:1;" placeholder="SE" value="${s.rg_uf || ''}">
            </div>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Data de Nascimento</label>
            <input type="date" id="edit_data_nascimento" class="edit-input" value="${s.data_nascimento || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Sexo / Gênero</label>
            <select id="edit_sexo" class="edit-select">
              <option value="Masculino" ${s.sexo === 'Masculino' ? 'selected' : ''}>Masculino</option>
              <option value="Feminino" ${s.sexo === 'Feminino' ? 'selected' : ''}>Feminino</option>
              <option value="Outro" ${s.sexo === 'Outro' ? 'selected' : ''}>Outro</option>
            </select>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Estado Civil</label>
            <select id="edit_estado_civil" class="edit-select">
              <option value="Solteiro(a)" ${s.estado_civil === 'Solteiro(a)' ? 'selected' : ''}>Solteiro(a)</option>
              <option value="Casado(a)" ${s.estado_civil === 'Casado(a)' ? 'selected' : ''}>Casado(a)</option>
              <option value="União Estável" ${s.estado_civil === 'União Estável' ? 'selected' : ''}>União Estável</option>
              <option value="Divorciado(a)" ${s.estado_civil === 'Divorciado(a)' ? 'selected' : ''}>Divorciado(a)</option>
              <option value="Viúvo(a)" ${s.estado_civil === 'Viúvo(a)' ? 'selected' : ''}>Viúvo(a)</option>
            </select>
          </div>
          <div class="edit-input-group col-span-2">
            <label class="edit-lbl">Nome da Mãe</label>
            <input type="text" id="edit_nome_mae" class="edit-input" value="${s.nome_mae || ''}">
          </div>
          <div class="edit-input-group col-span-2">
            <label class="edit-lbl">Nome do Pai</label>
            <input type="text" id="edit_nome_pai" class="edit-input" value="${s.nome_pai || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Título de Eleitor</label>
            <input type="text" id="edit_titulo_eleitor" class="edit-input" value="${s.titulo_eleitor || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Zona / Seção Eleitoral</label>
            <div style="display:flex; gap:0.4rem;">
              <input type="text" id="edit_titulo_zona" class="edit-input" placeholder="Zona" value="${s.titulo_zona || ''}">
              <input type="text" id="edit_titulo_secao" class="edit-input" placeholder="Seção" value="${s.titulo_secao || ''}">
            </div>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">CTPS Número / Série</label>
            <div style="display:flex; gap:0.4rem;">
              <input type="text" id="edit_ctps_numero" class="edit-input" placeholder="Número" value="${s.ctps_numero || ''}">
              <input type="text" id="edit_ctps_serie" class="edit-input" placeholder="Série" value="${s.ctps_serie || ''}">
            </div>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Escolaridade</label>
            <select id="edit_escolaridade" class="edit-select">
              <option value="Superior Completo" ${s.escolaridade === 'Superior Completo' ? 'selected' : ''}>Superior Completo</option>
              <option value="Pós-Graduação / Especialização" ${s.escolaridade === 'Pós-Graduação / Especialização' ? 'selected' : ''}>Pós-Graduação / Especialização</option>
              <option value="Mestrado" ${s.escolaridade === 'Mestrado' ? 'selected' : ''}>Mestrado</option>
              <option value="Doutorado" ${s.escolaridade === 'Doutorado' ? 'selected' : ''}>Doutorado</option>
              <option value="Superior Incompleto (Graduando)" ${s.escolaridade === 'Superior Incompleto (Graduando)' ? 'selected' : ''}>Superior Incompleto</option>
              <option value="Ensino Técnico" ${s.escolaridade === 'Ensino Técnico' ? 'selected' : ''}>Ensino Técnico</option>
              <option value="Ensino Médio Completo" ${s.escolaridade === 'Ensino Médio Completo' ? 'selected' : ''}>Ensino Médio Completo</option>
              <option value="Ensino Fundamental Completo" ${s.escolaridade === 'Ensino Fundamental Completo' ? 'selected' : ''}>Ensino Fundamental Completo</option>
            </select>
          </div>
          <div class="edit-input-group col-span-2">
            <label class="edit-lbl">Curso / Formação</label>
            <input type="text" id="edit_curso_formacao" class="edit-input" value="${s.curso_formacao || ''}">
          </div>
        </div>
      </div>

      <!-- 3. ENDEREÇO & CONTATOS -->
      <div class="ficha-card-block">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-location-dot"></i> 3. Endereço Residencial e Contatos</h4>
        </div>
        <div class="edit-form-grid">
          <div class="edit-input-group">
            <label class="edit-lbl">CEP</label>
            <input type="text" id="edit_cep" class="edit-input" value="${s.cep || ''}">
          </div>
          <div class="edit-input-group col-span-2">
            <label class="edit-lbl">Logradouro (Rua / Av.)</label>
            <input type="text" id="edit_logradouro" class="edit-input" value="${s.logradouro || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Número</label>
            <input type="text" id="edit_numero" class="edit-input" value="${s.numero || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Complemento</label>
            <input type="text" id="edit_complemento" class="edit-input" value="${s.complemento || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Bairro</label>
            <input type="text" id="edit_bairro" class="edit-input" value="${s.bairro || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">Cidade</label>
            <input type="text" id="edit_cidade" class="edit-input" value="${s.cidade || ''}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">UF</label>
            <input type="text" id="edit_uf" class="edit-input" value="${s.uf || 'SE'}">
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">WhatsApp / Celular *</label>
            <input type="text" id="edit_whatsapp" class="edit-input" value="${s.whatsapp || ''}" required>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">E-mail Pessoal *</label>
            <input type="email" id="edit_email_pessoal" class="edit-input" value="${s.email_pessoal || ''}" required>
          </div>
          <div class="edit-input-group">
            <label class="edit-lbl">E-mail Institucional</label>
            <input type="email" id="edit_email_institucional" class="edit-input" value="${s.email_institucional || ''}">
          </div>
        </div>
      </div>

      <!-- 4. DEPENDENTES EM EDIÇÃO -->
      <div class="ficha-card-block">
        <div class="ficha-card-header">
          <h4><i class="fa-solid fa-people-roof"></i> 4. Dependentes</h4>
        </div>
        <div id="containerDependentesEdicao">
          ${dependentesEditRows || '<p class="text-muted" id="msgSemDepEdit">Nenhum dependente adicionado.</p>'}
        </div>
        <button type="button" class="btn-add-dep-edit" onclick="adicionarDependenteEdicao()">
          <i class="fa-solid fa-plus"></i> Adicionar Dependente
        </button>
      </div>

    </form>
  `;
}

function atualizarCampoDep(idx, campo, valor) {
  if (dependentesEmEdicao[idx]) {
    dependentesEmEdicao[idx][campo] = valor;
  }
}

function adicionarDependenteEdicao() {
  dependentesEmEdicao.push({
    id: Date.now(),
    nome: '',
    parentesco: 'Filho(a)',
    data_nascimento: '',
    cpf: ''
  });
  renderizarFichaEdicao(servidorSelecionado);
}

function removerDependenteEdicao(idx) {
  dependentesEmEdicao.splice(idx, 1);
  renderizarFichaEdicao(servidorSelecionado);
}

/* 5.3 SALVAMENTO DA EDIÇÃO COMPLETA */
async function salvarEdicaoCompleta(e) {
  if (e) e.preventDefault();
  if (!servidorSelecionado) return;

  const btnSalvar = document.getElementById('btnSalvarEdicaoGeral');
  if (btnSalvar) {
    btnSalvar.disabled = true;
    btnSalvar.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Salvando dados...`;
  }

  const payload = {
    nome_completo: document.getElementById('edit_nome_completo').value.trim(),
    cpf: document.getElementById('edit_cpf').value.trim(),
    rg: document.getElementById('edit_rg').value.trim(),
    rg_orgao: document.getElementById('edit_rg_orgao').value.trim(),
    rg_uf: document.getElementById('edit_rg_uf').value.trim(),
    data_nascimento: document.getElementById('edit_data_nascimento').value,
    sexo: document.getElementById('edit_sexo').value,
    estado_civil: document.getElementById('edit_estado_civil').value,
    nome_mae: document.getElementById('edit_nome_mae').value.trim(),
    nome_pai: document.getElementById('edit_nome_pai').value.trim(),
    titulo_eleitor: document.getElementById('edit_titulo_eleitor').value.trim(),
    titulo_zona: document.getElementById('edit_titulo_zona').value.trim(),
    titulo_secao: document.getElementById('edit_titulo_secao').value.trim(),
    ctps_numero: document.getElementById('edit_ctps_numero').value.trim(),
    ctps_serie: document.getElementById('edit_ctps_serie').value.trim(),
    escolaridade: document.getElementById('edit_escolaridade').value,
    curso_formacao: document.getElementById('edit_curso_formacao').value.trim(),
    cep: document.getElementById('edit_cep').value.trim(),
    logradouro: document.getElementById('edit_logradouro').value.trim(),
    numero: document.getElementById('edit_numero').value.trim(),
    complemento: document.getElementById('edit_complemento').value.trim(),
    bairro: document.getElementById('edit_bairro').value.trim(),
    cidade: document.getElementById('edit_cidade').value.trim(),
    uf: document.getElementById('edit_uf').value.trim(),
    whatsapp: document.getElementById('edit_whatsapp').value.trim(),
    email_pessoal: document.getElementById('edit_email_pessoal').value.trim(),
    email_institucional: document.getElementById('edit_email_institucional').value.trim(),
    possui_dependentes: dependentesEmEdicao.length > 0,
    dependentes_json: JSON.stringify(dependentesEmEdicao),
    matricula: document.getElementById('edit_matricula').value.trim(),
    cargo: document.getElementById('edit_cargo').value.trim(),
    setor: document.getElementById('edit_setor').value,
    vinculo: document.getElementById('edit_vinculo').value,
    data_admissao: document.getElementById('edit_data_admissao').value,
    status: document.getElementById('edit_status').value,
    observacoes: document.getElementById('edit_observacoes').value.trim()
  };

  try {
    const response = await fetch(`${API_BASE_URL}/api/recadastramento/admin/${servidorSelecionado.id}/editar-completo`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) throw new Error('Falha ao atualizar dados do servidor.');

    const data = await response.json();
    if (data.success) {
      showToast('Ficha do servidor atualizada com sucesso pelo RH!', 'success');
      
      servidorSelecionado = data.servidor;
      modoEdicaoAtivo = false;
      atualizarBotaoModoEdicao();
      renderizarFichaVisualizacao(servidorSelecionado);
      carregarDados();
    }
  } catch (err) {
    console.error('Erro ao salvar edição:', err);
    showToast(`Erro ao salvar: ${err.message}`, 'error');
  } finally {
    if (btnSalvar) {
      btnSalvar.disabled = false;
      btnSalvar.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Salvar Todas as Alterações`;
    }
  }
}

function fecharModalDetalhes() {
  const modal = document.getElementById('modalDetalhes');
  if (modal) modal.classList.add('hidden');
}

/* ========================================================
   6. EXCLUSÃO COM MODAL ELEGANTE
   ======================================================== */

function solicitarExclusao(id, protocolo, nome) {
  abrirModalConfirmacao({
    titulo: 'Excluir Recadastramento?',
    mensagem: `Você está prestes a remover o cadastro de <strong>${nome}</strong> do sistema.`,
    detalhe: `Protocolo: ${protocolo} • Esta ação é permanente e irreversível.`,
    tipo: 'danger',
    icone: 'fa-regular fa-trash-can',
    textoBotao: 'Sim, Excluir Registro',
    classeBotao: 'btn-danger',
    onConfirmar: async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/recadastramento/admin/${id}`, {
          method: 'DELETE'
        });

        if (!response.ok) throw new Error('Não foi possível excluir o registro.');

        const data = await response.json();
        if (data.success) {
          showToast(data.mensagem || 'Registro excluído com sucesso!', 'success');
          carregarDados();
        }
      } catch (err) {
        console.error('Erro ao excluir:', err);
        showToast(`Erro ao excluir: ${err.message}`, 'error');
      }
    }
  });
}

/* ========================================================
   7. MODAL DE CONFIRMAÇÃO GENÉRICO ELEGANTE
   ======================================================== */

function abrirModalConfirmacao(config) {
  const modal = document.getElementById('modalConfirmacao');
  const iconBox = document.getElementById('confirmIconBox');
  const icon = document.getElementById('confirmIcon');
  const title = document.getElementById('confirmTitle');
  const desc = document.getElementById('confirmDesc');
  const detail = document.getElementById('confirmDetail');
  const btnProceed = document.getElementById('btnConfirmProceed');
  const btnProceedText = document.getElementById('btnConfirmProceedText');

  if (!modal) return;

  // Configura ícone e cor
  const tipo = config.tipo || 'danger';
  if (iconBox) iconBox.className = `confirm-icon-box ${tipo}`;
  if (icon) icon.className = config.icone || 'fa-solid fa-triangle-exclamation';

  if (title) title.textContent = config.titulo || 'Confirmar Ação';
  if (desc) desc.innerHTML = config.mensagem || 'Tem certeza que deseja prosseguir?';

  if (detail) {
    if (config.detalhe) {
      detail.innerHTML = config.detalhe;
      detail.classList.remove('hidden');
    } else {
      detail.classList.add('hidden');
    }
  }

  if (btnProceed) {
    btnProceed.className = `btn-confirm-action ${config.classeBotao || 'btn-danger'}`;
  }
  if (btnProceedText) {
    btnProceedText.textContent = config.textoBotao || 'Confirmar';
  }

  callbackConfirmacaoPendente = config.onConfirmar || null;

  modal.classList.remove('hidden');
}

function fecharModalConfirmacao(executar = false) {
  const modal = document.getElementById('modalConfirmacao');
  if (modal) modal.classList.add('hidden');
  if (!executar) {
    callbackConfirmacaoPendente = null;
  }
}

async function executarConfirmacaoCallback() {
  const fn = callbackConfirmacaoPendente;
  fecharModalConfirmacao(true);
  if (typeof fn === 'function') {
    await fn();
  }
  callbackConfirmacaoPendente = null;
}

/* ========================================================
   8. VISUALIZADOR DE DOCUMENTOS (LIGHTBOX MODAL)
   ======================================================== */

function abrirVisualizadorDoc(path, titulo) {
  const modal = document.getElementById('modalDocViewer');
  const container = document.getElementById('docViewerContainer');
  const titleEl = document.getElementById('docViewerTitle');
  const downloadBtn = document.getElementById('docViewerDownloadBtn');

  const fileUrl = `${API_BASE_URL}/${path}`;

  if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-paperclip"></i> ${titulo}`;
  if (downloadBtn) downloadBtn.href = fileUrl;

  const isPdf = path.toLowerCase().endsWith('.pdf');

  if (container) {
    if (isPdf) {
      container.innerHTML = `<iframe src="${fileUrl}" title="${titulo}"></iframe>`;
    } else {
      container.innerHTML = `<img src="${fileUrl}" alt="${titulo}">`;
    }
  }

  if (modal) modal.classList.remove('hidden');
}

function fecharModalDoc() {
  const modal = document.getElementById('modalDocViewer');
  const container = document.getElementById('docViewerContainer');
  if (modal) modal.classList.add('hidden');
  if (container) container.innerHTML = '';
}

/* ========================================================
   9. EXPORTAR EXCEL (CSV) E IMPRESSÃO
   ======================================================== */

function exportarExcel() {
  const busca = document.getElementById('filtroBusca').value.trim();
  const status = document.getElementById('filtroStatus').value;
  const escolaridade = document.getElementById('filtroEscolaridade').value;

  const params = new URLSearchParams();
  if (busca) params.append('busca', busca);
  if (status && status !== 'TODOS') params.append('status', status);
  if (escolaridade && escolaridade !== 'TODAS') params.append('escolaridade', escolaridade);

  const url = `${API_BASE_URL}/api/recadastramento/admin/exportar-csv?${params.toString()}`;
  window.open(url, '_blank');
  showToast('Iniciando download da planilha Excel...', 'info');
}

function imprimirFichaServidor() {
  window.print();
}

/* ========================================================
   10. UTILITÁRIOS E TOASTS
   ======================================================== */

function formatarDataIso(dataIso) {
  if (!dataIso) return '-';
  const p = dataIso.split('-');
  if (p.length === 3) return `${p[2]}/${p[1]}/${p[0]}`;
  return dataIso;
}

function obterNomeArquivo(path) {
  if (!path) return '';
  const p = path.split('/');
  return p[p.length - 1];
}

function showToast(msg, tipo = 'info') {
  const c = document.getElementById('adminToastContainer');
  if (!c) return;

  const toast = document.createElement('div');
  toast.className = `toast ${tipo}`;
  
  let icone = '<i class="fa-solid fa-circle-info"></i>';
  if (tipo === 'success') icone = '<i class="fa-solid fa-circle-check text-green"></i>';
  if (tipo === 'error') icone = '<i class="fa-solid fa-circle-exclamation" style="color:var(--danger)"></i>';

  toast.innerHTML = `${icone} <span>${msg}</span>`;
  c.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
