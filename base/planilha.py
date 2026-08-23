"""Lê o CSV que o gestor exportou, com o vocabulário que ele já usa.

Ninguém vai reformatar uma planilha de dez mil linhas para testar uma
ferramenta. Então os apelidos de coluna são generosos e as colunas a mais são
ignoradas em silêncio.
"""

from __future__ import annotations

import csv
import io

from .dominio import Registro

APELIDOS: dict[str, tuple[str, ...]] = {
    "id": ("id", "codigo", "código", "cod", "matricula", "matrícula", "chave"),
    "nome": ("nome", "razao_social", "razão_social", "razao social", "razão social",
             "cliente", "fornecedor", "empresa", "nome_fantasia", "descricao",
             "razaosocial", "nome fantasia"),
    "documento": ("documento", "cnpj", "cpf", "cpf_cnpj", "cnpj_cpf", "doc",
                  "cpfcnpj", "cnpjcpf", "inscricao", "inscrição"),
    "email": ("email", "e-mail", "e_mail", "mail", "correio"),
    "telefone": ("telefone", "fone", "celular", "tel", "contato", "whatsapp"),
    "cep": ("cep", "codigo_postal", "código postal"),
    "endereco": ("endereco", "endereço", "logradouro", "rua", "end"),
    "numero": ("numero", "número", "num", "nr", "n"),
}


class PlanilhaInvalida(ValueError):
    """Erro escrito para quem montou a planilha, não para quem lê o código."""


def _mapear(cabecalho: list[str]) -> dict[str, str]:
    encontrado: dict[str, str] = {}
    normal = {c: (c or "").strip().lower().replace("-", "_") for c in cabecalho}
    for campo, opcoes in APELIDOS.items():
        for coluna, chave in normal.items():
            if chave in opcoes and campo not in encontrado:
                encontrado[campo] = coluna
    return encontrado


def _separador(texto: str) -> str:
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    return ";" if primeira.count(";") > primeira.count(",") else ","


def ler(texto: str) -> list[Registro]:
    texto = (texto or "").strip()
    if not texto:
        raise PlanilhaInvalida("arquivo vazio")

    leitor = csv.DictReader(io.StringIO(texto), delimiter=_separador(texto))
    if not leitor.fieldnames:
        raise PlanilhaInvalida("não encontrei o cabeçalho")

    mapa = _mapear(list(leitor.fieldnames))
    if "nome" not in mapa:
        vistas = ", ".join(c for c in leitor.fieldnames if c)
        raise PlanilhaInvalida(
            "não achei a coluna do nome. Aceito: nome, razao_social, cliente, "
            f"fornecedor ou empresa. Encontrei: {vistas}"
        )

    registros: list[Registro] = []
    for numero, bruta in enumerate(leitor, start=2):
        valores = {campo: (bruta.get(coluna) or "").strip()
                   for campo, coluna in mapa.items()}
        if not any(valores.values()):
            continue
        if not valores.get("id"):
            valores["id"] = f"L{numero}"
        valores["linha"] = numero  # type: ignore[assignment]
        registros.append(Registro(**valores))  # type: ignore[arg-type]

    if not registros:
        raise PlanilhaInvalida("nenhuma linha de dados além do cabeçalho")
    if len(registros) < 2:
        raise PlanilhaInvalida("uma linha só não tem par para comparar")
    return registros


def escrever_pares(resultado) -> str:
    """Exporta a lista de conferência no formato que volta para o sistema."""
    saida = io.StringIO()
    w = csv.writer(saida)
    w.writerow(["veredito", "confianca", "id_a", "nome_a", "doc_a",
                "id_b", "nome_b", "doc_b", "motivos"])
    for p in resultado.pares + resultado.estabelecimentos:
        w.writerow([p.veredito, f"{p.confianca:.2f}",
                    p.a.id, p.a.nome, p.a.documento,
                    p.b.id, p.b.nome, p.b.documento,
                    "; ".join(p.motivos)])
    return saida.getvalue()
