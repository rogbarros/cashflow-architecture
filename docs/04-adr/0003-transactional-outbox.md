# ADR-0003 — Transactional Outbox para publicação confiável do evento

- **Status:** Aceito
- **Data:** 2026-10-20

## Contexto

Ao registrar um lançamento, precisamos **duas** coisas: (1) gravar no banco e (2) publicar
o evento. Fazer as duas “direto” cria uma **janela de inconsistência**:

- Grava no BD e o processo morre **antes** de publicar → lançamento existe, evento **nunca** publicado → saldo nunca atualiza.
- Publica e o commit do BD **falha** → evento de um lançamento que não existe.

Bancos e brokers **não compartilham transação** — não há commit distribuído simples.

## Decisão

Usar o **Transactional Outbox**: na **mesma transação** do lançamento, gravar também o
evento numa tabela `outbox`. Um **relay** lê a outbox e publica no broker, marcando como
enviado. O broker confirma; a linha sai da outbox.

```
BEGIN
   INSERT INTO cash_flow_entry (...)
   INSERT INTO outbox (event_id, payload, status='PENDING')
COMMIT
-- relay assincrono:
SELECT * FROM outbox WHERE status='PENDING'
  -> publish to broker
  -> UPDATE outbox SET status='SENT'
```

## Justificativa

- Garante **atomicidade**: ou existe **lançamento + evento**, ou **nenhum dos dois**.
- Publicação vira **at-least-once** (pode reenviar) — o que é **seguro** desde que o
  consumidor seja idempotente (ADR-0005).
- Independente do broker: se o broker cair, a outbox **acumula** e publica depois.

## Consequências

- ✅ Fecha a janela de perda de evento (RNF-05).
- ⚠️ Introduz **at-least-once** → exige idempotência no consumidor.
- ⚠️ Um pequeno **lag** entre commit e publicação (aceitável; medido — ver doc 07).

## Alternativas rejeitadas

- **Publicar antes de commitar / depois sem outbox:** cria evento fantasma ou evento perdido.
- **Two-Phase Commit (2PC):** complexidade e acoplamento altos; brokers raramente suportam.
- **Change Data Capture (CDC):** válido, mas exige infra extra (Debezium + Kafka Connect)
  — desproporcional para o porte. Fica como **evolução** se o throughput crescer.
