# ADR-0001 — Separação em dois serviços por Bounded Context

- **Status:** Aceito
- **Data:** 2026-10-20

## Contexto

O desafio pede dois serviços: **lançamentos** e **consolidado diário**. A tentação é
criar um monólito único (mais simples) ou um serviço por entidade (mais “micro”).

## Decisão

Separar em **dois serviços por bounded context** — `cashflow-service` e
`consolidation-service` — cada um com seu banco e sua linguagem, integrados por evento.

## Justificativa

- **Razões de mudança distintas:** regra de lançamento vs. regra de agregação.
- **NFRs opostos:** escrita sempre disponível vs. agregação tolerante a latência.
- **Isolamento de risco:** a queda do consolidado não pode tocar o lançamento (RNF-01).

## Consequências

- ✅ Isolamento de falha e evolução independente.
- ⚠️ Introduz consistência eventual (o saldo “atrasa” alguns ms/segundos).
- ⚠️ Custo operacional de dois deploys e um broker.

## Alternativas rejeitadas

- **Monólito único:** acopla os dois NFRs; não demonstra o desacoplamento pedido.
- **Um serviço por entidade (Lançamento/Débito/Crédito/Saldo):** over-decomposition;
  entidades do mesmo contexto mudam juntas.
