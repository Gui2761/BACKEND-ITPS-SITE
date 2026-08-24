/**
 * ========================================================
 * SCRIPT - RECADASTRAMENTO & CONTRATAÇÃO ITPS (GERH)
 * ========================================================
 */

// Estado Global do Wizard
let etapaAtual = 1;
const totalEtapas = 5;
let listaDependentes = [];
let arquivosSelecionados = {
  doc_foto3x4: null,
  doc_identificacao: null,
  doc_titulo: null,
  doc_residencia: null,
  doc_ctps: null,
  doc_escolaridade: null,
  doc_dependentes: []
};

// URL base do Backend FastAPI (Detecta automaticamente se está via túnel Cloudflare ou Intranet/Localhost)
const API_BASE_URL = (window.location.hostname.includes('trycloudflare.com') || window.location.port === '8000')
  ? window.location.origin
  : `${window.location.protocol}//${window.location.hostname}:8000`;

document.addEventListener('DOMContentLoaded', () => {
  inicializarMascaras();
  configurarEventos();
  configurarDropzones();
  configurarDependentes();
  atualizarUIEtapa();
});

/* ========================================================
   1. NAVEGAÇÃO ENTRE ETAPAS (WIZARD)
   ======================================================== */

function atualizarUIEtapa() {
  verificarExibicaoUploadDependentes();

  for (let i = 1; i <= totalEtapas; i++) {
    const el = document.getElementById(`stepContent${i}`);
    if (el) {
      if (i === etapaAtual) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    }
  }

  const stepItems = document.querySelectorAll('.step-item');
  stepItems.forEach((item, idx) => {
    const stepNum = idx + 1;
    item.classList.remove('active', 'completed');
    if (stepNum === etapaAtual) {
      item.classList.add('active');
    } else if (stepNum < etapaAtual) {
      item.classList.add('completed');
    }
  });

  const progressPercent = ((etapaAtual - 1) / (totalEtapas - 1)) * 100;
  const progressBar = document.getElementById('stepperProgressBar');
  if (progressBar) {
    let styleTag = document.getElementById('stepperDynamicStyle');
    if (!styleTag) {
      styleTag = document.createElement('style');
      styleTag.id = 'stepperDynamicStyle';
      document.head.appendChild(styleTag);
    }
    styleTag.innerHTML = `.stepper-progress-bar::after { width: ${progressPercent}% !important; }`;
  }

  const btnVoltar = document.getElementById('btnVoltar');
  const btnAvancar = document.getElementById('btnAvancar');
  const btnEnviar = document.getElementById('btnEnviar');
  const stepIndicatorText = document.getElementById('stepIndicatorText');

  if (stepIndicatorText) {
    stepIndicatorText.textContent = `Passo ${etapaAtual} de ${totalEtapas}`;
  }

  if (etapaAtual === 1) {
    btnVoltar.style.visibility = 'hidden';
  } else {
    btnVoltar.style.visibility = 'visible';
  }

  if (etapaAtual === totalEtapas) {
    btnAvancar.classList.add('hidden');
    btnEnviar.classList.remove('hidden');
    gerarResumoRevisao();
  } else {
    btnAvancar.classList.remove('hidden');
    btnEnviar.classList.add('hidden');
  }

  window.scrollTo({ top: 120, behavior: 'smooth' });
}

function proximaEtapa() {
  try {
    if (validarEtapa(etapaAtual)) {
      if (etapaAtual < totalEtapas) {
        etapaAtual++;
        atualizarUIEtapa();
      }
    }
  } catch (err) {
    console.error('Erro ao avançar etapa:', err);
    showToast('Erro ao avançar: ' + err.message, 'error');
  }
}

function etapaAnterior() {
  if (etapaAtual > 1) {
    etapaAtual--;
    atualizarUIEtapa();
  }
}

function irParaEtapa(num) {
  if (num >= 1 && num <= totalEtapas) {
    if (num > etapaAtual && !validarEtapa(etapaAtual)) {
      return;
    }
    etapaAtual = num;
    atualizarUIEtapa();
  }
}

/* ========================================================
   2. VALIDAÇÕES POR ETAPA
   ======================================================== */

