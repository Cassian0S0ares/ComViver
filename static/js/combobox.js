/* Typed field with suggestions: filters what is already registered and offers
   to create a new entry. The suggestions come from the input's <datalist>;
   without JS the browser keeps showing that native list.

   Optional `categoria` is a select whose options carry data-categoria: the list
   is then filtered by it (stock items). Inputs with [data-combobox] and no
   category are set up automatically, with texts from their data attributes. */
const normalizar = texto => texto.normalize('NFD').replace(/[̀-ͯ]/g, '')
  .toLowerCase().replace(/\s+/g, ' ').trim();

const TEXTOS_PADRAO = {
  lista: 'Sugestões',
  existente: () => 'Já cadastrado.',
  novo: () => 'Novo: será adicionado ao salvar.',
  novoSemCategoria: 'Novo: escolha a categoria para criá-lo.',
  criar: nome => `Adicionar “${nome}”`,
  criarDetalhe: () => '',
  vazio: 'Nada cadastrado ainda. Digite para adicionar.',
  vazioCategoria: 'Nada nesta categoria ainda. Digite para criar.',
};

function montarCombobox(input, categoria = null, textos = {}) {
  const t = { ...TEXTOS_PADRAO, ...textos };
  const fonte = document.getElementById(input.getAttribute('list') ?? '');
  if (!fonte) return () => {};
  const itens = [...fonte.options].map(opcao => ({
    nome: opcao.value, categoria: opcao.dataset.categoria, categoriaNome: opcao.dataset.categoriaNome,
  }));
  input.removeAttribute('list');  // the custom list replaces the native one
  const caixa = input.closest('.field-control') ?? input.parentElement;
  const lista = document.createElement('ul');
  const status = document.createElement('p');
  lista.id = `${input.id}-opcoes`;
  lista.className = 'combo-lista';
  lista.setAttribute('role', 'listbox');
  lista.setAttribute('aria-label', t.lista);
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
  // Works with the category select and with the donation type select ("c5").
  const catId = () => categoria?.selectedOptions[0]?.dataset.categoria ?? '';
  const nomeCategoria = () => (catId() ? categoria.selectedOptions[0].textContent.trim() : '');
  const existente = () => itens.find(item => normalizar(item.nome) === normalizar(input.value)
    && (!catId() || item.categoria === catId()));
  const informar = () => {
    const nome = input.value.trim();
    const achado = existente();
    status.classList.toggle('is-novo', Boolean(nome && !achado));
    if (!nome) status.textContent = '';
    else if (achado) status.textContent = t.existente(achado);
    else if (!categoria || catId()) status.textContent = t.novo(nomeCategoria());
    else status.textContent = t.novoSemCategoria;
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
    const destino = categoria?.querySelector(`option[data-categoria="${opcao.dataset.categoria}"]`);
    if (destino && catId() !== opcao.dataset.categoria) {
      categoria.value = destino.value;
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
      .filter(item => (!catId() || item.categoria === catId())
        && (!termo || normalizar(item.nome).includes(termo)))
      .slice(0, 8);
    lista.replaceChildren(...achados.map((item, i) => {
      const li = opcao(`${lista.id}-${i}`, item.nome, catId() ? '' : item.categoriaNome);
      if (item.categoria) li.dataset.categoria = item.categoria;
      return li;
    }));
    const digitado = input.value.trim().replace(/\s+/g, ' ');
    if (digitado && !existente()) {
      const li = opcao(`${lista.id}-novo`, digitado, t.criarDetalhe(nomeCategoria()));
      li.className = 'combo-criar';
      li.querySelector('span').textContent = t.criar(digitado);
      const icone = document.createElement('i');
      icone.className = 'bi bi-plus-circle';
      icone.setAttribute('aria-hidden', 'true');
      li.prepend(icone);
      lista.append(li);
    }
    if (!lista.children.length) {
      const li = document.createElement('li');
      li.className = 'combo-vazio';
      li.textContent = catId() ? t.vazioCategoria : t.vazio;
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

document.querySelectorAll('input[data-combobox]').forEach(input => {
  const d = input.dataset;
  montarCombobox(input, null, {
    lista: d.comboboxLista || TEXTOS_PADRAO.lista,
    existente: () => d.comboboxExistente || TEXTOS_PADRAO.existente(),
    novo: () => d.comboboxNovo || TEXTOS_PADRAO.novo(),
    vazio: d.comboboxVazio || TEXTOS_PADRAO.vazio,
  });
});
