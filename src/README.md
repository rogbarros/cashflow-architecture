# PoC — Código

Prova de conceito do desafio: dois serviços FastAPI desacoplados por evento
persistido. O código é deliberadamente enxuto — cada arquivo existe para
**provar uma decisão** documentada em [`../docs/04-adr/`](../docs/04-adr/).

## Mapa do código

| Componente | Arquivo | Prova |
|---|---|---|
| Domínio do lançamento | `cashflow_service/app.py` | RF-01..RF-03; transação local + outbox (ADR-0003) |
| Domínio do consolidado | `consolidation_service/app.py` | RF-04/RF-05; idempotência por `event_id` (ADR-0005) |
| Transporte substituível | `common/events.py` | Fila por arquivo **ou** RabbitMQ (ADR-0004) |
| Relay do outbox | `cashflow_service/__main__.py` | Publicação desacoplada da escrita |
| Worker competing-consumer | `consolidation_service/__main__.py` | Escala independente da API |
| Testes arquiteturais | `tests/test_poc.py` | Inclui o cenário-chave de resiliência |
| Carga (RNF-02) | `tests/load_test.py` | Vazão do consumidor |

## Duas formas de rodar (mesmo contrato)

O domínio **não conhece o broker**. A variável `TRANSPORT` escolhe:

- `TRANSPORT=file` (padrão) — fila durável em `event_queue/events.jsonl`.
  Roda **sem Docker**; é o caminho usado para validar a PoC localmente.
- `TRANSPORT=rabbit` — AMQP real via `pika`, usado pelo `docker-compose.yml`.

Trocar de uma para outra é mudança de **infraestrutura**, não de negócio —
que é exatamente o ponto de ADR-0004.

## Executar

### Docker (recomendado)

```bash
docker-compose up --build
```

### Sem Docker

```bash
# Linux/Mac/WSL
bash run_local.sh
# Windows
.\run_local.ps1
```

## Testes

```bash
pytest -q
```

Cobertura dos cenários:

| Teste | O que verifica |
|---|---|
| `test_register_entry_returns_201` | Contrato do lançamento (RF-01) |
| `test_amount_must_be_positive` / `test_invalid_type_rejected` | Validações (RF-02) |
| `test_entry_creates_outbox_event` | Outbox gravado na mesma transação (ADR-0003) |
| `test_consolidation_materializes_balance` | Materialização do saldo (RF-04/05) |
| `test_idempotency_same_event_not_duplicated` | Reprocessamento não duplica (ADR-0005) |
| `test_key_scenario_consolidation_down_does_not_break_cashflow` | **RNF-01**: lançamento segue aceito com o consumo parado |

## Evidência de vazão (RNF-02: 50 req/s, ≤5% perda)

Medido nesta máquina com `python -m tests.load_test 5000`:

| Etapa | Vazão |
|---|---|
| Publicação no transporte | ~3.900 msg/s |
| Processamento (1 worker) | ~200 msg/s |

Um único worker já entrega **4× o requisito de 50 req/s**. O dimensionamento de
produção (3 workers para folga/HA) está em
[`../docs/05-nfr-strategy.md`](../docs/05-nfr-strategy.md).

## Endpoints

| Serviço | Método | Rota |
|---|---|---|
| cashflow (8001) | POST | `/entries` |
| cashflow | GET | `/entries?merchant_id=&date=` |
| consolidation (8002) | GET | `/balance?merchant_id=&date=` |
| consolidation | GET | `/balance/range?merchant_id=&from=&to=` |
| ambos | GET | `/health/live`, `/health/ready`, `/metrics` |