function validarEtapa(etapa) {
  limparErrosVisuais();
  let valido = true;

  if (etapa === 1) {
    // Dados Pessoais & Escolaridade
    const nome = document.getElementById('nome_completo');
    const cpf = document.getElementById('cpf');
    const dataNasc = document.getElementById('data_nascimento');
    const rg = document.getElementById('rg');
    const rgOrgao = document.getElementById('rg_orgao');
    const sexo = document.getElementById('sexo');
    const estadoCivil = document.getElementById('estado_civil');
    const nomeMae = document.getElementById('nome_mae');
    const tituloEleitor = document.getElementById('titulo_eleitor');
    const escolaridade = document.getElementById('escolaridade');

    if (!nome || !nome.value.trim() || nome.value.trim().split(' ').length < 2) {
      if (nome) marcarInvalido(nome, 'Informe seu nome completo (nome e sobrenome).');
      valido = false;
    }

    if (!cpf || !validarCPF(cpf.value)) {
      if (cpf) marcarInvalido(cpf, 'Informe um CPF válido com 11 dígitos.');
      valido = false;
    }

    if (!dataNasc || !dataNasc.value) {
      if (dataNasc) marcarInvalido(dataNasc, 'Informe sua data de nascimento.');
      valido = false;
    }

    if (!rg || !rg.value.trim()) {
      if (rg) marcarInvalido(rg, 'Informe o número do seu RG.');
      valido = false;
    }

    if (!rgOrgao || !rgOrgao.value.trim()) {
      if (rgOrgao) marcarInvalido(rgOrgao, 'Informe o órgão emissor.');
      valido = false;
    }

    if (!sexo || !sexo.value) {
      if (sexo) marcarInvalido(sexo, 'Selecione o sexo/gênero.');
      valido = false;
    }

    if (!estadoCivil || !estadoCivil.value) {
      if (estadoCivil) marcarInvalido(estadoCivil, 'Selecione o estado civil.');
      valido = false;
    }

    if (!nomeMae || !nomeMae.value.trim()) {
      if (nomeMae) marcarInvalido(nomeMae, 'Informe o nome da mãe.');
      valido = false;
    }

    if (!tituloEleitor || !tituloEleitor.value.trim()) {
      if (tituloEleitor) marcarInvalido(tituloEleitor, 'Informe o número do Título de Eleitor.');
      valido = false;
    }

    if (!escolaridade || !escolaridade.value) {
      if (escolaridade) marcarInvalido(escolaridade, 'Selecione o grau de escolaridade.');
      valido = false;
    }
  } 
  else if (etapa === 2) {
    // Endereço e Contato
    const cep = document.getElementById('cep');
    const logradouro = document.getElementById('logradouro');
    const numero = document.getElementById('numero');
    const bairro = document.getElementById('bairro');
    const cidade = document.getElementById('cidade');
    const uf = document.getElementById('uf');
    const whatsapp = document.getElementById('whatsapp');
    const email = document.getElementById('email_pessoal');

    const cepLimpo = cep ? cep.value.replace(/\D/g, '') : '';
    if (cepLimpo.length !== 8) {
      if (cep) marcarInvalido(cep, 'Informe um CEP válido com 8 dígitos.');
      valido = false;
    }

    if (!logradouro || !logradouro.value.trim()) {
      if (logradouro) marcarInvalido(logradouro, 'Informe a rua/logradouro.');
      valido = false;
    }

    if (!numero || !numero.value.trim()) {
      if (numero) marcarInvalido(numero, 'Informe o número da residência ou S/N.');
      valido = false;
    }

    if (!bairro || !bairro.value.trim()) {
      if (bairro) marcarInvalido(bairro, 'Informe o bairro.');
      valido = false;
    }

    if (!cidade || !cidade.value.trim()) {
      if (cidade) marcarInvalido(cidade, 'Informe a cidade.');
      valido = false;
    }

    if (!uf || !uf.value) {
      if (uf) marcarInvalido(uf, 'Selecione o estado (UF).');
      valido = false;
    }

    const whatsLimpo = whatsapp ? whatsapp.value.replace(/\D/g, '') : '';
    if (whatsLimpo.length < 10) {
      if (whatsapp) marcarInvalido(whatsapp, 'Informe um número de telefone com DDD válido.');
      valido = false;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email.value.trim())) {
      if (email) marcarInvalido(email, 'Informe um e-mail válido.');
      valido = false;
    }
  }
  else if (etapa === 3) {
    // Dependentes
    const radioSim = document.querySelector('input[name="possui_dependentes_radio"][value="sim"]');
    const possuiDep = radioSim && radioSim.checked;
    if (possuiDep) {
      if (listaDependentes.length === 0) {
        showToast('Você indicou que possui dependentes. Clique em "+ Adicionar Dependente" para cadastrá-los.', 'error');
        valido = false;
      } else {
        for (let i = 0; i < listaDependentes.length; i++) {
          const dep = listaDependentes[i];
          const nomeInput = document.getElementById(`dep_nome_${dep.id}`);
          const parentescoSelect = document.getElementById(`dep_parentesco_${dep.id}`);

          if (!nomeInput || !nomeInput.value.trim()) {
            if (nomeInput) marcarInvalido(nomeInput, 'Informe o nome do dependente.');
            valido = false;
          }
          if (!parentescoSelect || !parentescoSelect.value) {
            if (parentescoSelect) marcarInvalido(parentescoSelect, 'Selecione o parentesco.');
            valido = false;
          }
        }
      }
    }
  }
  else if (etapa === 4) {
    // Uploads Obrigatórios (Checklist Oficial GERH)
    if (!arquivosSelecionados.doc_identificacao) {
      showToast('O upload do RG, CPF e/ou CNH é obrigatório.', 'error');
      destacarDropzone('dropzoneIdentificacao');
      valido = false;
    }
    else if (!arquivosSelecionados.doc_residencia) {
      showToast('O upload do Comprovante de Residência é obrigatório.', 'error');
      destacarDropzone('dropzoneResidencia');
      valido = false;
    }
  }
  else if (etapa === 5) {
    const aceite = document.getElementById('aceite_termo');
    if (!aceite.checked) {
      showToast('Você precisa ler e marcar o Termo de Declaração para concluir o envio.', 'error');
      valido = false;
    }
  }

  if (!valido && etapa !== 3 && etapa !== 4 && etapa !== 5) {
    showToast('Por favor, preencha todos os campos obrigatórios marcados em vermelho.', 'error');
  }

  return valido;
}

