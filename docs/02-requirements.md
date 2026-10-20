# 02 — Refinamento de Requisitos (RF / RNF)

## 1. Requisitos Funcionais (RF)

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| **RF-01** | Registrar um lançamento (crédito ou débito) com valor, data e descrição | Must | `POST /entries` retorna `201` com `id`; valor > 0 |
| **RF-02** | Consultar lançamentos por período | Must | `GET /entries?from=&to=` retorna a lista do período |
| **RF-03** | Consultar lançamentos do dia | Should | `GET /entries?date=YYYY-MM-DD` |
| **RF-04** | Consolidar o saldo diário a partir dos lançamentos | Must | Saldo = Σ créditos − Σ débitos do dia |
| **RF-05** | Consultar saldo consolidado de um dia | Must | `GET /balance?date=` retorna crédito, débito e saldo |
| **RF-06** | Consultar saldo consolidado de um período | Should | `GET /balance?from=&to=` |
| **RF-07** | Reprocessar lançamentos que falharam na consolidação | Should | Reenvio pela DLQ recalcula o saldo |
| **RF-08** | Idempotência no consumo do evento | Must | Evento repetido não duplica o agregado |
| **RF-09** | Registrar estorno de lançamento | Could | Estorno é um novo lançamento de sinal oposto |

## 2. Requisitos Não Funcionais (RNF)

> O enunciado fixa **dois** RNFs explícitos; os demais são derivados e usados para guiar
> as decisões (não inventamos obrigatoriedade — **classificamos a origem**).

| ID | RNF | Origem | Alvo | Como é atendido |
|---|---|---|---|---|
| **RNF-01** | **Lançamentos não podem ficar indisponíveis se o Consolidado cair** | ✅ Enunciado | 100% de disponibilidade do `cashflow-service` independente do estado do consolidado | Assincronia + evento persistido (ADR-0002); sem chamada síncrona |
| **RNF-02** | Consolidado recebe **50 req/s** em picos, com **máx. 5% de perda** | ✅ Enunciado | ≥ 47,5 req/s efetivos; perda ≤ 5% | Backlog durável + consumo concorrente + retry; ver `05-nfr-strategy` |
| **RNF-03** | Latência de escrita do lançamento baixa | Derivado | P95 < 150 ms | Escrita local + publicação assíncrona; índice em `entry_date`/`merchant_id` |
| **RNF-04** | Escalabilidade horizontal dos dois serviços | Derivado | Escala por réplicas sem estado local | Stateless com estado em BD/broker |
| **RNF-05** | Persistência e durabilidade dos lançamentos | Derivado | 0 perda de lançamento aceito (fonte da verdade) | Commit em BD antes de confirmar `201`; outbox/fila durável |
| **RNF-06** | Auditabilidade mínima | Derivado | Todo lançamento rastreável (id, created_at) | Modelo imutável + log estruturado |
| **RNF-07** | Segurança de integração | Diferencial | Autenticação e integridade do evento | API key/JWT; ver `08-security` |
| **RNF-08** | Observabilidade da integração | Diferencial | Lag, backlog, perda, DLQ visíveis | Métricas + health; ver `07-observability` |
| **RNF-09** | Custo controlado | Diferencial | Ordem de magnitude por ambiente | Ver `06-cost-estimate` |

## 3. Ambiguidade identificada (e tratada, não ignorada)

### “Máx. 5% de perda” — de quê?

O enunciado não diz se 5% é **de chamadas** ou **de dados**, nem em qual janela. Esta é
uma **ambiguidade real** e vira decisão explícita (ver ADR-0006):

| Interpretação | Significado | Nossa leitura |
|---|---|---|
| (a) 5% das **requisições** ao consolidado podem falhar/degradar | perda de *disponibilidade* de consulta | aceitável sob pico, com degradação controlada |
| (b) 5% dos **lançamentos** podem não compor o agregado | perda de *dado* no consolidado | **inaceitável para a fonte da verdade** — mitigada por retry + DLQ |

**Decisão:** tratar **5% como orçamento de erro operacional sob pico** (a), garantindo que
**nenhum lançamento seja perdido** (RNF-05) — o consolidado se **recupera** do backlog.
O “5%” nunca autoriza perder um lançamento: ele é o limite de **degradação aceitável de
serviço**, não de integridade de dado.

### “Relatório de saldo diário consolidado”

Pode ser **por dia** ou **por período**. A resposta modela **dia** como caso base (RF-05)
e **período** como extensão (RF-06).

## 4. Matriz de rastreabilidade (requisito → decisão/artefato)

| Requisito | Decisão arquitetural | Documento |
|---|---|---|
| RNF-01 | Integração assíncrona por evento | ADR-0002 |
| RNF-02, RNF-04 | Consumo concorrente + backlog durável + escala horizontal | ADR-0004, 05-nfr |
| RNF-05 | Commit antes do `201` + evento durável | ADR-0003 |
| RF-08 | Idempotência por `event_id` | ADR-0005 |
| RNF-07 | API key + assinatura de evento | 08-security |
| RNF-08 | Métricas de lag/backlog/DLQ | 07-observability |

## 5. Fora de escopo (consciente)

- Autenticação multiusuário completa / multi-tenant com isolamento físico.
- Conciliação bancária (importar extrato do banco).
- Relatórios fiscais/contábeis.
- Front-end — o desafio é de **arquitetura de integração**, a interface é a API.

## 6. Requisitos difusos que **elevamos** a explícitos

O enunciado pede “representações arquiteturais” de itens que muitas entregas esquecem.
Elevamos a requisitos rastreáveis: **arquitetura de transição** (doc 09), **estimativa de
custo** (doc 06), **monitoramento** (doc 07) e **segurança de integração** (doc 08).
