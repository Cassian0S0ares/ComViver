# Contrato de interface ComViver

## Contexto e fontes

Equipe brasileira do Lar Padre José Gumercindo; pt-BR; fuso America/Sao_Paulo;
calendário gregoriano. Meta de acessibilidade: WCAG 2.2 AA.

| Regra | Fonte |
|---|---|
| Perfis e limites de acesso | `docs/superpowers/specs/2026-09-22-comviver-design.md`, §5.1–5.2 |
| Sessão, troca inicial e tentativas | Mesma especificação, §5.4; plano fase 1, tarefa 7 |
| Desativação preserva histórico | Plano fase 1, tarefa 10 |
| PostgreSQL e configuração | Plano fase 1, restrições globais e tarefa 1 |

Identidade visual: `DESIGN.md`; tokens canônicos em `static/css/tokens.css`.
Não há regras de cobrança ou pagamentos nesta fase.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Django Select / select HTML | DESIGN.md | native, popup do navegador | teste de teclado em navegador |
| Form | components/fields.html + FormularioAcessivelMixin | este contrato | criar, editar, senha, login | pytest + navegador |
| Scrollbar | static/css/comviver.css | DESIGN.md | tabela com overflow próprio | computed style |
| Toast | components/messages.html + Django messages | este contrato | sucesso, erro inline persistente | pytest + navegador |
| CRUD | accounts/views.py | plano fase 1, tarefa 10 | retorno à lista | pytest + navegador |
| Dialog | dialog HTML + comviver.js | este contrato | alteração de permissão, trabalho não salvo | teclado, Escape, foco |
| Indicadores do painel | templates/core/painel.html + comviver.js | este contrato | um card visível, navegação manual e sem rotação automática | teclado, leitor de tela, viewport estreito |

Não há seleção em massa. As fases 2 e 3 usam datas nativas, com calendário e
geometria pertencentes ao navegador/sistema operacional. Os dados gravados usam
ISO; a apresentação do sistema usa pt-BR e America/Sao_Paulo.

## Navegação de dados

Paginação no servidor: 25 pessoas por página, ordenação estável por nome,
sobrenome, usuário e chave. Nas listas de equipe e de acolhidos, busca e filtros são
confirmados por Enter ou Filtrar, sem pedidos assíncronos por tecla. A tela de
medicações é a exceção: a tabela se atualiza enquanto a pessoa digita, com pedido
ao servidor a cada 250 ms de pausa, trocando apenas a região `data-lista` e a
contagem; o filtro de situação envia sozinho e o botão Filtrar existe só dentro
de `noscript`. Falha de rede cai no envio normal do formulário. URL contém q, perfil, status e page; estes
parâmetros descrevem somente a lista de equipe administrativa. Limpar busca
submete imediatamente, preserva filtros e reinicia a página. Página fora do
intervalo é ajustada pelo servidor. Estado vazio oferece Limpar filtros.

## Fluxos

| Operação | Em andamento | Sucesso | Falha / recuperação |
|---|---|---|---|
| Entrar | botão bloqueado | painel ou destino interno; troca obrigatória prevalece | mensagem em português; senha não reapresentada |
| Criar usuário | botão bloqueado, geometria estável | lista com confirmação | campos preservados, erros associados e foco no primeiro inválido |
| Editar usuário | confirmar mudança de perfil/situação; botão bloqueado | lista com confirmação | campos preservados; bloqueio de autoexclusão e autorrebaixamento |
| Desativar | página de confirmação, POST com CSRF | lista, histórico preservado | acesso negado antes de consultar alvo |
| Alterar senha | botão bloqueado | painel, sessão atual preservada | validação do Django; senha nunca persistida no cliente |
| Cancelar / navegar | diálogo se houver alterações | lista ou destino escolhido | Continuar editando mantém formulário |

POSTs dependem de autorização de servidor. Formulários de gestão exigem actor
administrador e expõem apenas campos permitidos. Templates não renderizam ações
restritas. /admin/ é manutenção exclusiva de superusuário.

## Estados, acessibilidade e dispositivos

