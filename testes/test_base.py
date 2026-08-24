"""Testes das teses do projeto, não da existência dos métodos.

Cada teste corresponde a uma afirmação do README. Se o README diz que matriz e
filial nunca são fundidas, existe um teste que tenta fundir.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from base.documento import (cnpj_valido, cpf_valido, mesma_empresa_outro_estabelecimento,
                            ordem, quase_igual, raiz)
from base.dominio import Registro, telefone_normalizado
from base.higiene import ConjuntosComVeto, analisar_base
from base.pares import candidatos, pontuar
from base.planilha import PlanilhaInvalida, ler
from base.texto import chave_ordenada, normalizar, similaridade


# ------------------------------------------------------------------ documento

def test_digito_verificador_de_cnpj():
    assert cnpj_valido("33.000.167/0001-01")
    assert not cnpj_valido("33.000.167/0001-02")
    assert not cnpj_valido("11111111111111")


def test_digito_verificador_de_cpf():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("529.982.247-26")
    assert not cpf_valido("00000000000")


def test_raiz_e_ordem_separam_a_empresa_do_estabelecimento():
    assert raiz("33.000.167/0002-83") == "33000167"
    assert ordem("33.000.167/0002-83") == "0002"


def test_matriz_e_filial_sao_reconhecidas_como_unidades():
    assert mesma_empresa_outro_estabelecimento("33000167000101", "33000167000283")
    assert not mesma_empresa_outro_estabelecimento("33000167000101", "33000167000101")


def test_digito_trocado_e_reconhecido():
    assert quase_igual("11222333000181", "11922333000181")
    assert not quase_igual("11222333000181", "44555666000199")


# ---------------------------------------------------------------------- texto

def test_forma_societaria_nao_distingue_empresa():
    assert normalizar("SILVA COMERCIO LTDA") == normalizar("Silva Comércio ME")


def test_abreviacao_equivale_ao_termo_inteiro():
    assert normalizar("TRANSP RAPIDO") == normalizar("TRANSPORTES RAPIDO")


def test_ordem_das_palavras_nao_muda_a_chave():
    assert chave_ordenada("COMERCIO DE TINTAS SILVA") == chave_ordenada("SILVA COMERCIO DE TINTAS")


def test_nomes_de_empresas_diferentes_nao_colidem():
    assert similaridade("SILVA COMERCIO", "SOUZA COMERCIO") < 0.85


def test_telefone_absorve_o_nono_digito():
    assert telefone_normalizado("1187654321") == telefone_normalizado("11987654321")


# ------------------------------------------------------------------ pontuação

def test_mesmo_documento_encerra_a_discussao():
    a = Registro(id="1", nome="MARTINS E CIA LTDA", documento="33000167000101")
    b = Registro(id="2", nome="GRUPO MR PARTICIPACOES", documento="33.000.167/0001-01")
    par = pontuar(a, b)
    assert par.confianca == 1.0
    assert par.veredito == "duplicata"


def test_documentos_validos_e_diferentes_nao_sao_duplicata():
    a = Registro(id="1", nome="PADARIA PAO QUENTE", documento="33000167000101")
    b = Registro(id="2", nome="PADARIA PAO QUENTE", documento="11222333000181")
    assert pontuar(a, b).confianca == 0.0


def test_matriz_e_filial_nunca_viram_duplicata():
    """A tese central. Fundir estas duas some com uma unidade do faturamento."""
    a = Registro(id="1", nome="SILVA COMERCIO LTDA", documento="33000167000101")
    b = Registro(id="2", nome="SILVA COMERCIO LTDA", documento="33000167000283")
    par = pontuar(a, b)
    assert par.veredito == "estabelecimentos"


def test_marcador_de_unidade_derruba_o_par():
    """'OTICA VISAO' e 'OTICA VISAO II' têm 0,97 de similaridade e são duas lojas."""
    a = Registro(id="1", nome="OTICA VISAO", telefone="1133334444")
    b = Registro(id="2", nome="OTICA VISAO II", telefone="1133335555")
    assert pontuar(a, b).confianca < 0.62


def test_motivo_e_sempre_conferivel_por_humano():
    a = Registro(id="1", nome="SOUZA MATERIAIS", email="c@souza.com.br")
    b = Registro(id="2", nome="SOUZA MAT LTDA", email="C@SOUZA.COM.BR")
    par = pontuar(a, b)
    assert par.motivos
    assert all(isinstance(m, str) and len(m) > 3 for m in par.motivos)


# ------------------------------------------------------------------- blocagem

def test_blocagem_nao_compara_todo_mundo_com_todo_mundo():
    regs = [Registro(id=str(i), nome=f"EMPRESA {i} COMERCIO") for i in range(200)]
    total = len(regs) * (len(regs) - 1) // 2
    assert len(candidatos(regs)) < total * 0.2


# --------------------------------------------------------------- agrupamento

def test_veto_impede_uniao_indireta():
    c = ConjuntosComVeto()
    for x in "abc":
        c.achar(x)
    c.vetar("a", "b")
    assert c.unir("b", "c")
    assert not c.unir("a", "c"), "o veto entre a e b tem de alcançar c"


def test_copia_suja_nao_entra_no_grupo_da_filial():
    """Regressão: a primeira versão fundiu 12 pares matriz/filial por este
    caminho — agrupava antes de aplicar a separação."""
    regs = [
        Registro(id="matriz", nome="FERREIRA CONSTRUCOES SA", documento="33000167000101",
                 telefone="1133330000"),
        Registro(id="filial", nome="FERREIRA CONSTRUCOES SA", documento="33000167000283",
                 telefone="1144440000"),
        Registro(id="copia", nome="Ferreira Construções S/A", documento="",
                 telefone="1144440000"),
    ]
    res = analisar_base(regs)
    fundidos = {p.chave() for p in res.pares}
    assert ("filial", "matriz") not in fundidos
    assert ("copia", "matriz") not in fundidos


def test_grupo_fecha_por_transitividade():
    regs = [
        Registro(id="1", nome="ALFA COMERCIO LTDA", documento="33000167000101"),
        Registro(id="2", nome="ALFA COMERCIO ME", documento="33000167000101"),
        Registro(id="3", nome="Alfa Comercio", documento="33.000.167/0001-01"),
    ]
    res = analisar_base(regs)
    assert len(res.grupos) == 1
    assert res.grupos[0].ids == ["1", "2", "3"]


# -------------------------------------------------------------------- leitura

def test_le_a_planilha_com_o_vocabulario_da_operacao():
    texto = ("Codigo;Razao Social;CNPJ;E-mail\n"
             "A1;SILVA COMERCIO LTDA;33.000.167/0001-01;a@b.com\n"
             "A2;Silva Comércio ME;33000167000101;a@b.com\n")
    regs = ler(texto)
    assert len(regs) == 2
    assert regs[0].id == "A1"
    assert regs[0].doc_valido


def test_coluna_a_mais_e_ignorada():
    texto = ("nome,cnpj,centro_de_custo\n"
             "ALFA LTDA,33000167000101,CC-1\n"
             "ALFA ME,33000167000101,CC-2\n")
    assert len(ler(texto)) == 2


@pytest.mark.parametrize("texto,trecho", [
    ("", "vazio"),
    ("cidade,estado\nSP,SP\n", "coluna do nome"),
    ("nome\n", "nenhuma linha"),
    ("nome\nALFA\n", "uma linha só"),
])
def test_erro_fala_com_quem_montou_a_planilha(texto, trecho):
    with pytest.raises(PlanilhaInvalida, match=trecho):
        ler(texto)


# ------------------------------------------------------- gabarito e resultado

def _casos():
    return json.loads((RAIZ / "dados" / "casos.json").read_text(encoding="utf-8"))


def test_conjunto_dificil_tem_as_duas_classes():
    casos = _casos()
    assert sum(1 for c in casos if c["rotulo"] == "duplicata") >= 8
    assert sum(1 for c in casos if c["rotulo"] != "duplicata") >= 8


def test_nenhum_falso_alarme_nos_casos_dificeis():
    """O número que o README publica: precisão 1,00 no conjunto escrito à mão.

    Falso positivo aqui significa fundir dois clientes reais — erro que apaga
    dado e não tem volta. É a métrica que manda neste projeto."""
    alarmes = []
    for caso in _casos():
        if caso["rotulo"] == "duplicata":
            continue
        par = pontuar(Registro(id="A", **caso["a"]), Registro(id="B", **caso["b"]))
        if par.veredito == "duplicata" and par.confianca >= 0.80:
            alarmes.append(caso["id"])
    assert alarmes == []


def test_supera_a_linha_de_base_do_documento_exato():
    """'Documento exato' tem precisão 1,00 e recall 0,20 nos casos difíceis.
    O método precisa ganhar disso sem perder a precisão."""
    vp = fp = fn = 0
    for caso in _casos():
        deve = caso["rotulo"] == "duplicata"
        par = pontuar(Registro(id="A", **caso["a"]), Registro(id="B", **caso["b"]))
        achou = par.veredito == "duplicata" and par.confianca >= 0.80
        vp += achou and deve
        fp += achou and not deve
        fn += (not achou) and deve
    assert fp == 0
    assert vp / (vp + fn) > 0.20
