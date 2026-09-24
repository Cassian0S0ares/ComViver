const goalForm = document.querySelector('[data-campaign-goals]');
if (goalForm) {
  const addItemButton = goalForm.querySelector('[data-add-meta]');
  const addMoneyButton = goalForm.querySelector('[data-add-money]');
  const list = goalForm.querySelector('[data-meta-list]');
  const template = goalForm.querySelector('[data-meta-template]');
  const total = goalForm.querySelector('[name="metas-TOTAL_FORMS"]');
  const moneyRow = list.querySelector('[data-money-goal]');
  const moneyValue = moneyRow.querySelector('[name="meta_valor"]');

  const updateUnits = row => {
    const type = row.querySelector('select[name$="-tipo"]');
    const unit = row.querySelector('select[name$="-unidade"]');
    if (!type || !unit) return;
    for (const option of unit.options) {
      const base = /^c\d+$/.test(type.value) ? 'ITEM' : type.value;
      const allowed = !option.value || option.dataset.tipos?.split(' ').includes(base);
      option.hidden = !allowed;
      option.disabled = !allowed;
    }
    if (unit.selectedOptions[0]?.disabled) unit.value = '';
  };

  const itemHasContent = row =>
    Boolean(row.querySelector('input[name$="-id"]')?.value) ||
    Boolean(row.querySelector('select[name$="-tipo"]')?.value) ||
    Boolean(row.querySelector('input[name$="-quantidade"]')?.value) ||
    Boolean(row.querySelector('select[name$="-unidade"]')?.value) ||
    Boolean(row.querySelector('.field-error'));

  const itemRows = () => [...list.querySelectorAll('[data-item-goal]')];
  const visibleRows = () => [...list.querySelectorAll('[data-meta-row]:not([hidden])')];

  const updateRemoveButtons = () => {
    const canRemove = visibleRows().length > 1;
    list.querySelectorAll('[data-remove-meta]').forEach(button => {
      button.hidden = !canRemove || button.closest('[data-meta-row]').hidden;
      button.disabled = button.hidden;
    });
    addMoneyButton.hidden = !moneyRow.hidden;
  };

  const showBlankItemIfNeeded = () => {
    if (visibleRows().length) return;
    const blank = itemRows().find(row => !row.querySelector('input[name$="-DELETE"]')?.checked);
    if (blank) blank.hidden = false;
  };

  moneyRow.hidden = !moneyValue.value && !moneyRow.querySelector('.field-error');
  itemRows().forEach(row => {
    row.querySelector('[data-remove-fallback]').hidden = true;
    row.hidden = Boolean(row.querySelector('input[name$="-DELETE"]')?.checked) || !itemHasContent(row);
    if (!row.hidden) updateUnits(row);
  });
  showBlankItemIfNeeded();
  updateRemoveButtons();

  list.addEventListener('change', event => {
    if (event.target.matches('select[name$="-tipo"]')) {
      updateUnits(event.target.closest('[data-item-goal]'));
    }
  });

  list.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-meta]');
    if (!button || button.hidden) return;
    const row = button.closest('[data-meta-row]');
    if (row === moneyRow) {
      moneyValue.value = '';
    } else {
      row.querySelector('input[name$="-DELETE"]').checked = true;
    }
    row.hidden = true;
    showBlankItemIfNeeded();
    updateRemoveButtons();
  });

  addItemButton.disabled = false;
  addItemButton.addEventListener('click', () => {
    let row = itemRows().find(item => item.hidden && !item.querySelector('input[name$="-DELETE"]')?.checked && !itemHasContent(item));
    if (!row) {
      const index = Number(total.value);
      list.insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__prefix__', String(index)));
      total.value = index + 1;
      row = list.lastElementChild;
      row.querySelector('[data-remove-fallback]').hidden = true;
    }
    row.hidden = false;
    updateUnits(row);
    updateRemoveButtons();
    row.querySelector('select[name$="-tipo"]')?.focus();
  });

  addMoneyButton.disabled = false;
  addMoneyButton.addEventListener('click', () => {
    const rows = visibleRows();
    if (rows.length === 1 && rows[0].matches('[data-item-goal]') && !itemHasContent(rows[0])) {
      rows[0].hidden = true;
    }
    moneyRow.hidden = false;
    updateRemoveButtons();
    moneyValue.focus();
  });
}
