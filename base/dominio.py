"""O registro de cadastro e a normalização dos campos de contato."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .documento import apenas_digitos, documento_valido, ordem, raiz
from .texto import chave_ordenada, normalizar, sem_acento

# Sufixos que marcam estabelecimento diferente, não erro de digitação.
# "PADARIA PAO QUENTE" e "PADARIA PAO QUENTE II" têm similaridade de 0,97 e são
# duas lojas. Fundir as duas é perder uma delas do faturamento.
DISTINTIVOS = re.compile(
    r"\b(I{1,3}|IV|V|VI{0,3}|[0-9]{1,2}|JR|JUNIOR|FILIAL|UNIDADE|LOJA|MATRIZ)\b"
)


@dataclass(frozen=True)
class Registro:
    id: str
    nome: str
    documento: str = ""
    email: str = ""
    telefone: str = ""
    cep: str = ""
    endereco: str = ""
    numero: str = ""
    linha: int = 0

    @property
    def doc(self) -> str:
        return apenas_digitos(self.documento)

    @property
    def doc_valido(self) -> bool:
        return documento_valido(self.documento)

    @property
    def raiz(self) -> str:
        return raiz(self.documento)

    @property
    def ordem(self) -> str:
        return ordem(self.documento)

    @property
    def nome_norm(self) -> str:
        return normalizar(self.nome)

    @property
    def nome_chave(self) -> str:
        return chave_ordenada(self.nome)

    @property
    def fone(self) -> str:
        return telefone_normalizado(self.telefone)

    @property
    def mail(self) -> str:
        return (self.email or "").strip().lower()

    @property
    def cep_norm(self) -> str:
        d = apenas_digitos(self.cep)
        return d if len(d) == 8 else ""

    @property
    def endereco_norm(self) -> str:
        base = sem_acento(self.endereco or "").upper()
        base = re.sub(r"[^A-Z0-9 ]+", " ", base)
        base = re.sub(r"\b(RUA|R|AV|AVENIDA|AL|ALAMEDA|TRAV|TRAVESSA|PCA|PRACA|ROD|RODOVIA)\b", " ", base)
        return " ".join(base.split())

    @property
    def num_norm(self) -> str:
        return apenas_digitos(self.numero)

    @property
    def distintivos(self) -> frozenset[str]:
        """Marcadores de unidade encontrados no nome."""
        return frozenset(DISTINTIVOS.findall(normalizar(self.nome)))


def telefone_normalizado(valor: str) -> str:
    """Reduz o telefone à forma comparável.

    Metade das bases brasileiras tem celular gravado antes da migração para
    nove dígitos e a outra metade depois. Comparar a string inteira perde o par;
    comparar DDD mais os oito dígitos finais resolve, e é o que o operador de
    telefonia faz.
    """
    d = apenas_digitos(valor)
    if d.startswith("55") and len(d) > 11:
        d = d[2:]
    d = d.lstrip("0")
    if len(d) < 10:
        return ""
    # Onze dígitos com o nono na frente é celular novo; dez é fixo ou celular
    # antigo. Comparar DDD mais os oito finais cobre os dois, e ainda absorve o
    # dígito digitado a mais no fim, que é erro corriqueiro de teclado.
    if len(d) > 11:
        d = d[:11]
    return d[:2] + d[-8:]


@dataclass
class Par:
    """Dois registros que podem ser a mesma entidade, e por quê."""
    a: Registro
    b: Registro
    confianca: float
    motivos: list[str] = field(default_factory=list)
    veredito: str = "duplicata"  # ou "estabelecimentos"

    def chave(self) -> tuple[str, str]:
        return tuple(sorted((self.a.id, self.b.id)))  # type: ignore[return-value]
