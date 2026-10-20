# 06 — Estimativa de Custo (infraestrutura e licenças)

> Estimativa **de ordem de grandeza** para dimensionar o ambiente — não uma fatura.
> Valores em USD, região São Paulo (sa-east-1), preços públicos aproximados (2026).
> A cifra que importa é a **relação custo × volume**, não o centavo.

## 1. Premissas de volume

| Parâmetro | Valor |
|---|---|
| Comerciantes ativos | 1.000 (base inicial) |
| Lançamentos/comerciante/dia | ~50 → **50.000/dia** |
| Pico de ingestão | **50 req/s** (claim do enunciado) |
| Retenção de lançamentos | 5 anos |
| Consultas de saldo/dia | ~200.000 |

## 2. Opção A — Serverless gerenciado (menor custo inicial)

| Componente | Serviço | Custo/mês aprox. | Comentário |
|---|---|---|---|
| Compute API | AWS Lambda / ECS Fargate (2 réplicas pequenas) | ~US$ 30–70 | picos absorvidos por escala |
| Banco (lançamentos) | RDS PostgreSQL `db.t4g.micro` + storage | ~US$ 20–35 | multi-AZ opcional (+~80%) |
| Banco (consolidado) | mesmo RDS (schema separado) ou instância pequena | ~US$ 20–35 | |
| Fila | Amazon SQS (4,3 M msgs/mês) | ~US$ 2 | **barato** — ~US$ 0,40/milhão |
| Broker alternativo | Amazon MQ (RabbitMQ) `mq.t3.micro` | ~US$ 30 | se precisar de AMQP gerenciado |
| Observabilidade | CloudWatch (métricas/logs) | ~US$ 10–20 | |
| **Total ordem** | | **~US$ 80–160/mês** | para a base inicial |

## 3. Opção B — Kubernetes gerenciado (maior controle, maior custo base)

| Componente | Custo/mês aprox. | Comentário |
|---|---|---|
| EKS control plane | ~US$ 73 | antes de qualquer node |
| Nodes (2× `t3.medium` spot/on-demand) | ~US$ 60–120 | |
| RDS + SQS + observabilidade | ~US$ 60–90 | como acima |
| **Total ordem** | **~US$ 200–300/mês** | só compensa com **muitos** serviços/equipes |

> **Recomendação:** começar na **Opção A**. Kubernetes (Opção B) se justifica quando houver
> **muitos** serviços e um **time de plataforma** dedicado — não para 2 serviços.

## 4. Licenças

| Item | Custo |
|---|---|
| Stack da PoC (Python, FastAPI, RabbitMQ, PostgreSQL, SQLite) | **US$ 0** — open source |
| Broker gerenciado (SQS) | por uso (barato, ver acima) |
| Broker iPaas gerenciado (ex.: barramento corporativo), **se adotado** | licença por volume/conector — **ordem de 10–100× a fila nativa** |

> **Ponto de arquitetura (não de preço):** se a organização já tem um **barramento iPaaS**
> (MuleSoft, Digibee, Sensedia), a decisão **build × buy** é: reusar governança/conectores
> existentes vs. usar fila nativa mais barata e simples. Para **2 serviços**, a fila nativa
> vence no custo e na simplicidade; o iPaaS vence em **padronização transversal** quando há
> muitas integrações e time heterogêneo. Ver ADR-0004.

## 5. Custo por unidade (a métrica que escala)

| Métrica | Cálculo | Valor |
|---|---|---|
| Custo por 1.000 lançamentos | US$ 120 / (50.000×30) × 1.000 | **~US$ 0,08** |
| Custo por comerciante/mês | US$ 120 / 1.000 | **~US$ 0,12** |
| Custo de fila por milhão de msgs | SQS | **~US$ 0,40** |

**Leitura:** o custo é dominado pelo **banco**, não pela fila. Otimizar significa
**retenção e índices**, não “cortar broker”.

## 6. Alavancas de otimização

1. **Retenção do dado quente** (lançamentos recentes em linha; antigos em arquivo/analytics).
2. **Aggregado materializado** (ADR-0007) reduz carga de leitura → menos compute.
3. **Auto-scaling** por fila (escala no pico, encolhe na calmaria).
4. **Reservas/Savings Plans** para a linha base de compute (−30–40%).
5. **Spot/Fargate Spot** para os workers (tolerantes a interrupção).

## 7. Estimativa de esforço de implementação (contexto GP)

| Fase | Esforço (pessoa-semana) | Comentário |
|---|---|---|
| Serviços base + modelo | 2 | 2 serviços + contratos de evento |
| Outbox/relay + idempotência | 1,5 | a parte “chata” e crítica |
| Observabilidade + DLQ reprocesso | 1 | métricas, alertas, runbook |
| Segurança (auth + assinatura) | 1 | |
| Testes (unit + integração + carga) | 1,5 | |
| Transição/legado (doc 09) | 2 | |
| **Total** | **~9–10 pessoa-semanas** | squad pequeno (2–3 pessoas) → ~1 mês |
