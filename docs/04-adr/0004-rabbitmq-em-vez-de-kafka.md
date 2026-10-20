# ADR-0004 — RabbitMQ (fila durável) em vez de Kafka

- **Status:** Aceito
- **Data:** 2026-10-20

## Contexto

O consolidado recebe **50 req/s em picos** (RNF-02). Precisamos de um transporte durável
que sustente esse volume, com suporte a retry e dead-letter.

## Decisão

Usar um **broker de filas durável** (RabbitMQ no compose local; **Amazon SQS** ou
**RabbitMQ gerenciado** em nuvem). **Não** usar Kafka neste porte.

## Justificativa

| Critério | RabbitMQ / SQS | Kafka |
|---|---|---|
| Volume alvo (50 req/s ≈ 4,3 M msgs/dia) | ✅ folgado | ✅ (overkill) |
| Complexidade operacional | Baixa | Alta (cluster, ZK/KRaft, retenção) |
| Fila durável + DLQ + retry | ✅ nativos | ⚠️ via configuração/consumer |
| Modelo | fila ponto-a-ponto | log particionado |
| Custo gerenciado | Baixo | Maior |
| Replay de histórico | ❌ (fica na DLQ/retry) | ✅ nativo |

Para **50 req/s com dois consumidores e um domínio**, fila durável é o **menor meio que
atende**. Kafka seria complexidade sem retorno.

## Consequências

- ✅ Operação simples; DLQ e retry nativos.
- ⚠️ Sem replay de longo prazo (aceitável — saldo é reconstruível da fonte).

## Critério de reversão (quando migrar para Kafka)

Migrar se **qualquer** condição ocorrer:
1. Throughput sustentado **> ~5.000 msgs/s** (100× o alvo atual).
2. Necessidade de **replay** de eventos históricos por múltiplos consumidores.
3. O stream virar **fonte de verdade** para analítica/CDC (event sourcing).
O transporte é abstraído por interface (`EventPublisher`/`EventConsumer`) — a troca não
deve tocar a lógica de domínio (ver ADR-0003 e o código da PoC).
