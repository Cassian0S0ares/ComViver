"""Numeros agregados dos acolhidos, para a tela de estatisticas.

Nenhum nome sai daqui: so contagens por grupo. Mesmo assim o resumo inclui
saude e tempo de acolhimento, e por isso a tela fica com a equipe tecnica.
"""

from collections import Counter
from datetime import date

from acolhidos.models import Destino, Medicacao, Sexo, TipoSanguineo

# Criança até 12 anos e adolescente de 12 a 18 (ECA, art. 2º). O acolhimento
# pode se estender até os 21 anos.
FAIXAS_ETARIAS = [
    ("0 a 8 anos", 0, 8),
    ("9 a 12 anos", 9, 12),
    ("13 a 15 anos", 13, 15),
    ("16 a 17 anos", 16, 17),
    ("18 anos ou mais", 18, None),
]

# O ECA fixa 18 meses como prazo maximo do acolhimento (art. 19, § 2º).
FAIXAS_PERMANENCIA = [
    ("Até 6 meses", 0, 6),
    ("7 a 12 meses", 7, 12),
    ("13 a 18 meses", 13, 18),
    ("Mais de 18 meses", 19, None),
]

def _linhas(rotulos_e_totais, total):
    """Linhas prontas para o template, com a porcentagem sobre o total."""
    maior = max((quantidade for _, quantidade in rotulos_e_totais), default=0)
    return [
        {
            "rotulo": rotulo,
            "quantidade": quantidade,
            "porcentagem": round(100 * quantidade / total) if total else 0,
            "largura": round(100 * quantidade / maior) if maior else 0,
        }
        for rotulo, quantidade in rotulos_e_totais
    ]


def _por_faixa(valores, faixas):
    contagem = Counter()
    for valor in valores:
        for rotulo, minimo, maximo in faixas:
            if valor >= minimo and (maximo is None or valor <= maximo):
                contagem[rotulo] += 1
                break
    return [(rotulo, contagem[rotulo]) for rotulo, _, _ in faixas]


def _meses_entre(inicio: date, fim: date) -> int:
    return (fim.year - inicio.year) * 12 + fim.month - inicio.month - (fim.day < inicio.day)


def _alergias(acolhidos):
    """Conta cada alergia uma vez por acolhido, sem diferenciar maiusculas.

    O rotulo e a grafia mais usada; no empate, a que comeca com maiuscula.
    """
    contagem, grafias = Counter(), {}
    sem_alergia = 0
    for acolhido in acolhidos:
        saude = getattr(acolhido, "saude", None)
        itens = {}
        for linha in (saude.alergias if saude else "").splitlines():
            item = " ".join(linha.split())
            # "Nenhuma", "Nenhuma conhecida": a pessoa registrou que nao ha.
            if item and not item.casefold().startswith("nenhum"):
                itens.setdefault(item.casefold(), item)
        if not itens:
            sem_alergia += 1
        for chave, item in itens.items():
            contagem[chave] += 1
            grafias.setdefault(chave, Counter())[item] += 1

    def rotulo(chave):
        return max(grafias[chave].items(), key=lambda par: (par[1], par[0][0].isupper(), par[0]))[0]

    linhas = sorted(contagem.items(), key=lambda par: (-par[1], par[0]))
    return [(rotulo(chave), quantidade) for chave, quantidade in linhas], sem_alergia


def calcular(acolhidos, hoje: date | None = None) -> dict:
    """Resumo agregado de um conjunto de acolhidos (queryset ou lista)."""
    hoje = hoje or date.today()
    acolhidos = list(acolhidos)
    total = len(acolhidos)
    fichas = [a.ficha for a in acolhidos if getattr(a, "ficha", None)]

    idades = [a.idade for a in acolhidos]
    sexo = Counter(a.sexo for a in acolhidos)
    anos_entrada = Counter(f.data_entrada.year for f in fichas)
    permanencias = [_meses_entre(f.data_entrada, f.data_desligamento or hoje) for f in fichas]
    alergias, sem_alergia = _alergias(acolhidos)
    com_alergia = total - sem_alergia

    tipos = Counter(
        a.saude.tipo_sanguineo
        for a in acolhidos
        if getattr(a, "saude", None) and a.saude.tipo_sanguineo in TipoSanguineo.values
    )
    sem_tipo = total - sum(tipos.values())
    naturalidades = Counter(a.naturalidade.strip() or "Não informada" for a in acolhidos)
    destinos = Counter(f.destino for f in fichas if f.data_desligamento and f.destino)

    com_medicacao = (
        Medicacao.em_vigor.filter(acolhido__in=[a.pk for a in acolhidos])
        .values("acolhido")
        .distinct()
        .count()
    )

    return {
        "total": total,
        "idade_media": round(sum(idades) / total, 1) if total else None,
        "permanencia_media": (
            round(sum(permanencias) / len(permanencias)) if permanencias else None
        ),
        "com_alergia": com_alergia,
        "com_medicacao": com_medicacao,
        "faixas_etarias": _linhas(_por_faixa(idades, FAIXAS_ETARIAS), total),
        "sexo": _linhas([(rotulo, sexo[valor]) for valor, rotulo in Sexo.choices], total),
        "anos_entrada": _linhas(sorted(anos_entrada.items()), len(fichas)),
        "sem_ficha": total - len(fichas),
        "permanencia": _linhas(_por_faixa(permanencias, FAIXAS_PERMANENCIA), len(fichas)),
        "alergias": _linhas(alergias, total),
        "sem_alergia": sem_alergia,
        "tipos_sanguineos": _linhas(
            [
                *[(valor, tipos[valor]) for valor in TipoSanguineo.values if tipos[valor]],
                *([("Não informado", sem_tipo)] if sem_tipo else []),
            ],
            total,
        ),
        "naturalidades": _linhas(naturalidades.most_common(), total),
        "destinos": _linhas(
            [(rotulo, destinos[valor]) for valor, rotulo in Destino.choices if destinos[valor]],
            sum(destinos.values()),
        ),
    }
