# ADR-0002 — Integração assíncrona por evento (não síncrona)

- **Status:** Aceito
- **Data:** 2026-10-20
- **Requisito motor:** **RNF-01** — “o serviço de lançamentos não pode ficar indisponível
  se o serviço de consolidado cair”.

## Contexto

Existem duas formas de integrar os serviços:

1. **Síncrona:** ao registrar um lançamento, o `cashflow-service` chama o
   `consolidation-service` via HTTP e espera a resposta.
2. **Assíncrona:** o `cashflow-service` publica um **evento** e o consolidado consome.

## Decisão

Integração **assíncrona por evento**: o `cashflow-service` grava o lançamento e publica
um evento `CashFlowEntryRegistered`; o `consolidation-service` **consome** quando puder.

## Justificativa

A integração síncrona **quebraria o RNF-01 por construção**: se o consolidado está fora,
a chamada HTTP falha (ou estoura timeout) e o lançamento — que deveria ser sempre aceito —
fica refém de um serviço secundário. A mala direta de falhas via síncrono:

```
Síncrono:   Comerciante → CashFlow → (HTTP) → Consolidado ❌  ⇒ CashFlow devolve erro ⇒ LANÇAMENTO PERDIDO
Assíncrono: Comerciante → CashFlow → commit + evento ✅       ⇒ Consolidado processa depois
```

O evento torna o consolidado um **consumidor desacoplado**: sua indisponibilidade vira
**backlog**, não **erro para o comerciante**.

## Consequências

- ✅ Atende RNF-01 (lançamento independente) e RNF-05 (nenhum lançamento perdido).
- ✅ Absorve picos (o backlog amortece a diferença de ritmo).
- ⚠️ **Consistência eventual:** o saldo pode ficar defasado por um instante — aceitável
  para saldo diário (não é transação bancária em tempo real).
- ⚠️ Exige **idempotência** no consumidor (ver ADR-0005) e **observabilidade de lag**.

## Alternativas rejeitadas

- **Síncrono com retry/circuit breaker:** mitiga, mas ainda acopla a **disponibilidade
  do lançamento** à do consolidado. Circuit breaker apenas troca “erro” por “recusa”.
- **Fila em memória (no processo):** perderia eventos no restart — fere RNF-05.
