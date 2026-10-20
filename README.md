# Controle de Fluxo de Caixa do Comerciante — Arquitetura Alvo + PoC

Desafio técnico: arquitetura de integração para um comerciante controlar o
**fluxo de caixa diário**, com dois serviços que precisam coexistir sem acoplamento:

- **`cashflow-service`** — recebe os lançamentos (débito/crédito) do comerciante.
- **`consolidation-service`** — consolida o saldo diário.

> **RNF que rege tudo:** o serviço de lançamentos **não pode ficar indisponível se o
> serviço de consolidado cair**. Em picos, o consolidado recebe **50 req/s** com no
> máximo **5% de perda**.

## Como ler este repositório

O foco deste projeto é **decisão arquitetural** — não volume de código. A PoC existe
para provar que a arquitetura é executável (`docker-compose up`), não para esgotar os
requisitos. Conforme o enunciado, os requisitos são expressos sobretudo nas
**decisões e representações arquiteturais** (ADRs, diagramas C4, NFRs, custo,
observabilidade, segurança).

| Documento | Conteúdo |
|---|---|
| [`docs/01-domain-mapping.md`](docs/01-domain-mapping.md) | Domínios, capacidades de negócio, contexto delimitado |
| [`docs/02-requirements.md`](docs/02-requirements.md) | Requisitos funcionais e não funcionais refinados + rastreabilidade |
| [`docs/03-architecture.md`](docs/03-architecture.md) | Arquitetura alvo, C4, fluxos, padrões |
| [`docs/04-adr/`](docs/04-adr/) | Architecture Decision Records (a decisão antes do código) |
| [`docs/05-nfr-strategy.md`](docs/05-nfr-strategy.md) | Como cada NFR é atendido (50 req/s, 5% perda, resiliência) |
| [`docs/06-cost-estimate.md`](docs/06-cost-estimate.md) | Estimativa de custo de infraestrutura e licenças |
| [`docs/07-observability.md`](docs/07-observability.md) | Monitoramento, métricas, alertas, SLO |
| [`docs/08-security.md`](docs/08-security.md) | Critérios de segurança de integração e integridade |
| [`docs/09-transition-architecture.md`](docs/09-transition-architecture.md) | Arquitetura de transição (convivência com legado) |

## PoC — executar localmente

A PoC sobe **dois serviços + broker de mensagens**:

```
cashflow-service  ──lancamento──▶  RabbitMQ (fila duravel)  ──▶  consolidation-service
   (API + BD)                          |
                                       └─ DLQ (mensagens nao processadas)
```

### Opção A — Docker Compose (caminho recomendado)

```bash
cd src
docker-compose up --build
```

- `cashflow-service`: http://localhost:8001/docs
- `consolidation-service`: http://localhost:8002/docs
- RabbitMQ Management: http://localhost:15672 (guest/guest)

### Opção B — Local (sem Docker), usando fila por arquivo (SQLite/outbox)

Para ambientes sem Docker, os serviços rodam com um **outbox de arquivo** que
simula a fila durável (mesmo contrato, transporte substituível — ver ADR-0003):

```bash
cd src
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements.txt
# terminal 1
PORT=8001 python -m cashflow_service
# terminal 2
PORT=8002 python -m consolidation_service
```

Ou use o runner pronto: [`run_local.sh`](src/run_local.sh) (Linux/Mac/WSL) ou
[`run_local.ps1`](src/run_local.ps1) (Windows), que sobe os dois serviços e ativa a fila por arquivo.

### Testes

```bash
cd src
pytest -q
```

Os testes cobrem: contrato do lançamento, publicação de evento, consumo assíncrono,
idempotência, e o cenário-chave **“consolidado indisponível não derruba lançamentos”**.

Evidência de vazão (RNF-02), executável sem broker:

```bash
cd src
python -m tests.load_test 5000     # mede publicacao e processamento (msg/s)
```

## O que uma PoC deste porte prova (e o que não prova)

| Prova | Não prova |
|---|---|
| Desacoplamento assíncrono real (lançamento independente do consolidado) | Volume de 50 req/s em produção (ver teste de carga documentado) |
| Contrato de evento + idempotência | Alta disponibilidade multi-AZ |
| Recuperação de backlog e DLQ | Custos reais de nuvem (ver estimativa) |

## Decisão central

A exigência *“lançamentos não pode cair se o consolidado cair”* **proíbe integração
síncrona**. A resposta é **assincronia com evento persistido** — o lançamento é
confirmado localmente e o evento fica durável; o consolidado processa no seu ritmo.
Detalhamento e trade-offs: [`docs/04-adr/0002-integração-assincrona-por-evento.md`](docs/04-adr/).
