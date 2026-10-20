# 07 — Observabilidade e Monitoramento

Numa integração assíncrona, **o que não é medido não existe**. O risco deixa de ser
“erro visível” e passa a ser **backlog silencioso**. Este documento define o que medir,
o que alertar e como diagnosticar.

## 1. Sinais de ouro (aplicados à integração)

| Sinal | Métrica | Alvo |
|---|---|---|
| **Latência** | P95/P99 de `POST /entries` e `GET /balance` | P95 < 150 ms |
| **Tráfego** | req/s de ingestão; msgs/s consumidas | ≥ 50 req/s suportado |
| **Erros** | 5xx por endpoint; falhas de processamento | < 0,1% |
| **Saturação** | profundidade de fila, uso de CPU/conexões | backlog → 0 na janela do dia |

## 2. Métricas específicas da integração (as que importam aqui)

| Métrica | Descrição | Por que |
|---|---|---|
| `outbox_pending` | eventos gravados e ainda não publicados | detecta relay parado |
| `queue_depth` | mensagens na fila | **o termômetro do desacoplamento** |
| `consumer_lag_seconds` | tempo entre publicação e consumo | deteta consumidor lento |
| `events_processed_total` | contador de eventos aplicados | vazão |
| `events_duplicated_total` | eventos ignorados por idempotência | saúde do exactly-once |
| `dlq_depth` | mensagens na dead-letter | falhas persistentes |
| `balance_rebuild_age` | tempo do último rebuild do agregado | integridade |

## 3. Health checks

| Endpoint | Semântica |
|---|---|
| `GET /health/live` | o processo está vivo (liveness) |
| `GET /health/ready` | consegue atender (dependências OK) |
| `GET /metrics` | exposição Prometheus (formato texto) |

> **Fail-fast no worker:** se o worker não consegue conectar ao broker, ele reporta
> `ready=false` — mas isso **não** afeta o `cashflow-service` (desacoplamento).

## 4. Alertas (o que acorda alguém)

| Alerta | Condição | Severidade |
|---|---|---|
| **Backlog crescendo** | `queue_depth` cresce por > 10 min | 🔴 Alto |
| **Relay parado** | `outbox_pending` > 0 por > 5 min | 🔴 Alto |
| **DLQ recebendo** | `dlq_depth` aumenta | 🟠 Médio |
| **Lag alto** | `consumer_lag_seconds` > 60 s | 🟠 Médio |
| **Erro de ingestão** | taxa 5xx > 1% por 5 min | 🔴 Alto |
| **Divergência de saldo** | diferença entre agregado e `SUM` em auditoria | 🔴 Alto |

## 5. Rastreabilidade (correlação)

- **`correlation_id`** propagado do `POST /entries` até o processamento do evento.
- **`event_id`** presente no log do produtor e do consumidor.
- Permitir responder: *“este lançamento entrou no saldo? quando? por qual worker?”*.

## 6. Dashboards (proposta)

1. **Ingestão:** req/s, P95, erros, latência de escrita.
2. **Integração:** `outbox_pending`, `queue_depth`, `consumer_lag`, `dlq_depth`.
3. **Consolidação:** eventos/s, duplicados, throughput por worker.
4. **Negócio:** saldo consolidado por dia × lançamentos brutos (auditoria visual).

## 7. Diagnóstico rápido (runbook)

| Sintoma | Provável causa | Ação |
|---|---|---|
| Backlog subindo, sem erro | pico ou worker lento | escalar workers |
| `outbox_pending` travado | relay parado | reiniciar relay / checar broker |
| DLQ crescendo | evento malformado ou regra | inspecionar, corrigir, reprocessar |
| Saldo divergente | bug de idempotência | rodar rebuild do agregado + investigar |

## 8. SLO proposto

| SLO | Alvo |
|---|---|
| Disponibilidade de ingestão | 99,9% |
| Disponibilidade de consulta de saldo | 99,5% (5% absorvido por RNF-02) |
| Frescor do saldo (lag máximo) | ≤ 60 s em operação normal |
| Perda de lançamento | **0** |
