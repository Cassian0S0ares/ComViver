/* Stock forms: validity only for categories that expire; the item field uses
   the shared combobox (combobox.js) filtered by the chosen category. */
document.querySelectorAll('[data-estoque-campos]').forEach(form => {
  const categoria = form.querySelector('[data-categoria-estoque]');
  const item = form.querySelector('[data-item-estoque]');
  const validade = form.querySelector('[name=validade]')?.closest('.field');
  if (!categoria) return;
  const reavaliarItem = item ? montarCombobox(item, categoria, {
    lista: 'Itens do estoque',
    existente: achado => `Item já cadastrado em ${achado.categoriaNome}.`,
    novo: nome => `Novo item: será criado em ${nome} ao salvar.`,
    novoSemCategoria: 'Novo item: escolha a categoria para criá-lo.',
    criar: nome => `Criar “${nome}”`,
    criarDetalhe: nome => (nome ? `em ${nome}` : 'escolha a categoria antes de salvar'),
    vazio: 'Nenhum item cadastrado ainda. Digite para criar.',
    vazioCategoria: 'Nenhum item nesta categoria ainda. Digite para criar.',
  }) : () => {};
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
