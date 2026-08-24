"""Mede o método contra linhas de base, nos dois conjuntos, separadamente.

O número sozinho não diz nada. Precisão de 0,9 é excelente contra uma linha de
base de 0,5 e é constrangedora contra uma de 0,89. Por isso tudo aqui é medido
contra o que a empresa já faz hoje sem ferramenta nenhuma:

  documento exato  — o que o ERP faz. Não acha nada sem CNPJ.
  nome exato       — o que o PROCV do Excel faz.
  nome normalizado — tirar acento e forma societária, e comparar.
  similaridade     — acusar todo par acima de um limiar de parecença.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from base.dominio import Registro
from base.pares import analisar, candidatos, pontuar
from base.texto import similaridade

RAIZ = Path(__file__).parent


def carregar_sintetico():
    """Gera a base se ela ainda não existe.

    Os dados não estão versionados de propósito: são saída determinística de
    `gerar_base.py`. O que precisa ser auditável é o gerador."""
    import csv
    if not (RAIZ / "dados" / "base_sintetica.csv").exists():
        from gerar_base import gerar, salvar
        registros, gab = gerar()
        salvar(registros, gab, RAIZ / "dados")
    with (RAIZ / "dados" / "base_sintetica.csv").open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    registros = [Registro(**{k: v for k, v in l.items()}) for l in linhas]
    gab = json.loads((RAIZ / "dados" / "gabarito_sintetico.json").read_text(encoding="utf-8"))
    return registros, {
        "duplicatas": {tuple(p) for p in gab["duplicatas"]},
        "estabelecimentos": {tuple(p) for p in gab["estabelecimentos"]},
    }


def carregar_casos():
    return json.loads((RAIZ / "dados" / "casos.json").read_text(encoding="utf-8"))


def metricas(vp: int, fp: int, fn: int) -> dict:
    precisao = vp / (vp + fp) if vp + fp else 0.0
    recall = vp / (vp + fn) if vp + fn else 0.0
    f1 = 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0
    return {"vp": vp, "fp": fp, "fn": fn,
            "precisao": precisao, "recall": recall, "f1": f1}


# ------------------------------------------------------------ linhas de base

def base_documento(a: Registro, b: Registro) -> bool:
    return bool(a.doc) and a.doc == b.doc


def base_nome_exato(a: Registro, b: Registro) -> bool:
    return a.nome.strip().upper() == b.nome.strip().upper()


def base_nome_normalizado(a: Registro, b: Registro) -> bool:
    return bool(a.nome_norm) and a.nome_norm == b.nome_norm


def base_similaridade(limiar: float):
    def f(a: Registro, b: Registro) -> bool:
        return similaridade(a.nome, b.nome) >= limiar
    return f


def avaliar_sintetico(registros, gabarito, decisor, limiar=None):
    """Um par só conta como acerto se for duplicata. Par matriz/filial marcado
    como duplicata é falso positivo — e é o falso positivo que custa caro."""
    verdadeiros = gabarito["duplicatas"]
    acusados = set()
    if decisor is None:
        for par in analisar(registros, limiar=limiar):
            if par.veredito == "duplicata":
                acusados.add(par.chave())
    else:
        for i, j in candidatos(registros):
            a, b = registros[i], registros[j]
            if decisor(a, b):
                acusados.add(tuple(sorted((a.id, b.id))))
    vp = len(acusados & verdadeiros)
    return metricas(vp, len(acusados) - vp, len(verdadeiros) - vp)


def avaliar_casos(decisor, limiar=None):
    vp = fp = fn = 0
    erros = []
    for caso in carregar_casos():
        a = Registro(id="A", **caso["a"])
        b = Registro(id="B", **caso["b"])
        deve = caso["rotulo"] == "duplicata"
        if decisor is None:
            par = pontuar(a, b)
            acusou = par.veredito == "duplicata" and par.confianca >= limiar
        else:
            acusou = decisor(a, b)
        if acusou and deve:
            vp += 1
        elif acusou and not deve:
            fp += 1
            erros.append((caso["id"], "falso alarme", caso["descricao"]))
        elif not acusou and deve:
            fn += 1
            erros.append((caso["id"], "escapou", caso["descricao"]))
    return metricas(vp, fp, fn), erros


def linha(nome, m):
    print(f"  {nome:<26} {m['precisao']:>8.3f} {m['recall']:>8.3f} {m['f1']:>8.3f}"
          f" {m['vp']:>5} {m['fp']:>5} {m['fn']:>5}")


def cabecalho(titulo):
    print(f"\n{titulo}")
    print(f"  {'método':<26} {'precisão':>8} {'recall':>8} {'F1':>8} {'VP':>5} {'FP':>5} {'FN':>5}")
    print("  " + "-" * 70)


def main():
    registros, gabarito = carregar_sintetico()
    print(f"BASE SINTÉTICA: {len(registros)} registros, "
          f"{len(gabarito['duplicatas'])} duplicatas, "
          f"{len(gabarito['estabelecimentos'])} pares matriz/filial")

    t0 = time.perf_counter()
    cand = candidatos(registros)
    t_blocagem = time.perf_counter() - t0
    total_possivel = len(registros) * (len(registros) - 1) // 2
    print(f"Blocagem: {len(cand)} pares comparados de {total_possivel} possíveis "
          f"({100 * len(cand) / total_possivel:.2f}%), em {t_blocagem:.2f}s")

    cabecalho("LINHAS DE BASE — conjunto sintético")
    linha("documento exato", avaliar_sintetico(registros, gabarito, base_documento))
    linha("nome exato", avaliar_sintetico(registros, gabarito, base_nome_exato))
    linha("nome normalizado", avaliar_sintetico(registros, gabarito, base_nome_normalizado))
    for lim in (0.80, 0.90, 0.95):
        linha(f"similaridade >= {lim:.2f}",
              avaliar_sintetico(registros, gabarito, base_similaridade(lim)))

    cabecalho("MÉTODO — conjunto sintético, por limiar")
    melhor, melhor_f1 = None, -1.0
    for lim in (0.50, 0.55, 0.58, 0.62, 0.68, 0.72, 0.80, 0.88):
        m = avaliar_sintetico(registros, gabarito, None, limiar=lim)
        linha(f"limiar {lim:.2f}", m)
        if m["f1"] > melhor_f1:
            melhor, melhor_f1 = lim, m["f1"]

    cabecalho("LINHAS DE BASE — casos difíceis escritos à mão")
    for nome, dec in [("documento exato", base_documento),
                      ("nome exato", base_nome_exato),
                      ("nome normalizado", base_nome_normalizado),
                      ("similaridade >= 0.90", base_similaridade(0.90))]:
        m, _ = avaliar_casos(dec)
        linha(nome, m)

    cabecalho("MÉTODO — casos difíceis, por limiar")
    for lim in (0.50, 0.55, 0.58, 0.62, 0.68, 0.72):
        m, _ = avaliar_casos(None, limiar=lim)
        linha(f"limiar {lim:.2f}", m)

    print(f"\nMELHOR LIMIAR NO SINTÉTICO: {melhor:.2f} (F1 {melhor_f1:.4f})")
    m_casos, erros = avaliar_casos(None, limiar=melhor)
    print(f"No conjunto difícil, com o mesmo limiar: "
          f"precisão {m_casos['precisao']:.3f}  recall {m_casos['recall']:.3f}  F1 {m_casos['f1']:.3f}")

    if erros:
        print("\nO QUE AINDA ERRA NOS CASOS DIFÍCEIS")
        for cid, tipo, desc in erros:
            print(f"  {cid}  {tipo:<13} {desc}")
    else:
        print("\nNenhum erro nos casos difíceis.")

    # Prova de que a regra dura não é decorativa, antes e depois da propagação.
    from base.higiene import analisar_base

    achados = analisar(registros, limiar=melhor)
    dup_sem = {p.chave() for p in achados if p.veredito == "duplicata"}
    fundidos_sem = dup_sem & gabarito["estabelecimentos"]

    res = analisar_base(registros, limiar=melhor)
    dup_com = {p.chave() for p in res.pares}
    fundidos_com = dup_com & gabarito["estabelecimentos"]

    print("\nMATRIZ E FILIAL — o par que não pode ser fundido")
    print(f"  pares matriz/filial no gabarito                 : {len(gabarito['estabelecimentos'])}")
    print(f"  fundidos por engano, só com a regra do CNPJ     : {len(fundidos_sem)}")
    print(f"  fundidos por engano, com a propagação por grupo : {len(fundidos_com)}")
    print(f"  fusões evitadas pela propagação                 : {res.protegidos}")

    m_com = metricas(len(dup_com & gabarito["duplicatas"]),
                     len(dup_com) - len(dup_com & gabarito["duplicatas"]),
                     len(gabarito["duplicatas"] - dup_com))
    cabecalho("MÉTODO COMPLETO — com propagação por grupo")
    linha(f"limiar {melhor:.2f}", m_com)

    r = res.resumo()
    print("\nO QUE O GESTOR RECEBE")
    print(f"  registros analisados          {r['registros']}")
    print(f"  pares comparados              {r['pares_comparados']} "
          f"({100 * r['pares_comparados'] / (r['registros'] * (r['registros'] - 1) / 2):.2f}% do total possível)")
    print(f"  grupos de duplicata           {r['grupos']}")
    print(f"  registros a eliminar          {r['registros_duplicados']} ({r['percentual_sujo']}% da base)")
    print(f"  pares de alta confiança       {r['pares_alta']}")
    print(f"  pares para conferir à mão     {r['pares_media']}")
    print(f"  unidades preservadas          {r['estabelecimentos']}")


if __name__ == "__main__":
    sys.exit(main())