function marcarInvalido(elemento, mensagem) {
  elemento.classList.add('is-invalid');
  elemento.classList.remove('is-valid');
  const parent = elemento.closest('.form-group');
  if (parent) {
    let feedback = parent.querySelector('.field-feedback');
    if (!feedback) {
      feedback = document.createElement('small');
      feedback.className = 'field-feedback error';
      parent.appendChild(feedback);
    }
    feedback.textContent = mensagem;
    feedback.className = 'field-feedback error';
  }
}

function limparErrosVisuais() {
  document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
  document.querySelectorAll('.field-feedback.error').forEach(el => el.textContent = '');
  document.querySelectorAll('.upload-card').forEach(el => el.style.borderColor = '');
}

function destacarDropzone(id) {
  const el = document.getElementById(id);
  if (el) {
    el.style.borderColor = '#EF4444';
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

/* ========================================================
   3. MÁSCARAS E VALIDAÇÃO DE CPF / CEP
   ======================================================== */

function inicializarMascaras() {
  const cpfInput = document.getElementById('cpf');
  if (cpfInput) {
    cpfInput.addEventListener('input', (e) => {
      let v = e.target.value.replace(/\D/g, '');
      if (v.length > 11) v = v.substring(0, 11);
      if (v.length > 9) v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
      else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
      else if (v.length > 3) v = v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
      e.target.value = v;

      const feedback = document.getElementById('cpfFeedback');
      if (v.replace(/\D/g, '').length === 11) {
        if (validarCPF(v)) {
          cpfInput.classList.remove('is-invalid');
          cpfInput.classList.add('is-valid');
          if (feedback) { feedback.textContent = 'CPF Válido'; feedback.className = 'field-feedback success'; }
        } else {
          cpfInput.classList.add('is-invalid');
          cpfInput.classList.remove('is-valid');
          if (feedback) { feedback.textContent = 'Dígitos verificadores do CPF inválidos'; feedback.className = 'field-feedback error'; }
        }
      } else {
        cpfInput.classList.remove('is-valid', 'is-invalid');
        if (feedback) feedback.textContent = '';
      }
    });
  }

  const cepInput = document.getElementById('cep');
  if (cepInput) {
    cepInput.addEventListener('input', (e) => {
      let v = e.target.value.replace(/\D/g, '');
      if (v.length > 8) v = v.substring(0, 8);
      if (v.length > 5) v = v.replace(/(\d{5})(\d{1,3})/, '$1-$2');
      e.target.value = v;

      if (v.replace(/\D/g, '').length === 8) {
        buscarViaCEP(v.replace(/\D/g, ''));
      }
    });
  }

  const whatsInput = document.getElementById('whatsapp');
  if (whatsInput) {
    whatsInput.addEventListener('input', (e) => {
      let v = e.target.value.replace(/\D/g, '');
      if (v.length > 11) v = v.substring(0, 11);
      if (v.length > 10) v = v.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
      else if (v.length > 6) v = v.replace(/(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3');
      else if (v.length > 2) v = v.replace(/(\d{2})(\d{0,5})/, '($1) $2');
      e.target.value = v;
    });
  }
}

function validarCPF(cpf) {
  cpf = cpf.replace(/\D/g, '');
  if (cpf.length !== 11 || !!cpf.match(/(\d)\1{10}/)) return false;
  
  let soma = 0, resto;
  for (let i = 1; i <= 9; i++) soma += parseInt(cpf.substring(i - 1, i)) * (11 - i);
  resto = (soma * 10) % 11;
  if ((resto === 10) || (resto === 11)) resto = 0;
  if (resto !== parseInt(cpf.substring(9, 10))) return false;
  
  soma = 0;
  for (let i = 1; i <= 10; i++) soma += parseInt(cpf.substring(i - 1, i)) * (12 - i);
  resto = (soma * 10) % 11;
  if ((resto === 10) || (resto === 11)) resto = 0;
  if (resto !== parseInt(cpf.substring(10, 11))) return false;
  
  return true;
}

async function buscarViaCEP(cep) {
  const spinner = document.getElementById('cepSpinner');
  const feedback = document.getElementById('cepFeedback');
  const logradouro = document.getElementById('logradouro');
  const bairro = document.getElementById('bairro');
  const cidade = document.getElementById('cidade');
  const uf = document.getElementById('uf');
  const numero = document.getElementById('numero');

  try {
    if (spinner) spinner.classList.add('active');
    if (feedback) { feedback.textContent = 'Buscando endereço...'; feedback.className = 'field-feedback'; }

    const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
    const data = await response.json();

    if (data.erro) {
      if (feedback) { feedback.textContent = 'CEP não encontrado. Preencha manualmente.'; feedback.className = 'field-feedback error'; }
      return;
    }

    if (logradouro) logradouro.value = data.logradouro || '';
    if (bairro) bairro.value = data.bairro || '';
    if (cidade) cidade.value = data.localidade || '';
    if (uf && data.uf) uf.value = data.uf;

    if (feedback) { feedback.textContent = `${data.localidade}/${data.uf} localizado com sucesso`; feedback.className = 'field-feedback success'; }
    if (numero) numero.focus();

  } catch (error) {
    if (feedback) { feedback.textContent = 'Não foi possível consultar o CEP automaticamente. Preencha os campos abaixo.'; feedback.className = 'field-feedback error'; }
  } finally {
    if (spinner) spinner.classList.remove('active');
  }
}

/* ========================================================
   3. GESTÃO DE DEPENDENTES
   ======================================================== */

function verificarExibicaoUploadDependentes() {
  const radioSim = document.querySelector('input[name="possui_dependentes_radio"][value="sim"]');
  const cardUploadDep = document.getElementById('cardUploadDependentes');
  const temDep = radioSim && radioSim.checked && listaDependentes.length > 0;
  
  if (cardUploadDep) {
    if (temDep) {
      cardUploadDep.classList.remove('hidden');
    } else {
      cardUploadDep.classList.add('hidden');
      arquivosSelecionados.doc_dependentes = [];
      const idleDep = document.getElementById('idleDependentes');
      const prevDep = document.getElementById('prevDependentes');
      if (idleDep) idleDep.classList.remove('hidden');
      if (prevDep) {
        prevDep.classList.add('hidden');
        prevDep.innerHTML = '';
      }
      const inputDep = document.getElementById('doc_dependentes');
      if (inputDep) inputDep.value = '';
    }
  }
}

function configurarDependentes() {
  const radioNao = document.querySelector('input[name="possui_dependentes_radio"][value="nao"]');
  const radioSim = document.querySelector('input[name="possui_dependentes_radio"][value="sim"]');
  const container = document.getElementById('dependentesContainer');
  const btnAdd = document.getElementById('btnAddDependente');

  function toggleContainer() {
    if (radioSim.checked) {
      container.classList.remove('hidden');
      if (listaDependentes.length === 0) {
        adicionarDependente();
      }
    } else {
      container.classList.add('hidden');
      listaDependentes = [];
      renderizarDependentes();
    }
    verificarExibicaoUploadDependentes();
  }

  if (radioNao) radioNao.addEventListener('change', toggleContainer);
  if (radioSim) radioSim.addEventListener('change', toggleContainer);
  if (btnAdd) btnAdd.addEventListener('click', () => adicionarDependente());
}

function adicionarDependente() {
  const depId = Date.now();
  listaDependentes.push({
    id: depId,
    nome: '',
    parentesco: 'Filho(a)',
    cpf: '',
    data_nascimento: ''
  });
  renderizarDependentes();
  verificarExibicaoUploadDependentes();
}

function removerDependente(depId) {
  listaDependentes = listaDependentes.filter(d => d.id !== depId);
  renderizarDependentes();
  verificarExibicaoUploadDependentes();
}

function renderizarDependentes() {
  const listContainer = document.getElementById('dependentesList');
  if (!listContainer) return;

  listContainer.innerHTML = '';

  listaDependentes.forEach((dep, index) => {
    const card = document.createElement('div');
    card.className = 'dependente-card';
    card.id = `depCard_${dep.id}`;

    card.innerHTML = `
      <div class="dependente-card-header">
        <span class="dependente-card-title"><i class="fa-solid fa-user-group"></i> Dependente #${index + 1}</span>
        <button type="button" class="btn-remove-dep" onclick="removerDependente(${dep.id})">
          <i class="fa-regular fa-trash-can"></i> Remover
        </button>
      </div>

      <div class="form-grid">
        <div class="form-group col-span-2">
          <label class="form-label">Nome Completo do Dependente <span class="req">*</span></label>
          <input type="text" id="dep_nome_${dep.id}" class="form-control" placeholder="Nome completo" value="${dep.nome}" required oninput="atualizarDepDado(${dep.id}, 'nome', this.value)">
        </div>

        <div class="form-group">
          <label class="form-label">Grau de Parentesco <span class="req">*</span></label>
          <select id="dep_parentesco_${dep.id}" class="form-control" required onchange="atualizarDepDado(${dep.id}, 'parentesco', this.value)">
            <option value="Filho(a)" ${dep.parentesco === 'Filho(a)' ? 'selected' : ''}>Filho(a)</option>
            <option value="Cônjuge / Companheiro(a)" ${dep.parentesco.includes('Cônjuge') ? 'selected' : ''}>Cônjuge / Companheiro(a)</option>
            <option value="Pai / Mãe" ${dep.parentesco === 'Pai / Mãe' ? 'selected' : ''}>Pai / Mãe</option>
            <option value="Enteado(a)" ${dep.parentesco === 'Enteado(a)' ? 'selected' : ''}>Enteado(a)</option>
            <option value="Menor sob Guarda" ${dep.parentesco === 'Menor sob Guarda' ? 'selected' : ''}>Menor sob Guarda</option>
            <option value="Outro" ${dep.parentesco === 'Outro' ? 'selected' : ''}>Outro</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Data de Nascimento</label>
          <input type="date" id="dep_nasc_${dep.id}" class="form-control" value="${dep.data_nascimento}" onchange="atualizarDepDado(${dep.id}, 'data_nascimento', this.value)">
        </div>

        <div class="form-group col-span-2">
          <label class="form-label">CPF do Dependente</label>
          <input type="text" id="dep_cpf_${dep.id}" class="form-control" placeholder="000.000.000-00" maxlength="14" value="${dep.cpf}" oninput="mascaraCPFDep(this, ${dep.id})">
        </div>
      </div>
    `;

    listContainer.appendChild(card);
  });
}

function atualizarDepDado(id, campo, valor) {
  const dep = listaDependentes.find(d => d.id === id);
  if (dep) dep[campo] = valor;
}

function mascaraCPFDep(input, id) {
  let v = input.value.replace(/\D/g, '');
  if (v.length > 11) v = v.substring(0, 11);
  if (v.length > 9) v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
  else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
  else if (v.length > 3) v = v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
  input.value = v;
  atualizarDepDado(id, 'cpf', v);
}

/* ========================================================
   5. UPLOADS E DROPZONES (8 ITENS CHECKLIST GERH)
   ======================================================== */

function configurarDropzones() {
  const configs = [
    { inputId: 'doc_foto3x4', idleId: 'idleFoto3x4', prevId: 'prevFoto3x4', key: 'doc_foto3x4', multiple: false },
    { inputId: 'doc_identificacao', idleId: 'idleIdentificacao', prevId: 'prevIdentificacao', key: 'doc_identificacao', multiple: false },
    { inputId: 'doc_titulo', idleId: 'idleTitulo', prevId: 'prevTitulo', key: 'doc_titulo', multiple: false },
    { inputId: 'doc_residencia', idleId: 'idleResidencia', prevId: 'prevResidencia', key: 'doc_residencia', multiple: false },
    { inputId: 'doc_ctps', idleId: 'idleCtps', prevId: 'prevCtps', key: 'doc_ctps', multiple: false },
    { inputId: 'doc_escolaridade', idleId: 'idleEscolaridade', prevId: 'prevEscolaridade', key: 'doc_escolaridade', multiple: false },
    { inputId: 'doc_dependentes', idleId: 'idleDependentes', prevId: 'prevDependentes', key: 'doc_dependentes', multiple: true }
  ];

  configs.forEach(cfg => {
    const input = document.getElementById(cfg.inputId);
    const dropzone = input ? input.closest('.dropzone-box') : null;

    if (!input || !dropzone) return;

    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('dragover');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
      }, false);
    });

    dropzone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        tratarArquivos(files, cfg);
      }
    });

    input.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        tratarArquivos(e.target.files, cfg);
      }
    });
  });
}

