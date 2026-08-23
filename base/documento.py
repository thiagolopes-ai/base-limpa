"""CPF e CNPJ: validação, raiz e estabelecimento.

Este módulo carrega a regra que separa este projeto de uma comparação de texto
qualquer. Duas linhas com o mesmo CNPJ raiz **não são** necessariamente a mesma
empresa: podem ser matriz e filial, que são estabelecimentos distintos, com
inscrição estadual própria, faturamento próprio e contrato próprio.

Fundir matriz com filial é o erro mais caro que um deduplicador pode cometer,
porque não gera relatório sujo — gera cliente desaparecido. E some em silêncio:
ninguém percebe que o número caiu, só que a filial parou de ser faturada.

Formato do CNPJ: RR.RRR.RRR/OOOO-DD
  raiz  = 8 primeiros dígitos, identificam a pessoa jurídica
  ordem = 4 seguintes, identificam o estabelecimento (0001 = matriz)
  dv    = 2 últimos, dígitos verificadores
"""

from __future__ import annotations

import re

SO_DIGITOS = re.compile(r"\D")

PESOS_CNPJ_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
PESOS_CNPJ_2 = (6,) + PESOS_CNPJ_1


def apenas_digitos(valor: str) -> str:
    return SO_DIGITOS.sub("", valor or "")


def _dv(digitos: str, pesos: tuple[int, ...]) -> str:
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(valor: str) -> bool:
    """Confere os dois dígitos verificadores.

    Documento inválido na base é achado por si só: costuma ser digitação, e é
    exatamente onde as duplicatas se escondem, porque o ERP não bloqueou.
    """
    d = apenas_digitos(valor)
    if len(d) != 14 or d == d[0] * 14:
        return False
    return d[12] == _dv(d[:12], PESOS_CNPJ_1) and d[13] == _dv(d[:13], PESOS_CNPJ_2)


def cpf_valido(valor: str) -> bool:
    d = apenas_digitos(valor)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = (soma * 10) % 11
        esperado = 0 if resto == 10 else resto
        if int(d[tamanho]) != esperado:
            return False
    return True


def documento_valido(valor: str) -> bool:
    d = apenas_digitos(valor)
    if len(d) == 14:
        return cnpj_valido(d)
    if len(d) == 11:
        return cpf_valido(d)
    return False


def raiz(valor: str) -> str:
    """Os 8 dígitos que identificam a pessoa jurídica. Vazio se não for CNPJ."""
    d = apenas_digitos(valor)
    return d[:8] if len(d) == 14 else ""


def ordem(valor: str) -> str:
    """Os 4 dígitos do estabelecimento. '0001' é a matriz."""
    d = apenas_digitos(valor)
    return d[8:12] if len(d) == 14 else ""


def mesma_empresa_outro_estabelecimento(a: str, b: str) -> bool:
    """Mesma raiz, ordem diferente — matriz e filial, ou duas filiais.

    É a regra que impede a fusão indevida. Existe como função própria, e com
    teste próprio, porque é a que não pode falhar em silêncio.
    """
    ra, rb = raiz(a), raiz(b)
    if not ra or ra != rb:
        return False
    return ordem(a) != ordem(b)


def formatar(valor: str) -> str:
    d = apenas_digitos(valor)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return valor


def quase_igual(a: str, b: str) -> bool:
    """Dois documentos do mesmo tamanho que diferem em um dígito, ou por troca
    de dois dígitos vizinhos.

    Existe porque o erro de digitação no CNPJ é o modo mais comum de nascer uma
    duplicata: o operador digita errado, o sistema não valida o dígito
    verificador, e o cliente entra de novo. Quando o nome bate, a diferença de
    um dígito é evidência a favor do par, não contra.
    """
    da, db = apenas_digitos(a), apenas_digitos(b)
    if len(da) != len(db) or len(da) not in (11, 14) or da == db:
        return False
    difs = [i for i, (x, y) in enumerate(zip(da, db)) if x != y]
    if len(difs) == 1:
        return True
    if len(difs) == 2 and difs[1] == difs[0] + 1:
        i = difs[0]
        return da[i] == db[i + 1] and da[i + 1] == db[i]
    return False
