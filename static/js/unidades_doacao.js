const tipoBase = valor => (/^c\d+$/.test(valor) ? 'ITEM' : valor);

function atualizarUnidades(container) {
  if (!container) return;
  const tipo = container.querySelector('select[name="tipo"], select[name$="-tipo"]');
  const unidade = container.querySelector('select[name="unidade"], select[name$="-unidade"]');
  if (!tipo || !unidade) return;

  for (const opcao of unidade.options) {
    if (!opcao.value) continue;
    const permitida = (opcao.dataset.tipos || '').split(' ').includes(tipoBase(tipo.value));
    opcao.disabled = !permitida;
    opcao.hidden = !permitida;
  }
  if (unidade.selectedOptions[0]?.disabled) unidade.value = '';
}

document.querySelectorAll('[data-unit-pair]').forEach(atualizarUnidades);
document.addEventListener('change', event => {
  if (!event.target.matches('select[name="tipo"], select[name$="-tipo"]')) return;
  atualizarUnidades(event.target.closest('[data-unit-pair]'));
});
document.addEventListener('unitpair:init', event => {
  atualizarUnidades(event.target.closest('[data-unit-pair]'));
});