function tratarArquivos(fileList, cfg) {
  const maxBytes = 10 * 1024 * 1024; // 10MB

  if (!cfg.multiple) {
    const file = fileList[0];
    if (file.size > maxBytes) {
      showToast(`O arquivo "${file.name}" ultrapassa o limite de 10MB.`, 'error');
      return;
    }
    arquivosSelecionados[cfg.key] = file;
  } else {
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      if (file.size > maxBytes) {
        showToast(`O arquivo "${file.name}" ultrapassa 10MB e foi ignorado.`, 'error');
        continue;
      }
      arquivosSelecionados[cfg.key].push(file);
    }
  }

  renderizarPreviewUpload(cfg);
}

function renderizarPreviewUpload(cfg) {
  const idleEl = document.getElementById(cfg.idleId);
  const prevEl = document.getElementById(cfg.prevId);

  if (!cfg.multiple) {
    const file = arquivosSelecionados[cfg.key];
    if (file) {
      idleEl.classList.add('hidden');
      prevEl.classList.remove('hidden');

      const isPdf = file.name.toLowerCase().endsWith('.pdf');
      const iconClass = isPdf ? 'fa-regular fa-file-pdf' : 'fa-regular fa-file-image';
      const sizeMb = (file.size / (1024 * 1024)).toFixed(2);

      prevEl.innerHTML = `
        <div class="file-preview-pill">
          <i class="${iconClass}"></i>
          <span class="file-preview-name" title="${file.name}">${file.name}</span>
          <span class="file-preview-size">(${sizeMb} MB)</span>
          <button type="button" class="btn-remove-file" onclick="removerArquivoUpload('${cfg.key}', event)" title="Remover">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      `;
    } else {
      idleEl.classList.remove('hidden');
      prevEl.classList.add('hidden');
      prevEl.innerHTML = '';
    }
  } else {
    const files = arquivosSelecionados[cfg.key];
    if (files.length > 0) {
      idleEl.classList.add('hidden');
      prevEl.classList.remove('hidden');

      let html = '';
      files.forEach((file, idx) => {
        const isPdf = file.name.toLowerCase().endsWith('.pdf');
        const iconClass = isPdf ? 'fa-regular fa-file-pdf' : 'fa-regular fa-file-image';
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);

        html += `
          <div class="file-preview-pill">
            <i class="${iconClass}"></i>
            <span class="file-preview-name" title="${file.name}">${file.name}</span>
            <span class="file-preview-size">(${sizeMb} MB)</span>
            <button type="button" class="btn-remove-file" onclick="removerArquivoMulti('${cfg.key}', ${idx}, event)" title="Remover">
              <i class="fa-solid fa-xmark"></i>
            </button>
          </div>
        `;
      });
      prevEl.innerHTML = html;
    } else {
      idleEl.classList.remove('hidden');
      prevEl.classList.add('hidden');
      prevEl.innerHTML = '';
    }
  }
}

