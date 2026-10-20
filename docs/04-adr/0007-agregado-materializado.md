# ADR-0007 — Agregado materializado em vez de `SUM()` on-the-fly

- **Status:** Aceito
- **Data:** 2026-10-20

## Contexto

O saldo diário poderia ser calculado **na hora da consulta** (`SELECT SUM(...)`) ou
**mantido materializado** (tabela `DailyBalance` atualizada a cada evento).

## Decisão

Manter o saldo **materializado** (`DailyBalance`), atualizado **incrementalmente** por
upsert a cada evento consumido. A consulta apenas **lê** o agregado.

## Justificativa

- **Latência de leitura previsível:** ler uma linha é O(1); `SUM()` cresce com o volume
  do período e degrada sob pico (RNF-03, e protege a consulta dos 50 req/s).
- **Custo de escrita amortizado:** o upsert é barato e acontece 1× por lançamento.
- **Desacopla leitura de escrita:** a consulta não recalcula — combina bem com a API de
  leitura separada do worker de escrita.

## Consequências

- ✅ Leitura rápida e estável sob pico.
- ⚠️ O agregado é **derivado**: precisa ser **reconstruível** (pode ser recalculado dos
  lançamentos se houver suspeita de divergência — comando de rebuild).
- ⚠️ Exige idempotência (ADR-0005) para o upsert não duplicar.

## Alternativas rejeitadas

- **`SUM()` on-the-fly:** simples, mas escala mal e acopla a latência de leitura ao volume.
- **Cache (Redis) do saldo:** adiciona um componente sem resolver a raiz; o agregado em
  banco já é a “cache” correta e durável.
- **CQRS com read model em outro store:** over-engineering para o porte — a separação
  lógica já existe; o store físico separado pode vir depois.
