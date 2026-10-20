# ADR-0006 — Interpretação do “máx. 5% de perda”

- **Status:** Aceito
- **Data:** 2026-10-20
- **Requisito motor:** **RNF-02**.

## Contexto

O enunciado diz: *“em picos o consolidado recebe 50 req/s com no máximo 5% de perda”*.
**“Perda” não está definida** — pode ser:

- (a) **perda de disponibilidade** de *consulta* sob pico (5% das requisições ao
  consolidado podem falhar/degradar), ou
- (b) **perda de dado** (5% dos lançamentos não entram no saldo consolidado).

## Decisão

Interpretar **5% como orçamento de erro operacional sob pico** (a) — **nunca** como
licença para perder lançamento. A integridade do dado é **invariante**: **0% de perda
de lançamento** (o lançamento é a fonte da verdade).

Traduzido em alvos operacionais:

| Métrica | Alvo |
|---|---|
| Perda de **lançamento** (dado) | **0%** — invariante |
| Sucesso de **ingestão** no consolidado | ≥ 99,9% (via retry + DLQ) |
| Degradação de **consulta** sob pico | ≤ 5% (respostas 429/503 controladas) |
| Recuperação do backlog | dentro da janela do dia (o saldo fecha corretamente) |

## Justificativa

Ler “5%” como perda de **dado** seria **inaceitável** num sistema de caixa: o comerciante
veria um saldo errado silenciosamente. O número razoável para “perda de dado” é **zero**.
O “5%” só faz sentido como **tolerância de serviço** em rajada — o sistema **absorve** o
pico enfileirando (amortecimento) e eventualmente **converge**.

## Consequências

- ✅ Protege a integridade financeira (RF-04/RNF-05).
- ✅ O pico vira **backlog**, não **perda** — o consumo drena depois.
- ⚠️ Exige **medir lag/backlog** e alertar quando o backlog ameaça a janela do dia (doc 07).
- ⚠️ Sob pico extremo, a **consulta** pode ser degradada (ex.: `429`) antes de arriscar o dado.

## Nota de comunicação ao cliente

Por ser ambíguo, este ponto **deveria ser confirmado** com o solicitante. A decisão aqui
é a leitura **segura** (preserva o dado) e fica **explícita** para validação — em vez de
silenciosamente assumir o caminho que “perde lançamento”.
