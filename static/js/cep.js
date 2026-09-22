const cep = document.getElementById('id_cep');
const status = document.getElementById('cep-status');
if (cep && status) {
  const campos = {
    logradouro: document.getElementById('id_logradouro'),
    bairro: document.getElementById('id_bairro'),
    localidade: document.getElementById('id_cidade'),
    uf: document.getElementById('id_uf'),
  };
  let ultimaConsulta = '';
  let requisicao;
  const buscar = async () => {
    const numeros = cep.value.replace(/\D/g, '');
    if (numeros.length !== 8 || numeros === ultimaConsulta) return;
    ultimaConsulta = numeros;
    requisicao?.abort();
    const controle = new AbortController();
    requisicao = controle;
    status.textContent = 'Consultando CEP…';
    try {
      const resposta = await fetch(`https://viacep.com.br/ws/${numeros}/json/`, {
        headers: { Accept: 'application/json' },
        signal: controle.signal,
      });
      if (!resposta.ok) throw new Error('Falha na consulta');
      const endereco = await resposta.json();
      if (endereco.erro) {
        status.textContent = 'CEP não encontrado. Confira o número e preencha o endereço manualmente.';
        return;
      }
      // O endereco vem do CEP consultado agora, entao substitui o que estava
      // preenchido: trocar o CEP de um cadastro antigo tem de trocar a rua.
      // Campo que a consulta devolve vazio (CEP geral de cidade) fica como
      // esta, para nao apagar o que a pessoa ja escreveu.
      let atualizados = 0;
      Object.entries(campos).forEach(([chave, campo]) => {
        const valor = (endereco[chave] || '').trim();
        if (!campo || !valor || campo.value === valor) return;
        campo.value = valor;
        campo.dispatchEvent(new Event('change', { bubbles: true }));
        atualizados += 1;
      });
      status.textContent = atualizados
        ? 'Endereço atualizado pelo CEP. Confira os dados e complete o número.'
        : 'Endereço confere com o CEP informado.';
      const numero = document.getElementById('id_numero');
      if (atualizados && numero && !numero.value.trim()) numero.focus();
    } catch (erro) {
      if (erro.name === 'AbortError') return;
      ultimaConsulta = '';
      status.textContent = 'Não foi possível consultar o CEP. Você pode preencher o endereço manualmente.';
    }
  };
  cep.addEventListener('input', () => {
    const numeros = cep.value.replace(/\D/g, '').slice(0, 8);
    cep.value = numeros.length > 5 ? `${numeros.slice(0, 5)}-${numeros.slice(5)}` : numeros;
    if (numeros.length === 8) buscar();
    else {
      requisicao?.abort();
      ultimaConsulta = '';
      status.textContent = '';
    }
  });
}
