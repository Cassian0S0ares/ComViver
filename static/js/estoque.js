/* Stock forms: validity only for categories that expire; the item field is a
   combobox that filters registered items and offers to create a new one.
   Without JS the input keeps its native <datalist> suggestions. */
const normalizar = texto => texto.normalize('NFD').replace(/[̀-ͯ]/g, '')
  .toLowerCase().replace(/\s+/g, ' ').trim();

function montarCombobox(input, categoria) {
  const fonte = document.getElementById(input.getAttribute('list') ?? '');
  if (!fonte) return () => {};
  const itens = [...fonte.options].map(opcao => ({
    nome: opcao.value, categoria: opcao.dataset.categoria, categoriaNome: opcao.dataset.categoriaNome,
  }));
  input.removeAttribute('list');  // the custom list replaces the native one
  const caixa = input.closest('.field-control');
  const lista = document.createElement('ul');
  const status = document.createElement('p');
  lista.id = `${input.id}-opcoes`;
  lista.className = 'combo-lista';
  lista.setAttribute('role', 'listbox');
  lista.setAttribute('aria-label', 'Itens do estoque');
  lista.hidden = true;
  status.className = 'combo-status small';
  status.setAttribute('aria-live', 'polite');
  caixa.append(lista);
  caixa.after(status);
  Object.entries({
    role: 'combobox', 'aria-autocomplete': 'list', 'aria-expanded': 'false', 'aria-controls': lista.id,
  }).forEach(([nome, valor]) => input.setAttribute(nome, valor));

  let opcoes = [];
  let ativa = -1;
  const nomeCategoria = () => (categoria.value ? categoria.selectedOptions[0].textContent.trim() : '');
  const existente = () => itens.find(item => normalizar(item.nome) === normalizar(input.value)
    && (!categoria.value || item.categoria === categoria.value));
  const informar = () => {
    const nome = input.value.trim();
    const achado = existente();
    status.classList.toggle('is-novo', Boolean(nome && !achado));
    if (!nome) status.textContent = '';
    else if (achado) status.textContent = `Item já cadastrado em ${achado.categoriaNome}.`;
    else if (categoria.value) status.textContent = `Novo item: será criado em ${nomeCategoria()} ao salvar.`;
    else status.textContent = 'Novo item: escolha a categoria para criá-lo.';
  };
  const fechar = () => {
    lista.hidden = true;
    ativa = -1;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
  };
  const marcar = indice => {
    ativa = indice;
    opcoes.forEach((opcao, i) => opcao.setAttribute('aria-selected', String(i === ativa)));
    if (opcoes[ativa]) {
      input.setAttribute('aria-activedescendant', opcoes[ativa].id);
      opcoes[ativa].scrollIntoView({ block: 'nearest' });
    } else {
      input.removeAttribute('aria-activedescendant');
    }
  };
  const escolher = opcao => {
    input.value = opcao.dataset.nome;
    if (opcao.dataset.categoria && categoria.value !== opcao.dataset.categoria) {
      categoria.value = opcao.dataset.categoria;
      categoria.dispatchEvent(new Event('change', { bubbles: true }));
    }
    input.dispatchEvent(new Event('change', { bubbles: true }));
    fechar();
    informar();
  };
  const opcao = (id, nome, detalhe) => {
    const li = document.createElement('li');
    li.id = id;
    li.setAttribute('role', 'option');
    li.dataset.nome = nome;
    const texto = document.createElement('span');
    texto.textContent = nome;
    li.append(texto);
    if (detalhe) {
      const small = document.createElement('small');
      small.textContent = detalhe;
      li.append(small);
    }
    return li;
  };
  const abrir = () => {
    const termo = normalizar(input.value);
    const achados = itens
      .filter(item => (!categoria.value || item.categoria === categoria.value)
        && (!termo || normalizar(item.nome).includes(termo)))
      .slice(0, 8);
    lista.replaceChildren(...achados.map((item, i) => {
      const li = opcao(`${lista.id}-${i}`, item.nome, categoria.value ? '' : item.categoriaNome);
      li.dataset.categoria = item.categoria;
      return li;
    }));
    const digitado = input.value.trim().replace(/\s+/g, ' ');
    if (digitado && !existente()) {
      const li = opcao(`${lista.id}-novo`, digitado,
        categoria.value ? `em ${nomeCategoria()}` : 'escolha a categoria antes de salvar');
      li.className = 'combo-criar';
      li.querySelector('span').textContent = `Criar “${digitado}”`;
      const icone = document.createElement('i');
      icone.className = 'bi bi-plus-circle';
      icone.setAttribute('aria-hidden', 'true');
      li.prepend(icone);
      lista.append(li);
    }
    if (!lista.children.length) {
      const li = document.createElement('li');
      li.className = 'combo-vazio';
      li.textContent = categoria.value ? 'Nenhum item nesta categoria ainda. Digite para criar.'
        : 'Nenhum item cadastrado ainda. Digite para criar.';
      lista.append(li);
    }
    opcoes = [...lista.querySelectorAll('[role=option]')];
    lista.hidden = false;
    input.setAttribute('aria-expanded', String(opcoes.length > 0));
    marcar(-1);
  };

  input.addEventListener('input', () => { abrir(); informar(); });
  input.addEventListener('focus', abrir);
  input.addEventListener('blur', () => setTimeout(fechar, 120));
  input.addEventListener('keydown', event => {
    if (event.isComposing) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (lista.hidden) abrir();
      if (!opcoes.length) return;
      marcar((ativa + (event.key === 'ArrowDown' ? 1 : -1) + opcoes.length) % opcoes.length);
    } else if (event.key === 'Enter' && !lista.hidden && opcoes[ativa]) {
      event.preventDefault();
      escolher(opcoes[ativa]);
    } else if (event.key === 'Escape' && !lista.hidden) {
      event.preventDefault();
      fechar();
    }
  });
  lista.addEventListener('mousedown', event => {
    const escolhida = event.target.closest('[role=option]');
    if (!escolhida) return;
    event.preventDefault();  // keep focus in the field
    escolher(escolhida);
  });
  informar();
  return () => {
    informar();
    if (!lista.hidden) abrir();
  };
}