function removerArquivoUpload(key, e) {
  if (e) { e.preventDefault(); e.stopPropagation(); }
  arquivosSelecionados[key] = null;
  const input = document.getElementById(key);
  if (input) input.value = '';

  const idMap = {
    doc_foto3x4: ['idleFoto3x4', 'prevFoto3x4'],
    doc_identificacao: ['idleIdentificacao', 'prevIdentificacao'],
    doc_titulo: ['idleTitulo', 'prevTitulo'],
    doc_residencia: ['idleResidencia', 'prevResidencia'],
    doc_ctps: ['idleCtps', 'prevCtps'],
    doc_escolaridade: ['idleEscolaridade', 'prevEscolaridade']
  };

  const [idleId, prevId] = idMap[key] || ['idleIdentificacao', 'prevIdentificacao'];
  renderizarPreviewUpload({ inputId: key, idleId, prevId, key, multiple: false });
}

function removerArquivoMulti(key, idx, e) {
  if (e) { e.preventDefault(); e.stopPropagation(); }
  arquivosSelecionados[key].splice(idx, 1);
  renderizarPreviewUpload({
    inputId: key,
    idleId: 'idleDependentes',
    prevId: 'prevDependentes',
    key: key,
    multiple: true
  });
}

/* ========================================================
   6. RESUMO DA ETAPA 7 (REVISÃO)
   ======================================================== */

