---
version: alpha
name: ComViver
description: Um espaço de trabalho acolhedor para a equipe do Lar Padre José Gumercindo.
colors:
  primary: "oklch(34% .052 238)"
  ink: "oklch(30% .035 240)"
  muted: "oklch(49% .029 240)"
  paper: "oklch(97% .008 240)"
  surface: "oklch(99.5% .002 240)"
  accent: "oklch(79% .069 165)"
  danger: "oklch(44% .15 23)"
  success: "oklch(40% .075 165)"
typography:
  display:
    fontFamily: "Manrope, Segoe UI, sans-serif"
  body:
    fontFamily: "Source Sans 3, Segoe UI, sans-serif"
rounded:
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
spacing:
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
components:
  button:
    rounded: "0.5rem"
    backgroundColor: "{colors.primary}"
  surface:
    rounded: "0.75rem"
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
  caption:
    textColor: "{colors.muted}"
  page:
    backgroundColor: "{colors.paper}"
  brand:
    textColor: "{colors.accent}"
  danger:
    textColor: "{colors.danger}"
  success:
    textColor: "{colors.success}"
---

# Identidade visual ComViver

## Overview

O ponto de partida é a porta de uma casa de acolhimento: um lugar de encontro,
com rotinas claras e pessoas reconhecidas pelo nome. Dois arcos sobrepostos
formam a assinatura da marca. Eles aparecem no símbolo, no acesso e na abertura
do painel, sem ocupar formulários ou competir com dados.

Público: coordenação, equipe técnica e equipe operacional da instituição.
Registro: produto administrativo brasileiro em pt-BR, usado diariamente em
computadores compartilhados e eventualmente no celular. O projeto foi criado
a partir da fase 1; os HTMLs ilustrativos do plano não são referências visuais.

Fonte canônica dos valores: `static/css/tokens.css`. Este documento espelha os
papéis principais. `comviver.css` importa os tokens; Bootstrap recebe as
adaptações de componentes no mesmo arquivo. `tokens.css` na raiz é um ponto de
entrada portátil, sem duplicação de valores. Verificação: `scripts/check_design.py`.

## Colors

Azul profundo estrutura navegação e ações principais. Verde água representa o
encontro na marca; não substitui a cor semântica de sucesso. O fundo azul muito
claro diferencia a área de trabalho das superfícies. Texto secundário tem
contraste suficiente para leitura, inclusive em formulários. Vermelho é
reservado a erros e desativação. Perfis têm rótulos escritos além das cores.
Tema claro único; cores forçadas seguem o sistema operacional.

## Typography

Manrope dá personalidade à marca e aos títulos. Source Sans 3 mantém formulários
e tabelas legíveis, com formas abertas e boa diferenciação de caracteres.
Fontes variáveis são hospedadas localmente, com preload. Corpo de 16px, títulos
de página de 32px (27px no celular), legendas entre 12px e 14px. Títulos não usam
itálico. Nomes completos podem quebrar linha; ações têm texto curto.

## Layout

Navegação de 248px; cabeçalho de 88px; conteúdo até 1440px. Ritmo de 4px com
espaçamentos de 8, 16, 24, 32, 40, 48 e 64px. Abaixo de 700px, menu expansível
no fluxo do documento, sem sobrepor conteúdo nem prender foco. Tabela tem sua
própria rolagem horizontal; formulários usam a rolagem natural da página.
Login em duas colunas, com a expressão de marca à esquerda e formulário à direita.

## Elevation & Depth

Hierarquia por cores de superfície e bordas finas. Sem sombras em cartões
estáticos. Diálogos usam a camada superior nativa com fundo escurecido. Não há
gradientes, cartões decorativos nem indicadores com números inventados.

## Shapes

Controles com raio de 8px, superfícies de 12px, abertura de painel de 16px.
Arcos exclusivos da marca; avatares circulares apenas para iniciais. Ícones
Bootstrap Icons, hospedados localmente, acompanhados por rótulo ou nome acessível.

## Components

Tokens `--color-*`, `--font-*`, `--space-*` e `--radius-*` são consumidos por
`.button`, `.surface`, `.field`, `.notice`, `.users-table` e pela navegação.
`templates/components/fields.html` e `FormularioAcessivelMixin` possuem os campos;
`messages.html` possui feedback; `comviver.js` possui interações compartilhadas.

Botões têm altura mínima de 44px e estados hover, foco visível instantâneo,
pressionado, desabilitado e ocupado. Erros incluem texto associado ao campo.
Sucesso é anunciado no retorno à listagem. Inputs mantêm a espessura da borda.
Senhas são mascaradas e permitem revelação. Selects são nativos: interação e
geometria do popup pertencem ao navegador, com opções em português.

Movimento reduzido: sem animação ornamental. Nenhuma transição de layout.
Scrollbars globais têm track, thumb, hover e active definidos nos tokens.

## Do's and Don'ts

- Usar apenas números reais e mostrar estados vazios com orientação.
- Reutilizar componentes e vocabulário: Criar usuário, Salvar alterações, Desativar acesso.
- Não exibir módulos futuros como links operáveis.
- Não usar fotos de crianças, selos de confiança inventados ou dados sensíveis como decoração.
- Não trocar a identidade ao acrescentar os módulos das fases seguintes.

## Aplicação na fase 3

Doações, doadores e campanhas reutilizam a navegação, superfícies, campos,
tabelas e feedback existentes. Menta destaca o vínculo de apoio; os totais têm
algarismos tabulares. Nenhuma soma mistura dinheiro, itens e serviços.
O cadastro rápido tem uma coluna de orientação e mantém doador/data no próximo
registro. No celular, os blocos se empilham e a tabela rola dentro da superfície.

Os recibos têm variante A4 com as mesmas fontes, azul e menta, convertidos para
cores sRGB em `static/css/recibo.css` para compatibilidade com impressão/PDF.
A variante elimina a navegação da folha impressa. CNPJ e endereço institucionais
só serão apresentados quando forem informados; não há dados fictícios no recibo.