Feedback compartilhado no início do conteúdo, aria-live polite. Erros essenciais
permanecem no formulário. Senhas permitem colar, gerenciadores e revelar/ocultar.
Validação HTML nativa desativada; Django valida no envio. Campos têm labels reais,
aria-invalid e mensagens de ajuda/erro associadas. Não há alert/confirm/prompt.

Diálogos nativos modais prendem foco, tornam fundo inerte, fecham com Escape e
devolvem foco. A escolha segura recebe foco inicial. Confirmação de desativação
é página própria e funciona sem JavaScript. Menus móveis são disclosures não
modais, com aria-expanded e Escape. Links e botões têm foco e alvo de 44px.

403/404 oferecem retorno ao painel. 500 independe de contexto e banco.
Layouts são verificados em 320, 375, 414, 768 e desktop. Tabela larga rola dentro
do painel, preservando nomes e ações.

## Persistência e recuperação

Aplicação renderizada no servidor, mutações pessimistas. Não há autosave, filas
offline nem armazenamento de senhas ou dados pessoais em localStorage.
Submissão duplicada é bloqueada no cliente; unicidade de nome protege criação no
banco. Sessão expirada exige novo login; nunca reaplicar POST automaticamente.
Formulários alertam ao sair com alterações; nenhum rascunho sensível é persistido.
Falha de rede usa recuperação do navegador e retorno ao formulário; não há
garantia de preservação de senhas após navegação ou expiração. Edições simultâneas
de dados comuns seguem o último salvamento; perfis são lidos novamente a cada pedido.

## Doações — fase 3

| Componente | Responsável | Comportamento |
|---|---|---|
| Campos | components/fields.html + FormularioAcessivelMixin | erros associados e valores preservados |
| Listas | BaseListView + doacoes/partials/_pagination.html | 25 registros, filtros na URL, página ajustada |
| Busca de doador | doacoes.js + HTMX + BuscarDoadorView | mínimo 3 letras, 300 ms, cancelamento, IME, setas/Enter/Escape |
| Seleção de doador/tipo/campanha | select nativo | opção Anônimo; popup de responsabilidade do navegador |
| Recibo | doacoes/recibo.html + core/pdf.py | mesmo HTML para tela, impressão e PDF |

Na busca auxiliar de doador, texto é transitório e não vai para a URL da página;
selecionar uma sugestão atualiza o campo nativo. Falha de rede deixa a seleção
nativa disponível. Limpar cancela a requisição e mantém o doador já selecionado.
Nas listagens, Enter/Filtrar confirma a busca; limpar preserva os demais filtros.

Admin e Operacional cadastram doadores, registram/alteram doações e emitem recibos.
Técnico consulta as listas e o histórico do doador. Campanhas só são alteradas por
Admin. Permissões são verificadas em view, formulário e ações exibidas.
Não há exclusão pela interface; modelos preservam exclusão lógica.

Salvar e registrar outra mantém apenas data e doador. O envio bloqueia botões sem
perder a ação escolhida. Alterações de doação registram autor no histórico; quem
recebeu originalmente é preservado. Campanhas ficam ativas até o fim da data final.
Consultar/baixar recibo não altera estado. Marcar entregue exige POST com CSRF e é
idempotente. O renderizador PDF aceita somente CSS/fontes locais autorizados.

## Metas de campanhas

Uma campanha pode ter uma meta em reais e várias metas de itens. Cada meta de item
combina tipo de doação, quantidade inteira positiva e unidade compatível com o tipo; tipo e unidade não
podem se repetir na mesma campanha. O progresso financeiro soma apenas doações em
dinheiro. O progresso de item soma apenas quantidades de doações vinculadas à mesma
campanha com o mesmo tipo e unidade. Doações sem quantidade não aumentam a meta.
A tela mostra cada progresso separadamente e aceita metas de itens sem meta em reais.
A criação e a edição salvam campanha e metas na mesma transação. Metas financeiras
anteriores continuam no campo `meta_valor`.
No formulário, a meta em dinheiro fica na seção Metas e mostra apenas o valor em
reais. Metas de itens mostram tipo, quantidade e unidade. O botão Remover meta
aparece apenas quando há mais de uma meta visível; ao remover uma meta existente,
o formulário marca sua exclusão para o salvamento.