function gerarResumoRevisao() {
  const getVal = id => {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
  };

  // 1. Dados Pessoais & Escolaridade
  const revPessoais = document.getElementById('revDadosPessoais');
  if (revPessoais) {
    revPessoais.innerHTML = `
      <div class="review-item"><span class="review-label">Nome Completo</span><span class="review-value">${getVal('nome_completo')}</span></div>
      <div class="review-item"><span class="review-label">CPF</span><span class="review-value">${getVal('cpf')}</span></div>
      <div class="review-item"><span class="review-label">RG / Órgão</span><span class="review-value">${getVal('rg')} (${getVal('rg_orgao')}/${getVal('rg_uf')})</span></div>
      <div class="review-item"><span class="review-label">Nascimento</span><span class="review-value">${formatarDataBR(getVal('data_nascimento'))}</span></div>
      <div class="review-item"><span class="review-label">Escolaridade</span><span class="review-value">${getVal('escolaridade')} ${getVal('curso_formacao') ? '- ' + getVal('curso_formacao') : ''}</span></div>
      <div class="review-item"><span class="review-label">Título de Eleitor</span><span class="review-value">${getVal('titulo_eleitor')} (Zona: ${getVal('titulo_zona') || '-'}, Seção: ${getVal('titulo_secao') || '-'})</span></div>
      <div class="review-item"><span class="review-label">Carteira de Trabalho</span><span class="review-value">${getVal('ctps_numero') ? getVal('ctps_numero') + ' / ' + getVal('ctps_serie') : 'Não informada'}</span></div>
      <div class="review-item"><span class="review-label">Mãe / Pai</span><span class="review-value">${getVal('nome_mae')} / ${getVal('nome_pai') || 'Pai não informado'}</span></div>
    `;
  }

  // 2. Endereço e Contato
  const revEndereco = document.getElementById('revEnderecoContato');
  if (revEndereco) {
    revEndereco.innerHTML = `
      <div class="review-item"><span class="review-label">Endereço</span><span class="review-value">${getVal('logradouro')}, Nº ${getVal('numero')} ${getVal('complemento') ? '(' + getVal('complemento') + ')' : ''}</span></div>
      <div class="review-item"><span class="review-label">Bairro / Cidade</span><span class="review-value">${getVal('bairro')} - ${getVal('cidade')}/${getVal('uf')} (CEP: ${getVal('cep')})</span></div>
      <div class="review-item"><span class="review-label">WhatsApp</span><span class="review-value">${getVal('whatsapp')}</span></div>
      <div class="review-item"><span class="review-label">E-mails</span><span class="review-value">${getVal('email_pessoal')} ${getVal('email_institucional') ? ' | ' + getVal('email_institucional') : ''}</span></div>
    `;
  }

  // 3. Dependentes
  const revDep = document.getElementById('revDependentes');
  if (revDep) {
    const possuiDep = document.querySelector('input[name="possui_dependentes_radio"]:checked').value === 'sim';
    if (!possuiDep || listaDependentes.length === 0) {
      revDep.innerHTML = `<span class="text-muted">Nenhum dependente cadastrado.</span>`;
    } else {
      let depHtml = '';
      listaDependentes.forEach((d, i) => {
        depHtml += `
          <div class="review-item">
            <span class="review-label">Dependente #${i+1} (${d.parentesco})</span>
            <span class="review-value">${d.nome} ${d.cpf ? ' - CPF: ' + d.cpf : ''} ${d.data_nascimento ? '(' + formatarDataBR(d.data_nascimento) + ')' : ''}</span>
          </div>
        `;
      });
      revDep.innerHTML = depHtml;
    }
  }

  // 4. Documentos Anexados
  const revDocs = document.getElementById('revDocumentos');
  if (revDocs) {
    let docsHtml = '';
    const docs = [
      { key: 'doc_foto3x4', label: 'Foto 3x4' },
      { key: 'doc_identificacao', label: 'RG, CPF e/ou CNH' },
      { key: 'doc_titulo', label: 'Título de Eleitor' },
      { key: 'doc_residencia', label: 'Comprovante de Residência' },
      { key: 'doc_ctps', label: 'Carteira de Trabalho (CTPS)' },
      { key: 'doc_escolaridade', label: 'Grau de Escolaridade (Diploma)' }
    ];

    docs.forEach(d => {
      if (arquivosSelecionados[d.key]) {
        docsHtml += `<div class="review-file-item"><i class="fa-solid fa-check text-green"></i> <span><strong>${d.label}:</strong> ${arquivosSelecionados[d.key].name}</span></div>`;
      }
    });

    if (arquivosSelecionados.doc_dependentes && arquivosSelecionados.doc_dependentes.length > 0) {
      docsHtml += `<div class="review-file-item"><i class="fa-solid fa-check text-green"></i> <span><strong>Documentos dos Dependentes:</strong> ${arquivosSelecionados.doc_dependentes.length} arquivo(s)</span></div>`;
    }

    revDocs.innerHTML = docsHtml || '<span class="text-muted">Nenhum documento anexado.</span>';
  }
}

