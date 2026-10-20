# ADR-0005 — Idempotência do consumidor por `event_id`

- **Status:** Aceito
- **Data:** 2026-10-20

## Contexto

A escolha de outbox + fila durável torna a entrega **at-least-once**: um evento
**pode ser entregue mais de uma vez** (retry, reprocesso de DLQ, redelivery do broker).
Ingenuamente, isso duplicaria o valor no saldo.

## Decisão

O consumidor é **idempotente** por `event_id`: antes de aplicar, verifica se aquele
evento já foi processado (tabela `processed_event`). Se sim, faz **ack e ignora**.

```
on_event(evt):
   BEGIN
     if exists(processed_event, evt.id):  -> ack; return  (ja processado)
     apply_delta(DailyBalance, evt)        -> upsert agregado
     insert(processed_event, evt.id)
   COMMIT
   ack
```

## Justificativa

- At-least-once + consumidor idempotente = **efetivamente exactly-once** no efeito.
- Alternativa “deduplicar no broker” não existe de forma confiável; a **responsabilidade
  é do consumidor**.
- O `event_id` é gerado **no produtor** (determinístico por lançamento), então reenvios
  carregam a **mesma** identidade.

## Consequências

- ✅ Reprocesso e retry seguros (RF-08) — base para a estratégia dos 5% (RNF-02).
- ⚠️ Custo de uma escrita extra por evento (checagem + marcação) — barato no volume alvo.
- ⚠️ A tabela de idempotência precisa de política de retenção (ex.: 30–90 dias).

## Alternativas rejeitadas

- **Confiar em “no máximo uma entrega”:** brokers não oferecem exactly-once fim-a-fim com
  garantia forte; assumir isso é o caminho para divergência de saldo.
- **Chave natural (data+valor+descrição):** falsos positivos (dois cafés de R$ 5 no mesmo
  dia) — a identidade precisa ser **do evento**, não do conteúdo.
