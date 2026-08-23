"""Normalização e similaridade de nomes, sem dependência externa.

A ausência de dependência não é purismo: é a decisão que permite este mesmo
código rodar dentro do navegador do cliente, sem que a base de clientes dele
saia da máquina. Base de cadastro é dado pessoal; pedir para alguém subir isso
num servidor de terceiro só para testar uma ferramenta seria o oposto do que
este projeto defende.
"""

from __future__ import annotations

import re
import unicodedata

# Sufixos e marcadores societários. Não identificam a empresa — identificam o
# tipo dela. "SILVA LTDA" e "SILVA ME" podem ser a mesma empresa que mudou de
# enquadramento, e é exatamente esse par que a comparação exata perde.
FORMAS_SOCIETARIAS = {
    "LTDA", "LIMITADA", "ME", "MEI", "EPP", "EIRELI", "SA", "S/A",
    "EI", "CIA", "COMPANHIA", "SS", "SLU", "S", "A",
}

# Abreviações que aparecem dos dois jeitos na mesma base.
EQUIVALENTES = {
    "COM": "COMERCIO", "COML": "COMERCIO", "CO": "COMERCIO",
    "IND": "INDUSTRIA", "INDL": "INDUSTRIA",
    "SERV": "SERVICOS", "SERVS": "SERVICOS", "SERVICO": "SERVICOS",
    "DISTR": "DISTRIBUIDORA", "DIST": "DISTRIBUIDORA",
    "REPR": "REPRESENTACOES", "REP": "REPRESENTACOES",
    "TRANSP": "TRANSPORTES", "TRANSPORTE": "TRANSPORTES",
    "CONSTR": "CONSTRUCOES", "CONST": "CONSTRUCOES",
    "EMPR": "EMPREENDIMENTOS", "EMPREEND": "EMPREENDIMENTOS",
    "PART": "PARTICIPACOES", "PARTIC": "PARTICIPACOES",
    "TEC": "TECNOLOGIA", "TECN": "TECNOLOGIA",
    "ADM": "ADMINISTRACAO", "ASSESS": "ASSESSORIA",
    "MAT": "MATERIAIS", "EQUIP": "EQUIPAMENTOS",
    "PROD": "PRODUTOS", "IMP": "IMPORTACAO", "EXP": "EXPORTACAO",
}

# Conectivos que não distinguem nada.
VAZIAS = {"DE", "DA", "DO", "DAS", "DOS", "E", "EM", "A", "O", "AS", "OS"}


def sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


def fichas(nome: str) -> list[str]:
    """Quebra o nome em partes comparáveis, já limpas."""
    bruto = sem_acento(nome or "").upper()
    bruto = re.sub(r"[^A-Z0-9 ]+", " ", bruto)
    partes = []
    for parte in bruto.split():
        if parte in FORMAS_SOCIETARIAS or parte in VAZIAS:
            continue
        partes.append(EQUIVALENTES.get(parte, parte))
    return partes


def normalizar(nome: str) -> str:
    return " ".join(fichas(nome))


def chave_ordenada(nome: str) -> str:
    """Nome com as partes em ordem alfabética.

    Resolve o caso em que a mesma empresa foi cadastrada como
    'COMERCIO DE TINTAS SILVA' e 'SILVA COMERCIO DE TINTAS'.
    """
    return " ".join(sorted(fichas(nome)))


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    alcance = max(len(a), len(b)) // 2 - 1
    if alcance < 0:
        alcance = 0
    marca_a = [False] * len(a)
    marca_b = [False] * len(b)
    comuns = 0
    for i, ca in enumerate(a):
        inicio = max(0, i - alcance)
        fim = min(len(b), i + alcance + 1)
        for j in range(inicio, fim):
            if marca_b[j] or b[j] != ca:
                continue
            marca_a[i] = marca_b[j] = True
            comuns += 1
            break
    if comuns == 0:
        return 0.0
    trocas = 0
    j = 0
    for i, ca in enumerate(a):
        if not marca_a[i]:
            continue
        while not marca_b[j]:
            j += 1
        if ca != b[j]:
            trocas += 1
        j += 1
    trocas //= 2
    return (comuns / len(a) + comuns / len(b) + (comuns - trocas) / comuns) / 3


def jaro_winkler(a: str, b: str, escala: float = 0.1) -> float:
    """Favorece nomes que começam igual — que é como erro de digitação se
    comporta em cadastro: quase sempre no meio ou no fim, raramente no início."""
    base = jaro(a, b)
    prefixo = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefixo += 1
    return base + prefixo * escala * (1 - base)


def jaccard(a: str, b: str) -> float:
    """Sobreposição de partes. Insensível à ordem, ao contrário do Jaro."""
    fa, fb = set(a.split()), set(b.split())
    if not fa or not fb:
        return 0.0
    return len(fa & fb) / len(fa | fb)


def similaridade(nome_a: str, nome_b: str) -> float:
    """Combina os dois: o maior entre caractere a caractere e parte a parte.

    Usar o maior, e não a média, é deliberado. Os dois erram em situações
    diferentes — o Jaro perde reordenação, o Jaccard perde digitação — e o par
    só precisa ser pego por um deles.
    """
    a, b = normalizar(nome_a), normalizar(nome_b)
    if not a or not b:
        return 0.0
    return max(jaro_winkler(a, b), jaccard(a, b))
