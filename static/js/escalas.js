/* Start the day at 07:00; all 24 hours remain available by scrolling. */
const cronograma = document.querySelector('[data-cronograma]');
if (cronograma) {
  const hora = cronograma.querySelector('.cronograma-hora');
  const escolhida = Number(new URLSearchParams(location.search).get('hora') ?? 7);
  const inicio = Number.isFinite(escolhida) ? Math.min(23, Math.max(0, escolhida)) : 7;
  cronograma.scrollTop = inicio * hora.getBoundingClientRect().height;
}

/* Clicking a shift opens its details in a modal; edit and delete load in place. */
const detalhe = document.getElementById('turno-detalhe');
if (detalhe && window.htmx) {
  const conteudo = detalhe.querySelector('#turno-detalhe-conteudo');
  let origem = null;
  const abrir = url => htmx.ajax('GET', url, { target: conteudo, swap: 'innerHTML' }).then(() => {
    if (!detalhe.open) detalhe.showModal();
    conteudo.querySelector('h2')?.focus();
  });
  document.addEventListener('click', event => {
    const card = event.target.closest('.cronograma-evento');
    if (!card) return;
    const acao = event.target.closest('a, button');
    if (acao && !acao.matches('[data-turno-detalhe]')) return;
    const alvo = card.querySelector('[data-turno-detalhe]');
    if (!alvo) return;
    origem = alvo;
    abrir(alvo.dataset.turnoDetalhe);
  });
  document.addEventListener('htmx:afterSwap', event => {
    if (event.detail.target !== conteudo || !detalhe.open) return;
    const foco = conteudo.querySelector('[aria-invalid=true], [data-form-error], [autofocus]');
    // Adding or removing someone keeps the reader on the people list.
    const lista = event.detail.requestConfig?.verb === 'post' && conteudo.querySelector('#turno-pessoas-titulo');
    (foco ?? lista ?? conteudo.querySelector('h2'))?.focus();
  });
  detalhe.querySelector('[data-turno-detalhe-fechar]').addEventListener('click', () => detalhe.close());
  detalhe.addEventListener('click', event => { if (event.target === detalhe) detalhe.close(); });
  detalhe.addEventListener('close', () => { conteudo.replaceChildren(); origem?.focus(); });
}

/* One optional responsible select per vacancy, following the vacancies field. */
document.querySelectorAll('[data-responsaveis]').forEach(lista => {
  const form = lista.closest('form');
  const vagas = form?.elements.namedItem('vagas');
  const modelo = lista.querySelector('select');
  if (!vagas || !modelo) return;
  const limite = Number(lista.dataset.limite) || Infinity;
  const sincronizar = () => {
    const alvo = Math.max(1, Math.min(limite, Number(vagas.value) || 1, 50));
    const selects = [...lista.querySelectorAll('select')];
    selects.slice(alvo).forEach(select => select.remove());
    for (let i = selects.length; i < alvo; i++) {
      const novo = modelo.cloneNode(true);
      novo.id = `${modelo.id}_${i}`;
      novo.value = '';
      novo.setAttribute('aria-label', `Responsável ${i + 1}`);
      lista.append(novo);
    }
  };
  vagas.addEventListener('input', sincronizar);
  form.addEventListener('reset', () => setTimeout(sincronizar));
  sincronizar();
});
