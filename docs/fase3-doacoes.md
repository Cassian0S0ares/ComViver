# Fase 3 — Doações

## Uso

1. Abra **Doadores → Novo doador** para cadastrar uma pessoa ou organização.
   Documento e contato são opcionais. Marque recorrente quando houver regularidade.
2. Em **Doações → Registrar doação**, selecione o doador ou deixe Anônimo.
   Dinheiro exige valor positivo; itens e serviços exigem descrição. Datas futuras
   são recusadas.
3. Use **Salvar e registrar outra** quando receber vários itens do mesmo doador.
   Doador e data permanecem preenchidos.
4. Abra **Recibo** na lista para imprimir, baixar PDF ou marcar a entrega.
5. Administradores criam campanhas e ajustam o término para encerrá-las.
   A campanha permanece ativa até o fim da data informada.

Dinheiro e quantidade nunca são somados juntos. O painel mostra dinheiro e número
de contribuições do mês; administradores também veem recorrentes sem doação há
60 dias. O histórico do doador inclui todas as contribuições registradas.

## Instalação

Instale `requirements/dev.txt` no ambiente Python e aplique `python manage.py migrate`.
O arquivo `iniciar.bat` executa as migrações antes de iniciar o servidor local.
Configure `.env` com a conexão PostgreSQL válida antes de abrir o sistema.

No Windows, o WeasyPrint precisa das DLLs de Pango. Neste workspace elas estão em
`.tools/weasyprint/runtime`. Para preparar outra máquina, no ambiente virtual:

```powershell
python -m pip install "pyinstaller>=6,<7"
python scripts/preparar_pdf_windows.py
```

O script obtém o pacote oficial v63.1, verifica SHA-256 e extrai apenas DLLs locais.
Não altera o PATH global. Alternativamente, configure `WEASYPRINT_DLL_DIRECTORIES`
para uma instalação de Pango existente, conforme a
[documentação oficial](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).
Linux usa a instalação de Pango recomendada na documentação da distribuição.

## Verificação

Banco de validação isolado: PostgreSQL local, porta 55432. O script
`scripts/local_validation.py` substitui as credenciais do ambiente antes dos testes.
Não usa o Supabase nem os dados da instituição.

```powershell
.venv312/Scripts/python scripts/local_validation.py -m pytest --create-db
.venv312/Scripts/python scripts/local_validation.py -m pytest tests/browser_doacoes.py
.venv312/Scripts/python -m ruff check .
.venv312/Scripts/python scripts/check_design.py
```

`--create-db` recria exclusivamente o banco de testes: evita reutilizar um banco
esvaziado pelo encerramento de testes transacionais do navegador.

`seed_demo` também cria campanha, doadores e seis tipos de doações fictícias.
Execute somente em banco descartável. A parte de doações é repetível e não apaga
registros existentes. Não foi executada contra o banco remoto.

Recibos não incluem CNPJ/endereço da instituição enquanto esses dados não forem
fornecidos. O nome usado é Lar Padre José Gumercindo.

### Resultado em 22/09/2026

- Suíte completa: 323 testes aprovados em PostgreSQL.
- Fluxo no Edge: cadastro em dinheiro/item, validação, busca por teclado,
  estado vazio, recuperação de falha de rede, salvar e registrar outra,
  recibo HTML/PDF, entrega e largura de 390 px. Também foram verificados
  cadastro/edição de doador e criação/encerramento de campanha.
- Ruff, tokens de design e auditoria estrita de interface sem erros.
- `check --deploy --settings=comviver.settings.prod`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma alteração pendente.
- `collectstatic`: concluído.
- Consulta ao Supabase configurado: conexão estabelecida; nenhuma migração pendente.

A biblioteca de fontes do WeasyPrint emite um aviso de API obsoleta nos testes;
a geração dos PDFs foi validada com sucesso. Evidências de navegador e PDF estão
na pasta local `test-results`, não versionada.