function formatarDataBR(dataIso) {
  if (!dataIso) return '';
  const partes = dataIso.split('-');
  if (partes.length === 3) return `${partes[2]}/${partes[1]}/${partes[0]}`;
  return dataIso;
}

/* ========================================================
   5. SUBMISSÃO DO FORMULÁRIO (ENVIO PARA O BACKEND)
   ======================================================== */

function configurarEventos() {
  const form = document.getElementById('recadastramentoForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (!validarEtapa(5)) return;

      const modalLoading = document.getElementById('loadingModal');
      if (modalLoading) modalLoading.classList.remove('hidden');

      try {
        const formData = new FormData();

        // 1. Dados Pessoais
        formData.append('nome_completo', document.getElementById('nome_completo').value.trim());
        formData.append('cpf', document.getElementById('cpf').value.trim());
        formData.append('rg', document.getElementById('rg').value.trim());
        formData.append('rg_orgao', document.getElementById('rg_orgao').value.trim());
        formData.append('rg_uf', document.getElementById('rg_uf').value);
        formData.append('rg_data_expedicao', document.getElementById('rg_data_expedicao').value);
        formData.append('data_nascimento', document.getElementById('data_nascimento').value);
        formData.append('sexo', document.getElementById('sexo').value);
        formData.append('estado_civil', document.getElementById('estado_civil').value);
        formData.append('nome_mae', document.getElementById('nome_mae').value.trim());
        formData.append('nome_pai', document.getElementById('nome_pai').value.trim());
        formData.append('titulo_eleitor', document.getElementById('titulo_eleitor').value.trim());
        formData.append('titulo_zona', document.getElementById('titulo_zona').value.trim());
        formData.append('titulo_secao', document.getElementById('titulo_secao').value.trim());
        formData.append('escolaridade', document.getElementById('escolaridade').value);
        formData.append('curso_formacao', document.getElementById('curso_formacao').value.trim());
        formData.append('ctps_numero', document.getElementById('ctps_numero').value.trim());
        formData.append('ctps_serie', document.getElementById('ctps_serie').value.trim());
        formData.append('ctps_uf', document.getElementById('rg_uf').value);

        // 2. Endereço & Contato
        formData.append('cep', document.getElementById('cep').value.trim());
        formData.append('logradouro', document.getElementById('logradouro').value.trim());
        formData.append('numero', document.getElementById('numero').value.trim());
        formData.append('complemento', document.getElementById('complemento').value.trim());
        formData.append('bairro', document.getElementById('bairro').value.trim());
        formData.append('cidade', document.getElementById('cidade').value.trim());
        formData.append('uf', document.getElementById('uf').value);
        formData.append('whatsapp', document.getElementById('whatsapp').value.trim());
        formData.append('email_pessoal', document.getElementById('email_pessoal').value.trim());
        formData.append('email_institucional', document.getElementById('email_institucional').value.trim());

        // 3. Dependentes
        const possuiDep = document.querySelector('input[name="possui_dependentes_radio"]:checked').value === 'sim';
        formData.append('possui_dependentes', possuiDep ? 'true' : 'false');
        formData.append('dependentes_json', JSON.stringify(possuiDep ? listaDependentes : []));

        // 4. Arquivos do Checklist Oficial GERH
        if (arquivosSelecionados.doc_foto3x4) formData.append('doc_foto3x4', arquivosSelecionados.doc_foto3x4);
        formData.append('doc_identificacao', arquivosSelecionados.doc_identificacao);
        if (arquivosSelecionados.doc_titulo) formData.append('doc_titulo', arquivosSelecionados.doc_titulo);
        formData.append('doc_residencia', arquivosSelecionados.doc_residencia);
        if (arquivosSelecionados.doc_ctps) formData.append('doc_ctps', arquivosSelecionados.doc_ctps);
        if (arquivosSelecionados.doc_escolaridade) formData.append('doc_escolaridade', arquivosSelecionados.doc_escolaridade);

        if (arquivosSelecionados.doc_dependentes && arquivosSelecionados.doc_dependentes.length > 0) {
          arquivosSelecionados.doc_dependentes.forEach(file => {
            formData.append('doc_dependentes', file);
          });
        }

        const response = await fetch(`${API_BASE_URL}/api/recadastramento/enviar`, {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || 'Ocorreu um erro ao registrar suas informações.');
        }

        const resData = await response.json();
        exibirTelaSucesso(resData);

      } catch (err) {
        console.error('Erro no envio:', err);
        showToast(`Erro ao enviar: ${err.message}`, 'error');
      } finally {
        if (modalLoading) modalLoading.classList.add('hidden');
      }
    });
  }
}