document.querySelectorAll('[data-estoque-campos]').forEach(form => {
  const categoria = form.querySelector('[data-categoria-estoque]');
  const item = form.querySelector('[data-item-estoque]');
  const validade = form.querySelector('[name=validade]')?.closest('.field');
  if (!categoria) return;
  const reavaliarItem = item ? montarCombobox(item, categoria) : () => {};
  const atualizar = () => {
    if (validade) {
      const vence = categoria.selectedOptions[0]?.dataset.validade === '1';
      validade.hidden = !vence;
      validade.querySelector('input').disabled = !vence;
    }
    reavaliarItem();
  };
  categoria.addEventListener('change', atualizar);
  form.addEventListener('estoque:atualizar', atualizar);
  atualizar();
});

/* "Dar baixa" opens a dialog on the list; without JS the link goes to the item page. */
const baixaDialog = document.getElementById('baixa-dialog');
if (baixaDialog) {
  const form = baixaDialog.querySelector('[data-baixa-form]');
  const quantidade = form.querySelector('[name=quantidade]');
  document.addEventListener('click', event => {
    const botao = event.target.closest('[data-baixa]');
    if (!botao || event.ctrlKey || event.metaKey || event.shiftKey) return;
    event.preventDefault();
    form.action = botao.dataset.baixa;
    form.reset();
    baixaDialog.querySelector('#baixa-titulo').textContent = `Dar baixa em ${botao.dataset.baixaNome}`;
    baixaDialog.querySelector('[data-baixa-disponivel]').textContent = botao.dataset.baixaMax;
    quantidade.max = botao.dataset.baixaMax;
    form.elements.proximo.value = location.pathname + location.search;
    baixaDialog.showModal();
    quantidade.focus();
  });
}
