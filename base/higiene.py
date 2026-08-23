"""A camada de cima: agrupa, propaga e protege matriz de filial.

Pontuar par a par não basta. Se A e B são a mesma empresa, e B e C também, então
A e C são a mesma empresa mesmo que o par A-C nunca tenha sido comparado — é a
transitividade que fecha o grupo.

E ela protege: se A é duplicata de B, e B é matriz de C, então A também é outra
unidade em relação a C. Sem essa propagação, a cópia suja de uma matriz aparece
como duplicata da filial, e a fusão apaga uma unidade inteira do faturamento.
Foi exatamente isso que a primeira versão fez em 12 pares, e é a razão de este
módulo existir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .dominio import Par, Registro
from .pares import ALTA, LIMIAR_PADRAO, analisar, faixa


class ConjuntosComVeto:
    """União-busca que sabe recusar uma união.

    Um deduplicador comum só junta. Este precisa saber **não** juntar: matriz e
    filial compartilham nome, endereço e às vezes telefone, e a única coisa que
    as separa é uma regra de negócio que o algoritmo tem de carregar como veto,
    não como pontuação.

    O veto é transitivo dos dois lados. Se A não pode juntar com B, e C já está
    junto de B, então A também não junta com C. É isso que impede a cópia suja
    da matriz de entrar no grupo da filial por um caminho indireto.
    """

    def __init__(self) -> None:
        self.pai: dict[str, str] = {}
        self.inimigos: dict[str, set[str]] = {}

    def achar(self, x: str) -> str:
        self.pai.setdefault(x, x)
        self.inimigos.setdefault(x, set())
        while self.pai[x] != x:
            self.pai[x] = self.pai[self.pai[x]]
            x = self.pai[x]
        return x

    def vetar(self, a: str, b: str) -> None:
        ra, rb = self.achar(a), self.achar(b)
        if ra == rb:
            return
        self.inimigos[ra].add(rb)
        self.inimigos[rb].add(ra)

    def pode_unir(self, a: str, b: str) -> bool:
        ra, rb = self.achar(a), self.achar(b)
        return ra == rb or rb not in self.inimigos[ra]

    def unir(self, a: str, b: str) -> bool:
        """Une e devolve True; devolve False se houver veto entre os grupos."""
        ra, rb = self.achar(a), self.achar(b)
        if ra == rb:
            return True
        if rb in self.inimigos[ra]:
            return False
        self.pai[rb] = ra
        # O grupo que some transfere seus vetos para quem o absorveu.
        for inimigo in self.inimigos.pop(rb, set()):
            raiz_inimiga = self.achar(inimigo)
            if raiz_inimiga == ra:
                continue
            self.inimigos[ra].add(raiz_inimiga)
            self.inimigos.setdefault(raiz_inimiga, set()).discard(rb)
            self.inimigos[raiz_inimiga].add(ra)
        return True


@dataclass
class Grupo:
    """Registros que são a mesma entidade."""
    ids: list[str]
    confianca_minima: float
    motivos: list[str] = field(default_factory=list)


@dataclass
class Resultado:
    grupos: list[Grupo]
    pares: list[Par]
    estabelecimentos: list[Par]
    registros_analisados: int
    pares_comparados: int
    protegidos: int = 0

    @property
    def registros_duplicados(self) -> int:
        return sum(len(g.ids) - 1 for g in self.grupos)

    def resumo(self) -> dict:
        por_faixa: dict[str, int] = {"alta": 0, "média": 0}
        for p in self.pares:
            f = faixa(p.confianca)
            if f in por_faixa:
                por_faixa[f] += 1
        return {
            "registros": self.registros_analisados,
            "pares_comparados": self.pares_comparados,
            "grupos": len(self.grupos),
            "registros_duplicados": self.registros_duplicados,
            "percentual_sujo": round(100 * self.registros_duplicados / max(1, self.registros_analisados), 2),
            "pares_alta": por_faixa["alta"],
            "pares_media": por_faixa["média"],
            "estabelecimentos": len(self.estabelecimentos),
            "fusoes_evitadas": self.protegidos,
        }


def analisar_base(registros: list[Registro], limiar: float = LIMIAR_PADRAO,
                  limiar_grupo: float = ALTA) -> Resultado:
    """Analisa a base inteira.

    `limiar`       — a partir de onde o par entra na lista de conferência
    `limiar_grupo` — a partir de onde o par é agrupado como mesma entidade
    """
    todos = analisar(registros, limiar=limiar)
    duplicatas = [p for p in todos if p.veredito == "duplicata"]
    estabelecimentos = [p for p in todos if p.veredito == "estabelecimentos"]

    conj = ConjuntosComVeto()
    for r in registros:
        conj.achar(r.id)

    # Os vetos entram primeiro. Depois deles, nenhuma união consegue passar por
    # cima — que era o furo da primeira versão: ela agrupava e só então tentava
    # separar, e o próprio agrupamento já tinha apagado a informação.
    for p in estabelecimentos:
        conj.vetar(p.a.id, p.b.id)

    # Da maior confiança para a menor. Quando o mesmo registro sem documento
    # poderia entrar em dois grupos vetados entre si, ele fica com o que tem
    # mais evidência a favor.
    protegidos = 0
    finais: list[Par] = []
    for p in sorted(duplicatas, key=lambda x: -x.confianca):
        if p.confianca >= limiar_grupo:
            if not conj.unir(p.a.id, p.b.id):
                p.veredito = "estabelecimentos"
                p.motivos.append("grupo econômico com unidades distintas")
                estabelecimentos.append(p)
                protegidos += 1
                continue
        elif not conj.pode_unir(p.a.id, p.b.id):
            p.veredito = "estabelecimentos"
            p.motivos.append("grupo econômico com unidades distintas")
            estabelecimentos.append(p)
            protegidos += 1
            continue
        finais.append(p)

    familias: dict[str, list[str]] = {}
    for r in registros:
        familias.setdefault(conj.achar(r.id), []).append(r.id)

    grupos = []
    for raiz, ids in familias.items():
        if len(ids) < 2:
            continue
        relevantes = [p for p in finais
                      if conj.achar(p.a.id) == raiz and p.confianca >= limiar_grupo]
        motivos = sorted({m for p in relevantes for m in p.motivos})
        grupos.append(Grupo(
            ids=sorted(ids),
            confianca_minima=min((p.confianca for p in relevantes), default=1.0),
            motivos=motivos,
        ))
    grupos.sort(key=lambda g: (-len(g.ids), g.ids[0]))

    from .pares import candidatos
    return Resultado(
        grupos=grupos,
        pares=sorted(finais, key=lambda p: (-p.confianca, p.a.id, p.b.id)),
        estabelecimentos=estabelecimentos,
        registros_analisados=len(registros),
        pares_comparados=len(candidatos(registros)),
        protegidos=protegidos,
    )
