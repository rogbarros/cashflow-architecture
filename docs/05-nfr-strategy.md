# 05 — Estratégia de NFRs (como os requisitos são atendidos)

Este documento liga **cada NFR** às **decisões** e à **evidência** (PoC ou plano de teste).

## RNF-01 — Lançamentos disponíveis mesmo com o consolidado fora

| Aspecto | Como |
|---|---|
| **Mecanismo** | Integração assíncrona por evento (ADR-0002). Nenhuma chamada de rede do `cashflow-service` para o `consolidation-service`. |
| **Garantia** | O `201` é emitido após commit **local**. O broker só é tocado pelo **relay** (outbox), fora do caminho crítico. |
| **Evidência na PoC** | Teste `test_cashflow_accepts_when_consolidation_down`: com o consumidor desligado, `POST /entries` continua retornando `201`. |
| **Prova de fogo (produção)** | Desligar o `consolidation-service` em ambiente de teste e verificar 0 erro em `/entries` + backlog crescendo na fila. |

## RNF-02 — 50 req/s com até 5% de perda

| Aspecto | Como |
|---|---|
| **Ingestão** | N workers **competing consumers** drenam a mesma fila; escala horizontal. |
| **Perda de dado** | **0%** (ADR-0006): retry com backoff + DLQ; nenhum lançamento descartado. |
| **Absorção do pico** | A fila **amortece** a rajada — se a chegada (50 req/s) excede a vazão momentânea, o backlog cresce e drena depois; não há perda. |
| **5% de degradação** | Reservado à **consulta** sob pico extremo (429/503 controlado), **nunca** ao dado. |
| **Evidência na PoC** | Teste de carga (Locust/`hey`) contra o worker documentado; gráfico de backlog × tempo. |

### Dimensionamento do consumo (ordem de grandeza)

| Parâmetro | Valor | Comentário |
|---|---|---|
| Chegada em pico | 50 req/s | claim do enunciado |
| Msgs/dia (pico sustentado 1 h) | ~180.000 | 50 × 3600 |
| Custo por msg no worker | ~1–5 ms | upsert indexado |
| Vazão por worker | ~200–1.000 msg/s | folgado |
| **Workers para 50 req/s** | **1 basta**; **3** dá folga e HA | escala trivial |

Conclusão: **50 req/s é um volume modesto** — o desenho não precisa de Kafka (ADR-0004);
precisa de **durabilidade + idempotência + backlog monitorado**.

## RNF-03 — Latência de escrita do lançamento

| Aspecto | Como |
|---|---|
| **Caminho crítico** | INSERT lançamento + INSERT outbox na mesma transação, índice em (`merchant_id`,`entry_date`). |
| **Sem I/O externo** | Nenhuma espera de rede (broker é assíncrono). |
| **Alvo** | P95 < 150 ms (local: dezenas de ms). |

## RNF-04 — Escalabilidade horizontal

- Serviços **stateless**; estado em BD e broker (gerenciados).
- Escala por **réplicas** atrás de load balancer.
- Consumo escala por **mais workers** na mesma fila.

## RNF-05 — Nenhum lançamento perdido (invariante)

- Commit **antes** do `201` (o que o comerciante vê confirmado, está persistido).
- Outbox garante o evento; broker durável garante a entrega; DLQ garante que nada some.
- **Rastreabilidade:** todo lançamento tem `id`, `created_at`; todo evento tem `event_id`.

## RNF-06..09 — Auditabilidade, segurança, observabilidade, custo

- **Auditabilidade:** modelo imutável (correção = estorno) → trilha natural.
- **Segurança:** ver `08-security.md` (API key, assinatura de evento, princípio do menor privilégio).
- **Observabilidade:** ver `07-observability.md` (lag, backlog, DLQ, taxa de erro).
- **Custo:** ver `06-cost-estimate.md`.

## Resumo — NFR → decisão → evidência

| NFR | Decisão | Evidência |
|---|---|---|
| RNF-01 | Evento assíncrono | teste automatizado |
| RNF-02 | Competing consumers + retry/DLQ | teste de carga (plano) |
| RNF-03 | Transação local + índices | benchmark local |
| RNF-04 | Stateless + replicas | diagrama de implantação |
| RNF-05 | Commit + outbox + DLQ | teste de durabilidade |
| RNF-08 | Métricas de lag/backlog | doc + endpoint `/metrics` |