function exibirTelaSucesso(data) {
  document.querySelector('.form-card').classList.add('hidden');
  document.querySelector('.stepper-wrapper').classList.add('hidden');

  document.getElementById('resProtocolo').textContent = data.protocolo || 'ITPS-REC-2026-00001';
  document.getElementById('resNome').textContent = data.nome_completo || '';
  document.getElementById('resCpf').textContent = data.cpf || '';
  document.getElementById('resDataHora').textContent = data.data_envio || '';

  const successScreen = document.getElementById('successScreen');
  if (successScreen) {
    successScreen.classList.remove('hidden');
    window.scrollTo({ top: 100, behavior: 'smooth' });
  }

  showToast('Documentação enviada e registrada com sucesso!', 'success');
}

function copiarProtocolo() {
  const protocolo = document.getElementById('resProtocolo').textContent;
  navigator.clipboard.writeText(protocolo).then(() => {
    const copyText = document.getElementById('copyText');
    if (copyText) {
      copyText.textContent = 'Copiado!';
      setTimeout(() => { copyText.textContent = 'Copiar'; }, 2500);
    }
    showToast('Número de protocolo copiado para a área de transferência!', 'success');
  }).catch(() => {
    showToast('Não foi possível copiar automaticamente.', 'error');
  });
}

/* ========================================================
   8. TOAST NOTIFICATIONS
   ======================================================== */

function showToast(mensagem, tipo = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast-item toast-${tipo}`;
  
  const icon = tipo === 'error' ? 'fa-solid fa-triangle-exclamation' : (tipo === 'success' ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-info');
  toast.innerHTML = `<i class="${icon}"></i> <span>${mensagem}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(12px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
