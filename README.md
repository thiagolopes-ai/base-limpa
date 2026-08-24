# base-limpa

Encontra registros repetidos em base de cadastro — e recusa fundir matriz com filial.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Sem dependência](https://img.shields.io/badge/depend%C3%AAncias-nenhuma-success?style=flat-square)
![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green?style=flat-square)

**[▶ Abrir no navegador](https://thiagolopes-ai.github.io/base-limpa/)** — cole a sua base e receba os pares repetidos com o motivo ao lado. O arquivo não sai da sua máquina.

---

## O problema

Toda empresa com mais de mil clientes tem a mesma base suja. "João Silva ME", "Joao Silva M.E.", "J SILVA MEI" e "SILVA, JOAO — MATRIZ" são a mesma pessoa em quatro linhas.

O efeito não é estético:

- cobrança emitida duas vezes para o mesmo CNPJ
- limite de crédito calculado sobre um pedaço do histórico
- mala direta paga quatro vezes para o mesmo destinatário
- relatório de faturamento apresentado ao conselho com o número inflado

Ninguém contrata para arrumar isso porque ninguém sabe o tamanho do problema. É invisível até alguém medir.

E há um segundo problema, mais caro, que aparece justamente em quem tenta resolver o primeiro.

## O erro que o deduplicador comum comete

CNPJ tem estrutura: `RR.RRR.RRR/OOOO-DD`. Os oito primeiros dígitos são a **raiz** e identificam a pessoa jurídica. Os quatro seguintes são a **ordem** e identificam o estabelecimento — `0001` é a matriz, `0002` em diante são as filiais.

Matriz e filial compartilham nome, quase sempre o endereço de cobrança e às vezes o telefone. Para qualquer comparação de texto, são a mesma empresa. **Não são.** Cada uma tem inscrição estadual própria, faturamento próprio e contrato próprio.

Fundir as duas não produz relatório sujo. Produz cliente desaparecido — e some em silêncio, porque ninguém percebe que o número caiu, só que a filial parou de ser faturada.

Este projeto trata essa separação como **veto**, não como pontuação. Nenhuma quantidade de similaridade consegue passar por cima dela.

---

## O que ele mede

Dois conjuntos de avaliação, medidos e publicados **separados**. Somar os dois esconderia justamente o que cada um revela.

### Conjunto sintético — 1.638 registros, 207 duplicatas, 340 pares matriz/filial

| Método | Precisão | Recall | F1 |
|---|---|---|---|
| **base-limpa (limiar 0,80)** | **0,990** | **0,947** | **0,968** |
| linha de base: documento exato | 1,000 | 0,546 | 0,706 |
| linha de base: nome normalizado | 0,057 | 0,483 | 0,102 |
| linha de base: nome exato | 0,056 | 0,140 | 0,080 |
| linha de base: similaridade ≥ 0,95 | 0,090 | 0,918 | 0,164 |

**Por que a linha de base importa.** "Documento exato" é o que o ERP já faz sozinho: precisão perfeita e recall de 0,546 — perde metade, porque metade das duplicatas nasce justamente de um cadastro sem CNPJ. "Similaridade de nome" é o que se faz quando se resolve atacar o problema sem pensar: recall alto e precisão de 0,09, ou seja, onze falsos alarmes para cada acerto. É contra esses dois que a ferramenta precisa valer a pena.

### Conjunto difícil — 20 pares escritos e rotulados à mão

| Método | Precisão | Recall | F1 |
|---|---|---|---|
| **base-limpa (limiar 0,80)** | **1,000** | 0,800 | 0,889 |
| linha de base: nome normalizado | 0,636 | 0,700 | 0,667 |
| linha de base: similaridade ≥ 0,90 | 0,529 | 0,900 | 0,667 |
| linha de base: documento exato | 1,000 | 0,200 | 0,333 |

São as armadilhas que o gerador sintético não sabe produzir: homônimos em cidades diferentes, escritório compartilhado com o mesmo CEP e número, e-mail do contador repetido em dois clientes, pai e filho no mesmo endereço, sócio pessoa física e a empresa dele com o mesmo nome.

**Precisão de 1,000 é a métrica que manda aqui.** Falso negativo deixa o problema como estava. Falso positivo funde dois clientes reais, apaga dado e não tem volta.

### O efeito do veto, isolado

| | Fusões indevidas de matriz e filial | Precisão | F1 |
|---|---|---|---|
| Só com a regra do CNPJ | 12 | 0,933 | 0,940 |
| **Com propagação por grupo** | **0** | **0,990** | **0,968** |

A regra do CNPJ sozinha não bastava, e o motivo é interessante: quando a cópia suja perde o documento, ela entra no grupo pelo nome, e o grupo carrega junto a matriz — a filial acaba fundida por um caminho indireto, sem que nenhum par matriz-filial tenha sido comparado diretamente.

A correção foi inverter a ordem: **o veto entra antes do agrupamento e vira restrição dele**, não um filtro aplicado depois. A primeira versão agrupava e só então tentava separar, e o próprio agrupamento já tinha apagado a informação necessária.

O ganho não foi só de segurança. A precisão subiu de 0,933 para 0,990.

Reproduza com `python avaliar.py`.

---

## O que ele ainda erra

Dois dos vinte casos difíceis escapam no limiar recomendado:

**Nome truncado no campo de 30 caracteres.** "EMPREENDIMENTOS IMOBILIARIOS SANTOS E FILHOS LTDA" contra "EMPREENDIMENTOS IMOBILIARIOS S". Sem um e-mail ou telefone em comum, este par não é achado — e não deveria ser, porque o prefixo sozinho também casaria com qualquer outra imobiliária de nome parecido.

**Telefone com um dígito digitado a mais.** `31 99887766` e `31 998877669`. A segunda forma é indistinguível de um celular válido de nove dígitos. Uma regra que tratasse as duas como iguais criaria falsos positivos em toda base com celular novo. Preferi perder o par.

Os dois são achados no limiar 0,62, que é o padrão da lista de conferência — só não entram na faixa de alta confiança, que é a que pode ser fundida sem olho humano.

### E há uma tensão entre os dois conjuntos

O limiar que maximiza F1 no sintético (0,80) não é o que maximiza no conjunto difícil (0,62, com F1 1,000). Não é contradição: o conjunto sintético tem 1.638 registros que compartilham sobrenomes, e por isso pune limiar baixo com falso alarme; o conjunto difícil são vinte pares isolados, sem esse ruído.

A escolha foi assumir os dois limiares, com papéis diferentes:

- **0,62** — entra na lista de conferência. Recall alto, para o humano decidir.
- **0,80** — entra na faixa de alta confiança, que pode ser fundida.

A ferramenta **não funde nada**. Ela devolve uma lista com o motivo ao lado, e a decisão fica com quem responde pelo cadastro.

---

## Como funciona

**Blocagem.** Comparar todo mundo com todo mundo é inviável: 50 mil clientes dão 1,25 bilhão de pares. Registros são agrupados por chaves fortes — documento, raiz do CNPJ, nome normalizado, prefixo do nome, telefone, e-mail, CEP com número — e a comparação acontece dentro do grupo. No conjunto sintético isso reduz de 1.340.703 pares para 7.525, **0,56% do total**, em menos de um décimo de segundo.

O preço está documentado: par que não compartilha nenhuma chave nunca é comparado, e portanto nunca é achado. Não existe recall de 100% em deduplicação real. Quem promete isso está comparando tudo com tudo e cobrando pelo tempo de máquina.

**Normalização com vocabulário brasileiro.** LTDA, ME, EPP, EIRELI e S/A não identificam a empresa — identificam o enquadramento dela, que muda. COM/COMÉRCIO, TRANSP/TRANSPORTES, IND/INDÚSTRIA são a mesma palavra escrita por operadores diferentes. Acento entra e sai. Ordem de palavras troca.

**Pontuação por evidência, com o motivo explícito.** Cada par vem com uma frase que o gestor confere sozinho: "mesmo documento", "mesmo telefone", "nome idêntico após normalização", "documento com um dígito de diferença, um deles inválido". Ferramenta que devolve só um número de 0 a 1 obriga a confiar. Ferramenta que diz o porquê permite verificar.

**Marcador de unidade derruba o par.** "ÓTICA VISÃO" e "ÓTICA VISÃO II" têm 0,97 de similaridade e são duas lojas. Numerais, algarismos romanos e as palavras FILIAL, UNIDADE, LOJA e JÚNIOR entram como sinal de separação.

**Dígito verificador.** CPF e CNPJ são validados. Documento inválido na base é achado por si só — e é exatamente onde as duplicatas se escondem, porque o sistema não bloqueou a digitação errada. Quando o nome corrobora, um dígito de diferença é evidência **a favor** do par.

---

## A base não sai da máquina de quem usa

A página carrega o Python no navegador via Pyodide e roda a análise ali dentro. Nada é enviado para servidor nenhum.

Isso não é enfeite. Base de cadastro é dado pessoal na definição da LGPD; pedir para um gestor subir a carteira de clientes dele para um servidor de terceiro só para "testar uma ferramenta" seria o oposto do que este projeto defende.

E não há reimplementação. Os arquivos que rodam no navegador são exatamente `base/documento.py`, `texto.py`, `dominio.py`, `pares.py`, `higiene.py` e `planilha.py` — os mesmos que passam nos 28 testes. Nenhum deles tem dependência externa, e isso não é sorte: é a decisão de projeto que torna a página possível. Uma versão em JavaScript acabaria divergindo do motor testado em três meses, e ninguém perceberia.

---

## Por que a base sintética não basta

O gerador cria a sujeira, então o gabarito sai de graça e sem erro de rotulagem. Só que **eu escolho a sujeira** — a medida diz o quanto o método pega do que eu imaginei, não do que a base real faz.

Já publiquei, em outro projeto, um experimento com dados sintéticos que falhou. A lição que ficou está aplicada aqui: dado sintético serve para medir escala, não para provar que funciona no mundo. Por isso existem os vinte casos escritos à mão, e por isso os dois resultados aparecem separados.

A base sintética não está versionada: é saída determinística do gerador, e o que precisa ser auditável é o gerador, não a saída dele. A integração contínua prova o determinismo gerando duas vezes e comparando o hash. Os vinte casos escritos à mão, esses sim, estão versionados — foram digitados, não gerados.

---

## Como executar

```bash
git clone https://github.com/thiagolopes-ai/base-limpa.git
cd base-limpa
pip install -r requirements.txt

python gerar_base.py              # gera a base sintética e o gabarito
python montar_casos.py            # regenera os casos difíceis
python avaliar.py                 # reproduz todas as tabelas acima
python -m pytest testes/ -q       # 28 testes
```

### Usando como biblioteca

```python
from base import ler, analisar_base

registros = ler(open("clientes.csv", encoding="utf-8").read())
resultado = analisar_base(registros)

print(resultado.resumo())
# {'registros': 1638, 'grupos': 192, 'registros_duplicados': 194,
#  'percentual_sujo': 11.84, 'fusoes_evitadas': 12, ...}

for par in resultado.pares:
    print(par.confianca, par.a.nome, "|", par.b.nome, "|", "; ".join(par.motivos))
```

### O formato de entrada

Só `nome` é obrigatória. Cada coluna a mais vira evidência independente.

| Campo | Também aceito como |
|---|---|
| `nome` | razao_social, cliente, fornecedor, empresa, nome_fantasia |
| `documento` | cnpj, cpf, cpf_cnpj, doc, inscricao |
| `email` | e-mail, mail |
| `telefone` | fone, celular, contato, whatsapp |
| `cep`, `numero`, `endereco`, `id` | codigo, logradouro, num |

Separador vírgula ou ponto e vírgula. Colunas a mais são ignoradas em silêncio, porque planilha de operação sempre tem colunas a mais.

---

## Decisões técnicas

| Escolhi | Contra o que | Por quê |
|---|---|---|
| Nenhuma dependência externa | pandas, recordlinkage, dedupe | É o que permite rodar dentro do navegador do cliente, sem que a base saia da máquina dele |
| Veto antes do agrupamento | filtrar depois de agrupar | Agrupar primeiro apaga a informação que separa matriz de filial — foi assim que 12 pares foram fundidos na primeira versão |
| Regras com motivo escrito | modelo estatístico treinado | Não existe base pública de duplicatas rotuladas em português, e cadastro é dado pessoal. Regra que se lê também se audita |
| Maior entre Jaro-Winkler e Jaccard | média dos dois | Erram em situações diferentes: um perde reordenação, o outro perde digitação. O par só precisa ser pego por um |
| Dois limiares com papéis distintos | um limiar só | Os dois conjuntos discordam do melhor valor, e a discordância é real. Assumi as duas faixas em vez de esconder uma |
| Lista de conferência | fusão automática | Falso positivo apaga dado e não tem volta. A decisão é de quem responde pelo cadastro |

---

## O que este projeto não faz

- **Não funde registro.** Devolve lista, não executa alteração.
- **Não consulta a Receita Federal.** Valida o dígito verificador, não a existência do CNPJ.
- **Não enriquece cadastro.** Não busca endereço por CEP nem completa dado faltante.
- **Não resolve base sem nome.** Se a coluna de nome estiver vazia na maioria das linhas, nenhuma técnica salva.

---

Licença MIT. Escrito por [Tiago Lopes](https://www.linkedin.com/in/tiagolopes-gerentegeral/) — advogado e legal engineer. [Outros projetos](https://github.com/thiagolopes-ai).
