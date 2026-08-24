"""Gera uma base sintética de cadastro com o gabarito junto.

Por que sintética: base de cadastro real é dado pessoal, e não existe uma
pública com duplicatas rotuladas. Gerando eu mesmo a sujeira, sei exatamente
quais pares são duplicata — o gabarito sai de graça e sem erro de rotulagem.

Por que isso não basta: eu escolho a sujeira, então a medida diz o quanto o
método pega **do que eu imaginei**. Se a base real errar de um jeito que não
está aqui, o número de cima não vale. Por isso existe o segundo conjunto,
`dados/casos.json`, escrito à mão com os casos difíceis — e os dois resultados
são publicados separados, nunca somados.

Já publiquei um experimento com dados sintéticos que falhou, em outro projeto.
A lição que ficou foi esta: dado sintético serve para medir escala, não para
provar que funciona no mundo.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

from base.documento import _dv, PESOS_CNPJ_1, PESOS_CNPJ_2

RAMOS = ["COMERCIO", "INDUSTRIA", "SERVICOS", "TRANSPORTES", "DISTRIBUIDORA",
         "CONSTRUCOES", "TECNOLOGIA", "REPRESENTACOES", "EMPREENDIMENTOS"]
SOBRENOMES = ["SILVA", "SOUZA", "OLIVEIRA", "SANTOS", "PEREIRA", "LIMA", "COSTA",
              "FERREIRA", "ALMEIDA", "RIBEIRO", "CARVALHO", "GOMES", "MARTINS",
              "ROCHA", "BARBOSA", "AZEVEDO", "MOREIRA", "CARDOSO", "TEIXEIRA"]
PRODUTOS = ["TINTAS", "MATERIAIS", "ALIMENTOS", "PECAS", "EQUIPAMENTOS", "MOVEIS",
            "PRODUTOS", "FERRAMENTAS", "EMBALAGENS", "TEXTIL", "QUIMICA"]
FORMAS = ["LTDA", "ME", "EPP", "EIRELI", "S/A", ""]
ABREVIACOES = {"COMERCIO": "COM", "INDUSTRIA": "IND", "SERVICOS": "SERV",
               "TRANSPORTES": "TRANSP", "DISTRIBUIDORA": "DISTR",
               "CONSTRUCOES": "CONSTR", "TECNOLOGIA": "TEC",
               "REPRESENTACOES": "REPR", "EMPREENDIMENTOS": "EMPR",
               "MATERIAIS": "MAT", "EQUIPAMENTOS": "EQUIP", "PRODUTOS": "PROD"}
ACENTUADOS = {"COMERCIO": "COMÉRCIO", "INDUSTRIA": "INDÚSTRIA",
              "SERVICOS": "SERVIÇOS", "CONSTRUCOES": "CONSTRUÇÕES",
              "TEXTIL": "TÊXTIL", "QUIMICA": "QUÍMICA"}


def cnpj(rnd: random.Random, raiz: str | None = None, ordem: str = "0001") -> str:
    raiz = raiz or "".join(rnd.choice("0123456789") for _ in range(8))
    doze = raiz + ordem
    d1 = _dv(doze, PESOS_CNPJ_1)
    return doze + d1 + _dv(doze + d1, PESOS_CNPJ_2)


def nome_empresa(rnd: random.Random) -> str:
    partes = [rnd.choice(SOBRENOMES), rnd.choice(RAMOS)]
    if rnd.random() < 0.6:
        partes.append("DE " + rnd.choice(PRODUTOS))
    forma = rnd.choice(FORMAS)
    return " ".join(partes + ([forma] if forma else []))


def _erro_de_digitacao(rnd: random.Random, texto: str) -> str:
    if len(texto) < 6:
        return texto
    i = rnd.randrange(1, len(texto) - 2)
    modo = rnd.choice(["troca", "some", "dobra"])
    if modo == "troca":
        return texto[:i] + texto[i + 1] + texto[i] + texto[i + 2:]
    if modo == "some":
        return texto[:i] + texto[i + 1:]
    return texto[:i] + texto[i] + texto[i:]


def sujar(rnd: random.Random, original: dict) -> dict:
    """Cria uma segunda versão do mesmo cadastro, do jeito que a vida cria."""
    copia = dict(original)
    nome = copia["nome"]

    efeitos = rnd.sample(
        ["forma", "abreviar", "acento", "truncar", "digitar", "reordenar", "caixa"],
        k=rnd.randint(1, 3),
    )
    for efeito in efeitos:
        if efeito == "forma":
            for f in ("LTDA", "ME", "EPP", "EIRELI", "S/A"):
                nome = nome.replace(" " + f, "")
            nova = rnd.choice(FORMAS)
            nome = (nome + " " + nova).strip() if nova else nome
        elif efeito == "abreviar":
            for longo, curto in ABREVIACOES.items():
                if longo in nome and rnd.random() < 0.7:
                    nome = nome.replace(longo, curto)
        elif efeito == "acento":
            for sem, com in ACENTUADOS.items():
                nome = nome.replace(sem, com)
        elif efeito == "truncar":
            nome = nome[:30].strip()
        elif efeito == "digitar":
            nome = _erro_de_digitacao(rnd, nome)
        elif efeito == "reordenar":
            fichas = nome.split()
            if len(fichas) > 2:
                rnd.shuffle(fichas)
                nome = " ".join(fichas)
        elif efeito == "caixa":
            nome = nome.title()
    copia["nome"] = nome

    # O documento some em boa parte das duplicatas: é justamente por não achar
    # o cliente pelo CNPJ que o operador cadastra de novo.
    if rnd.random() < 0.45:
        copia["documento"] = ""
    elif rnd.random() < 0.3:
        d = copia["documento"]
        copia["documento"] = f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"

    if copia["telefone"] and rnd.random() < 0.5:
        d = copia["telefone"]
        copia["telefone"] = d if rnd.random() < 0.5 else f"({d[:2]}) {d[2:-4]}-{d[-4:]}"
    if rnd.random() < 0.3:
        copia["email"] = copia["email"].upper()
    if rnd.random() < 0.35:
        copia["telefone"] = ""
    if rnd.random() < 0.3:
        copia["email"] = ""
    if rnd.random() < 0.25:
        copia["cep"] = ""
    return copia


def gerar(semente: int = 42, empresas: int = 1200,
          fracao_duplicada: float = 0.18, fracao_com_filial: float = 0.12):
    """Devolve (registros, gabarito).

    gabarito["duplicatas"]      pares que são a mesma entidade
    gabarito["estabelecimentos"] pares da mesma empresa, unidades diferentes
    """
    rnd = random.Random(semente)
    registros: list[dict] = []
    duplicatas: set[tuple[str, str]] = set()
    estabelecimentos: set[tuple[str, str]] = set()
    proximo = 1

    for _ in range(empresas):
        raiz = "".join(rnd.choice("0123456789") for _ in range(8))
        nome = nome_empresa(rnd)
        ddd = rnd.choice(["11", "21", "31", "41", "51", "61", "71", "81"])
        base = {
            "id": f"C{proximo:05d}",
            "nome": nome,
            "documento": cnpj(rnd, raiz, "0001"),
            "email": f"contato@{nome.split()[0].lower()}{rnd.randint(1, 99)}.com.br",
            "telefone": ddd + str(rnd.randint(30000000, 99999999)),
            "cep": f"{rnd.randint(1000, 99999):05d}{rnd.randint(0, 999):03d}",
            "endereco": f"RUA {rnd.choice(SOBRENOMES)}",
            "numero": str(rnd.randint(1, 2000)),
        }
        proximo += 1
        registros.append(base)
        familia = [base]

        if rnd.random() < fracao_com_filial:
            for k in range(rnd.randint(1, 2)):
                filial = dict(base)
                filial["id"] = f"C{proximo:05d}"
                proximo += 1
                filial["documento"] = cnpj(rnd, raiz, f"{k + 2:04d}")
                filial["cep"] = f"{rnd.randint(1000, 99999):05d}{rnd.randint(0, 999):03d}"
                filial["numero"] = str(rnd.randint(1, 2000))
                filial["telefone"] = ddd + str(rnd.randint(30000000, 99999999))
                registros.append(filial)
                for irmao in familia:
                    estabelecimentos.add(tuple(sorted((irmao["id"], filial["id"]))))
                familia.append(filial)

        if rnd.random() < fracao_duplicada:
            origem = rnd.choice(familia)
            copia = sujar(rnd, origem)
            copia["id"] = f"C{proximo:05d}"
            proximo += 1
            registros.append(copia)
            duplicatas.add(tuple(sorted((origem["id"], copia["id"]))))
            # A duplicata herda a relação de estabelecimento dos irmãos da origem.
            for irmao in familia:
                if irmao["id"] == origem["id"]:
                    continue
                par = tuple(sorted((irmao["id"], copia["id"])))
                if tuple(sorted((irmao["id"], origem["id"]))) in estabelecimentos:
                    estabelecimentos.add(par)

    rnd.shuffle(registros)
    for i, r in enumerate(registros, start=2):
        r["linha"] = i
    gabarito = {
        "duplicatas": sorted(map(list, duplicatas)),
        "estabelecimentos": sorted(map(list, estabelecimentos)),
    }
    return registros, gabarito


COLUNAS = ["id", "nome", "documento", "email", "telefone", "cep", "endereco", "numero"]


def salvar(registros, gabarito, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    with (pasta / "base_sintetica.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, extrasaction="ignore")
        w.writeheader()
        w.writerows(registros)
    (pasta / "gabarito_sintetico.json").write_text(
        json.dumps(gabarito, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    semente = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    registros, gabarito = gerar(semente=semente)
    salvar(registros, gabarito, Path(__file__).parent / "dados")
    print(f"registros            {len(registros)}")
    print(f"duplicatas no gabarito {len(gabarito['duplicatas'])}")
    print(f"pares matriz/filial    {len(gabarito['estabelecimentos'])}")
