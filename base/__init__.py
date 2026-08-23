"""base-limpa — encontra registros repetidos em cadastro, sem fundir matriz com filial."""

from .dominio import Par, Registro
from .higiene import Grupo, Resultado, analisar_base
from .pares import analisar, faixa, pontuar
from .planilha import PlanilhaInvalida, escrever_pares, ler

__all__ = ["Registro", "Par", "Grupo", "Resultado", "analisar_base",
           "analisar", "pontuar", "faixa", "ler", "escrever_pares", "PlanilhaInvalida"]
