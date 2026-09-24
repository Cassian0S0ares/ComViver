/* HTMX busca fragmentos; a seleção nativa continua utilizável sem JavaScript. */
const donorSearch = document.querySelector('[data-donor-search]');
if (donorSearch && window.htmx) {
  donorSearch.hidden = false;
  const input = document.getElementById('doador-busca');
  input.setAttribute('hx-request', JSON.stringify({ timeout: 8000 }));
  const results = document.getElementById('doador-resultados');
  const select = document.getElementById('id_doador');
  const status = donorSearch.querySelector('[data-donor-status]');
  const clear = donorSearch.querySelector('[data-donor-clear]');
  clear.disabled = false;
  let timer, composing = false, index = -1;
  const close = () => {
    results.replaceChildren(); index = -1;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
  };
  const schedule = () => {
    clear.hidden = !input.value;
    clearTimeout(timer); htmx.trigger(input, 'htmx:abort'); close();
    status.textContent = '';
    if (composing || input.value.trim().length < 3) return;
    timer = setTimeout(() => htmx.trigger(input, 'buscarDoador'), 300);
  };
  input.addEventListener('input', schedule);
  clear.addEventListener('click', () => {
    input.value = ''; schedule(); input.focus();
  });
  input.addEventListener('compositionstart', () => { composing = true; schedule(); });
  input.addEventListener('compositionend', () => { composing = false; schedule(); });
  input.addEventListener('htmx:beforeRequest', event => {
    if (composing || input.value.trim().length < 3) { event.preventDefault(); return; }
    status.textContent = 'Buscando doadores…';
  });
  input.addEventListener('htmx:afterRequest', event => {
    if (event.detail.failed) status.textContent = 'Não foi possível buscar. Use a seleção de doador abaixo.';
  });
  ['htmx:sendError', 'htmx:timeout', 'htmx:responseError'].forEach(name => {
    input.addEventListener(name, () => {
      status.textContent = 'Não foi possível buscar. Use a seleção de doador abaixo.';
    });
  });
  document.body.addEventListener('htmx:afterSwap', event => {
    if (event.detail.target !== results) return;
    const count = results.querySelectorAll('[data-donor-id]').length;
    results.querySelectorAll('[data-donor-id]').forEach(button => { button.disabled = false; });
    input.setAttribute('aria-expanded', String(count > 0));
    status.textContent = `${count} doador(es) encontrado(s). Use as setas para selecionar.`;
  });
  const choose = button => {
    if (!select.querySelector(`option[value="${button.dataset.donorId}"]`)) {
      select.add(new Option(button.dataset.donorName, button.dataset.donorId));
    }
    select.value = button.dataset.donorId;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    input.value = ''; clear.hidden = true;
    status.textContent = `${button.dataset.donorName} selecionado.`;
    close(); select.focus();
  };
  results.addEventListener('click', event => {
    const button = event.target.closest('[data-donor-id]');
    if (button) choose(button);
  });
  input.addEventListener('keydown', event => {
    if (event.isComposing) return;
    const options = [...results.querySelectorAll('[data-donor-id]')];
    if (event.key === 'Escape') { clearTimeout(timer); htmx.trigger(input, 'htmx:abort'); close(); }
    if (['ArrowDown', 'ArrowUp'].includes(event.key) && options.length) {
      event.preventDefault();
      index = (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
      options.forEach((button, i) => button.setAttribute('aria-selected', String(i === index)));
      input.setAttribute('aria-activedescendant', options[index].id);
      options[index].scrollIntoView({ block: 'nearest' });
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      if (index >= 0 && options[index]) choose(options[index]);
    }
  });
}
const donationForm = document.querySelector('[data-doacao-form]');
if (donationForm) {
  const type = document.getElementById('id_tipo');
  const amount = document.getElementById('id_valor');
  const amountField = donationForm.querySelector('[data-campo="valor"]');
  const description = document.getElementById('id_descricao');
  const campo = nome => donationForm.querySelector(`[data-campo="${nome}"]`);
  const rotulo = (nome, texto, obrigatorio) => {
    const label = campo(nome)?.querySelector('label');
    if (label) label.textContent = `${texto}${obrigatorio ? ' *' : ''}`;
  };
  // Mostra so o que cabe no tipo: dinheiro pede valor; servico, quantidade e
  // unidade; itens vao para o estoque com categoria, item e quantidade em unidades.
  const mostrar = (nome, visivel, obrigatorio = false) => {
    const bloco = campo(nome);
    if (!bloco) return;
    bloco.hidden = !visivel;
    bloco.querySelectorAll('input, select').forEach(entrada => {
      entrada.disabled = !visivel;
      entrada.required = visivel && obrigatorio;
      if (!visivel && entrada.type !== 'checkbox') entrada.value = '';
    });
  };
  const update = () => {
    const money = type.value === 'DINHEIRO';
    const servico = type.value === 'SERVICO';
    const item = /^c\d+$/.test(type.value);
    mostrar('quantidade', Boolean(type.value) && !money, true);
    mostrar('unidade', servico, true);
    mostrar('item_nome', item, true);
    if (item) donationForm.dispatchEvent(new Event('estoque:atualizar'));
    else mostrar('validade', false);
    rotulo('quantidade', item ? 'Quantidade (unidades)' : 'Quantidade', true);
    rotulo('unidade', 'Unidade', true);
    rotulo('item_nome', 'Item', true);
    amountField.hidden = !money;
    amount.disabled = !money;
    if (!money) amount.value = '';
    amount.required = money;
    description.required = servico;
    amountField.querySelector('label').textContent = 'Valor em reais *';
    rotulo('descricao', 'Descrição', servico);
  };
  type.addEventListener('change', update); update();
}
