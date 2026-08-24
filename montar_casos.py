"""Escreve dados/casos.json: os pares difíceis, rotulados à mão.

Cada caso aqui existe porque é uma armadilha que o gerador sintético não sabe
produzir — e que a base real produz toda semana. São eles que dizem se o método
funciona no mundo; o conjunto sintético só diz se ele aguenta escala.
"""

from __future__ import annotations

import json
from pathlib import Path

from base.documento import _dv, PESOS_CNPJ_1, PESOS_CNPJ_2


def cnpj(raiz: str, ordem: str = "0001") -> str:
    doze = raiz + ordem
    d1 = _dv(doze, PESOS_CNPJ_1)
    return doze + d1 + _dv(doze + d1, PESOS_CNPJ_2)


def cpf(nove: str) -> str:
    d = nove
    for _ in range(2):
        soma = sum(int(x) * (len(d) + 1 - i) for i, x in enumerate(d))
        resto = (soma * 10) % 11
        d += "0" if resto == 10 else str(resto)
    return d


A = cnpj("11222333")
B = cnpj("11222333", "0002")
C = cnpj("44555666")
D = cnpj("77888999")
E = cnpj("22333444")

CASOS = [
    # ---------------------------------------------------- deve achar
    dict(id="caso-01", rotulo="duplicata",
         descricao="Forma societária mudou de LTDA para ME. Mesmo CNPJ.",
         a=dict(nome="SILVA COMERCIO DE TINTAS LTDA", documento=A),
         b=dict(nome="Silva Comércio de Tintas ME", documento=A)),
    dict(id="caso-02", rotulo="duplicata",
         descricao="Segundo cadastro sem documento, feito por quem não achou o cliente.",
         a=dict(nome="OLIVEIRA MATERIAIS DE CONSTRUCAO LTDA", documento=C,
                telefone="(11) 3456-7890"),
         b=dict(nome="Oliveira Materiais de Construção", documento="",
                telefone="1134567890")),
    dict(id="caso-03", rotulo="duplicata",
         descricao="Nome truncado no campo de 30 caracteres do sistema antigo.",
         a=dict(nome="EMPREENDIMENTOS IMOBILIARIOS SANTOS E FILHOS LTDA", documento=D),
         b=dict(nome="EMPREENDIMENTOS IMOBILIARIOS S", documento="",
                email="contato@santos.com.br"),
         nota="Sem o e-mail em comum, este par não seria achado."),
    dict(id="caso-04", rotulo="duplicata",
         descricao="Abreviação: TRANSP contra TRANSPORTES.",
         a=dict(nome="TRANSP RAPIDO DO NORTE LTDA", documento="", telefone="8199887766"),
         b=dict(nome="TRANSPORTES RAPIDO DO NORTE", documento="", telefone="(81) 99887-766")),
    dict(id="caso-05", rotulo="duplicata",
         descricao="Celular gravado antes e depois do nono dígito.",
         a=dict(nome="PEREIRA SERVICOS", documento="", telefone="1187654321"),
         b=dict(nome="PEREIRA SERVIÇOS", documento="", telefone="11987654321")),
    dict(id="caso-06", rotulo="duplicata",
         descricao="Palavras do nome em ordem trocada.",
         a=dict(nome="COMERCIO DE PECAS ALMEIDA LTDA", documento="",
                email="vendas@almeida.com.br"),
         b=dict(nome="ALMEIDA COMERCIO DE PECAS", documento="",
                email="VENDAS@ALMEIDA.COM.BR")),
    dict(id="caso-07", rotulo="duplicata",
         descricao="Erro de digitação no CNPJ deixou o documento inválido.",
         a=dict(nome="FERREIRA DISTRIBUIDORA LTDA", documento=E),
         b=dict(nome="FERREIRA DISTRIBUIDORA LTDA", documento=E[:5] + "9" + E[6:]),
         nota="O documento do segundo não passa no dígito verificador."),
    dict(id="caso-08", rotulo="duplicata",
         descricao="Empresa trocou de razão social. Mesmo CNPJ, nome irreconhecível.",
         a=dict(nome="MARTINS E CIA LTDA", documento=cnpj("55666777")),
         b=dict(nome="GRUPO MR PARTICIPACOES S/A", documento=cnpj("55666777")),
         nota="Só o documento salva este par. Nenhuma comparação de nome pegaria."),
    dict(id="caso-09", rotulo="duplicata",
         descricao="Acentuação inconsistente entre os dois cadastros.",
         a=dict(nome="INDUSTRIA QUIMICA SAO JOAO", documento="", cep="04567000", numero="120"),
         b=dict(nome="Indústria Química São João", documento="", cep="04567-000", numero="120")),
    dict(id="caso-10", rotulo="duplicata",
         descricao="Pessoa física cadastrada duas vezes, com e sem CPF.",
         a=dict(nome="MARIA APARECIDA DE SOUZA", documento=cpf("123456789"),
                telefone="3199887766"),
         b=dict(nome="Maria Aparecida de Souza", documento="", telefone="31998877669"),
         nota="O telefone do segundo tem um dígito a mais, erro comum de digitação."),

    # ---------------------------------------------------- não pode achar
    dict(id="caso-11", rotulo="estabelecimentos",
         descricao="Matriz e filial. Mesma raiz, ordem diferente.",
         a=dict(nome="SILVA COMERCIO DE TINTAS LTDA", documento=A),
         b=dict(nome="SILVA COMERCIO DE TINTAS LTDA", documento=B),
         nota="O par mais caro de errar: fundir some com uma unidade do faturamento."),
    dict(id="caso-12", rotulo="distintos",
         descricao="Homônimos em cidades diferentes, CNPJs diferentes.",
         a=dict(nome="PADARIA PAO QUENTE LTDA", documento=cnpj("12345678"), cep="01310100"),
         b=dict(nome="PADARIA PAO QUENTE LTDA", documento=cnpj("87654321"), cep="80010000")),
    dict(id="caso-13", rotulo="distintos",
         descricao="Duas lojas da mesma marca, distinguidas por numeral.",
         a=dict(nome="OTICA VISAO", documento="", telefone="1133334444"),
         b=dict(nome="OTICA VISAO II", documento="", telefone="1133335555")),
    dict(id="caso-14", rotulo="distintos",
         descricao="Escritório compartilhado: mesmo CEP e número, empresas diferentes.",
         a=dict(nome="ALFA CONSULTORIA LTDA", documento=cnpj("13579246"),
                cep="04538133", numero="1000"),
         b=dict(nome="BETA ASSESSORIA LTDA", documento=cnpj("24681357"),
                cep="04538133", numero="1000"),
         nota="Endereço igual é evidência fraca em centro empresarial."),
    dict(id="caso-15", rotulo="distintos",
         descricao="E-mail genérico compartilhado pelo mesmo contador.",
         a=dict(nome="GOMES TRANSPORTES", documento=cnpj("19283746"),
                email="contabilidade@escritoriox.com.br"),
         b=dict(nome="ROCHA ALIMENTOS", documento=cnpj("46372819"),
                email="contabilidade@escritoriox.com.br")),
    dict(id="caso-16", rotulo="distintos",
         descricao="Sócio pessoa física e a empresa dele. Mesmo nome, documentos de tipos diferentes.",
         a=dict(nome="CARLOS EDUARDO BARBOSA", documento=cpf("987654321")),
         b=dict(nome="CARLOS EDUARDO BARBOSA", documento=cnpj("31415926"))),
    dict(id="caso-17", rotulo="distintos",
         descricao="Franquias diferentes com a mesma marca no nome.",
         a=dict(nome="FRANQUIA BOM SABOR MOEMA LTDA", documento=cnpj("11223344")),
         b=dict(nome="FRANQUIA BOM SABOR TATUAPE LTDA", documento=cnpj("44332211"))),
    dict(id="caso-18", rotulo="distintos",
         descricao="Pai e filho, nomes quase idênticos.",
         a=dict(nome="JOSE ANTONIO RIBEIRO", documento=cpf("111444777"),
                cep="30130010", numero="45"),
         b=dict(nome="JOSE ANTONIO RIBEIRO JUNIOR", documento="",
                cep="30130010", numero="45"),
         nota="Mesmo endereço, porque moram juntos. É o caso que mais engana."),
    dict(id="caso-19", rotulo="distintos",
         descricao="Duas filiais entre si, sem a matriz no par.",
         a=dict(nome="TEIXEIRA LOGISTICA LTDA", documento=cnpj("99887766", "0002")),
         b=dict(nome="TEIXEIRA LOGISTICA LTDA", documento=cnpj("99887766", "0003")),
         nota="Rotulado como distintos e não como estabelecimentos: são duas unidades, e o veredito correto é o mesmo — não fundir."),
    dict(id="caso-20", rotulo="distintos",
         descricao="Nomes parecidos, ramos e documentos diferentes.",
         a=dict(nome="COSTA COMERCIO DE MOVEIS", documento=cnpj("15975345")),
         b=dict(nome="COSTA COMERCIO DE MOTORES", documento=cnpj("34579515"))),
]

if __name__ == "__main__":
    destino = Path(__file__).parent / "dados" / "casos.json"
    # A quebra de linha no fim não é capricho: sem ela, qualquer editor que
    # respeite POSIX acrescenta uma ao salvar, e a conferência de
    # reprodutibilidade da integração contínua passa a falhar por um byte.
    destino.write_text(json.dumps(CASOS, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
    from collections import Counter
    print(f"{len(CASOS)} casos escritos em {destino.name}")
    for rotulo, n in sorted(Counter(c["rotulo"] for c in CASOS).items()):
        print(f"  {rotulo:<18} {n}")
