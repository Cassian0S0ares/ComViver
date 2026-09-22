/* Progressive enhancement. POSTs, validation and authorization stay on the server. */
document.querySelectorAll('[data-password]').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.password);
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    input.toggleAttribute('data-revealed', visible);
    button.setAttribute('aria-pressed', String(visible));
    const label = input.labels?.[0]?.textContent.replace('*', '').trim().toLowerCase() || 'senha';
    button.setAttribute('aria-label', `${visible ? 'Ocultar' : 'Mostrar'} ${label}`);
    button.querySelector('i').className = visible ? 'bi bi-eye-slash' : 'bi bi-eye';
  });
});
const menuButton = document.querySelector('[data-menu]');
menuButton?.addEventListener('click', () => {
  const open = menuButton.getAttribute('aria-expanded') !== 'true';
  document.getElementById('navegacao').classList.toggle('is-open', open);
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.setAttribute('aria-label', open ? 'Fechar navegação' : 'Abrir navegação');
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && menuButton?.getAttribute('aria-expanded') === 'true') {
    menuButton.click(); menuButton.focus();
  }
});
document.querySelectorAll('[data-clear-search]').forEach(button => {
  const input = button.closest('form').querySelector('input[type=search]');
  input.addEventListener('input', () => { button.hidden = !input.value; });
  button.addEventListener('click', () => { input.value = ''; input.focus(); input.form.requestSubmit(); });
});
// Filtro sem botao: a tabela se atualiza enquanto a pessoa digita e ao mudar a
// selecao. Quem filtra e o servidor, como no envio normal do formulario; so a
// tabela e trocada, para nao recarregar a pagina nem tirar o foco do campo.
// Sem JavaScript, o formulario continua funcionando pelo botao do noscript.
document.querySelectorAll('[data-auto-filtrar]').forEach(form => {
  const lista = document.querySelector('[data-lista]');
  const contagem = document.querySelector('[data-contagem]');
  const busca = form.querySelector('input[type=search]');
  if (!lista) return;

  let emCurso;
  let espera;

  const atualizar = async () => {
    const parametros = new URLSearchParams(new FormData(form));
    const destino = `${location.pathname}?${parametros}`;
    emCurso?.abort();
    const controle = new AbortController();
    emCurso = controle;
    lista.setAttribute('aria-busy', 'true');
    try {
      const resposta = await fetch(destino, { signal: controle.signal });
      if (!resposta.ok) throw new Error(resposta.status);
      const pagina = new DOMParser().parseFromString(await resposta.text(), 'text/html');
      lista.innerHTML = pagina.querySelector('[data-lista]').innerHTML;
      if (contagem) contagem.textContent = pagina.querySelector('[data-contagem]').textContent;
      history.replaceState(null, '', destino);
    } catch (erro) {
      // Rede fora ou resposta inesperada: cai no envio normal do formulario.
      if (erro.name !== 'AbortError') form.submit();
    } finally {
      lista.removeAttribute('aria-busy');
    }
  };

  form.addEventListener('submit', event => { event.preventDefault(); atualizar(); });
  form.querySelectorAll('select').forEach(select => {
    select.addEventListener('change', atualizar);
  });
  busca?.addEventListener('input', () => {
    clearTimeout(espera);
    espera = setTimeout(atualizar, 250);
  });
});
document.querySelectorAll('[data-dialog-close]').forEach(button => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
const firstError = document.querySelector('[aria-invalid=true], [data-form-error]');
firstError?.focus();
let dirty = false;
let destination = null;
const dirtyForm = document.querySelector('[data-dirty]');
const unsavedDialog = document.getElementById('unsaved-dialog');
dirtyForm?.addEventListener('input', () => { dirty = true; });
dirtyForm?.addEventListener('change', () => { dirty = true; });
window.addEventListener('beforeunload', event => {
  if (dirty) { event.preventDefault(); event.returnValue = ''; }
});
document.querySelectorAll('a[href]').forEach(link => {
  link.addEventListener('click', event => {
    if (!dirty || link.hash || event.ctrlKey || event.metaKey || event.shiftKey) return;
    event.preventDefault(); destination = () => { window.location.href = link.href; };
    unsavedDialog?.showModal();
  });
});
document.querySelector('[data-discard]')?.addEventListener('click', () => {
  dirty = false; unsavedDialog.close(); destination?.();
});
const permissionForm = document.querySelector('[data-permission-confirm]');
const permissionDialog = document.getElementById('permission-dialog');
const initialProfile = permissionForm?.querySelector('[name=perfil]')?.value;
const initialActive = permissionForm?.querySelector('[name=is_active]')?.checked;
let permissionConfirmed = false;
document.querySelector('[data-permission-save]')?.addEventListener('click', () => {
  permissionConfirmed = true; permissionDialog.close(); permissionForm.requestSubmit();
});
document.querySelectorAll('form[method=post]').forEach(form => {
  form.addEventListener('submit', event => {
    if (event.isComposing) { event.preventDefault(); return; }
    if (dirty && form !== dirtyForm) {
      event.preventDefault(); destination = () => form.requestSubmit(); unsavedDialog?.showModal(); return;
    }
    if (form === permissionForm && !permissionConfirmed &&
      (form.querySelector('[name=perfil]').value !== initialProfile || form.querySelector('[name=is_active]').checked !== initialActive)) {
      event.preventDefault(); permissionDialog.showModal(); return;
    }
    if (form.getAttribute('aria-busy') === 'true') { event.preventDefault(); return; }
    dirty = false; form.setAttribute('aria-busy', 'true');
    form.querySelectorAll('button[type=submit], button:not([type])').forEach(button => { button.disabled = true; });
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[aria-busy]').forEach(form => {
    form.removeAttribute('aria-busy');
    form.querySelectorAll('button').forEach(button => { button.disabled = false; });
  });
});
// Enhancement controls only become available after their handlers are attached.
document.querySelectorAll('button[data-enhancement]').forEach(button => {
  button.disabled = false;
});
