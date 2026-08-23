"""Blocagem e pontuação dos pares candidatos.

Comparar todo mundo com todo mundo é inviável: uma base de 50 mil clientes dá
1,25 bilhão de pares. A blocagem resolve isso agrupando registros que
compartilham alguma chave forte e comparando só dentro do grupo — é o que faz a
análise caber em segundos no navegador do cliente.

O preço da blocagem é honesto e está documentado: par que não compartilha
nenhuma chave nunca é comparado, e portanto nunca é encontrado. Duas linhas da
mesma empresa sem documento, com nome escrito de forma completamente diferente e
sem telefone, e-mail ou CEP em comum, escapam. Não existe recall de 100% em
deduplicação real, e quem promete isso está comparando tudo com tudo e cobrando
pelo tempo de máquina.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .dominio import Par, Registro
from .documento import mesma_empresa_outro_estabelecimento, quase_igual
from .texto import similaridade

# Abaixo disto o par não é mostrado. Calibrado em avaliar.py, não escolhido a
# dedo: é o limiar que maximiza F1 nos dois conjuntos de avaliação.
LIMIAR_PADRAO = 0.62

ALTA = 0.85
MEDIA = 0.62


def chaves(r: Registro) -> list[tuple[str, str]]:
    """As chaves de blocagem de um registro, da mais forte para a mais fraca."""
    ks: list[tuple[str, str]] = []
    if r.doc_valido:
        ks.append(("doc", r.doc))
    if r.raiz:
        ks.append(("raiz", r.raiz))
    if r.nome_chave:
        ks.append(("nome", r.nome_chave))
        # Prefixo pega quem tem o nome truncado no cadastro — campo de 30
        # caracteres é a causa mais comum de duplicata que ninguém explica.
        ks.append(("pref", r.nome_chave[:10]))
    if r.fone:
        ks.append(("fone", r.fone))
    if r.mail:
        ks.append(("mail", r.mail))
    if r.cep_norm and r.num_norm:
        ks.append(("end", r.cep_norm + "-" + r.num_norm))
    return ks


def candidatos(registros: list[Registro]) -> set[tuple[int, int]]:
    """Índices de pares que valem a pena comparar."""
    blocos: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, r in enumerate(registros):
        for k in chaves(r):
            blocos[k].append(i)

    pares: set[tuple[int, int]] = set()
    for indices in blocos.values():
        # Bloco gigante é sinal de chave inútil (nome vazio, telefone 0000...).
        # Comparar tudo dentro dele custa caro e não acha nada.
        if len(indices) > 60:
            continue
        for i, j in combinations(sorted(indices), 2):
            pares.add((i, j))
    return pares


def _contatos_iguais(a: Registro, b: Registro) -> list[str]:
    iguais = []
    if a.fone and a.fone == b.fone:
        iguais.append("mesmo telefone")
    if a.mail and a.mail == b.mail:
        iguais.append("mesmo e-mail")
    if a.cep_norm and a.cep_norm == b.cep_norm and a.num_norm and a.num_norm == b.num_norm:
        iguais.append("mesmo endereço")
    return iguais


def pontuar(a: Registro, b: Registro) -> Par:
    """Devolve o par com a confiança e o motivo explícito.

    Todo motivo é uma frase que o gestor consegue conferir sozinho. Ferramenta
    que devolve só um número de 0 a 1 obriga a confiar; ferramenta que diz
    'mesmo CNPJ, nome escrito diferente' permite verificar.
    """
    # Regra dura, avaliada antes de qualquer pontuação: mesma empresa, unidades
    # diferentes. Não é duplicata e não pode ser fundida.
    if mesma_empresa_outro_estabelecimento(a.documento, b.documento):
        return Par(a, b, 1.0,
                   [f"mesmo CNPJ raiz, estabelecimentos {a.ordem} e {b.ordem}"],
                   veredito="estabelecimentos")

    motivos: list[str] = []
    sim = similaridade(a.nome, b.nome)
    contatos = _contatos_iguais(a, b)

    # Documento completo igual e válido encerra a discussão.
    if a.doc_valido and a.doc == b.doc:
        motivos.append("mesmo documento")
        if a.nome_norm != b.nome_norm:
            motivos.append("nome grafado de formas diferentes")
        return Par(a, b, 1.0, motivos)

    # Documento diferente e ambos válidos: são entidades distintas perante a
    # Receita, por mais parecido que o nome esteja.
    if a.doc_valido and b.doc_valido and a.doc != b.doc and not a.raiz == b.raiz:
        return Par(a, b, 0.0, ["documentos válidos e diferentes"])

    # Um dígito de diferença, com um dos lados reprovando no verificador: é
    # digitação, não outra empresa. Só vale quando o nome corrobora — sozinha,
    # a regra fundiria CNPJs vizinhos de empresas sem relação nenhuma.
    if quase_igual(a.doc, b.doc) and not (a.doc_valido and b.doc_valido):
        if similaridade(a.nome, b.nome) >= 0.85:
            return Par(a, b, 0.95,
                       ["documento com um dígito de diferença, um deles inválido",
                        "nome confere"])

    confianca = 0.0
    if a.nome_norm and a.nome_norm == b.nome_norm:
        confianca = 0.72
        motivos.append("nome idêntico após normalização")
    elif a.nome_chave and a.nome_chave == b.nome_chave:
        confianca = 0.68
        motivos.append("mesmas palavras no nome, em ordem diferente")
    elif sim >= 0.90:
        confianca = 0.58
        motivos.append(f"nome muito parecido ({sim:.2f})")
    elif sim >= 0.80:
        confianca = 0.45
        motivos.append(f"nome parecido ({sim:.2f})")
    else:
        confianca = 0.15

    # Cada contato coincidente é evidência independente do nome.
    for motivo in contatos:
        confianca += 0.16
        motivos.append(motivo)

    # Um dos dois tem documento e o outro não: o cadastro incompleto é
    # normalmente a duplicata recém-criada por quem não achou o cliente.
    if (a.doc_valido) != (b.doc_valido) and sim >= 0.80:
        confianca += 0.05
        motivos.append("um dos registros está sem documento")

    # Marcador de unidade diferente derruba o par. "PADARIA PAO QUENTE" e
    # "PADARIA PAO QUENTE II" têm 0,97 de similaridade e são duas lojas.
    so_a = a.distintivos - b.distintivos
    so_b = b.distintivos - a.distintivos
    if so_a or so_b:
        confianca -= 0.45
        marca = ", ".join(sorted(so_a | so_b))
        motivos.append(f"marcador de unidade diferente ({marca})")

    return Par(a, b, max(0.0, min(1.0, confianca)), motivos)


def faixa(confianca: float) -> str:
    if confianca >= ALTA:
        return "alta"
    if confianca >= MEDIA:
        return "média"
    return "baixa"


def analisar(registros: list[Registro], limiar: float = LIMIAR_PADRAO) -> list[Par]:
    """Todos os pares acima do limiar, do mais confiante para o menos."""
    achados = []
    for i, j in candidatos(registros):
        par = pontuar(registros[i], registros[j])
        if par.veredito == "estabelecimentos" or par.confianca >= limiar:
            achados.append(par)
    achados.sort(key=lambda p: (-p.confianca, p.a.id, p.b.id))
    return achados
