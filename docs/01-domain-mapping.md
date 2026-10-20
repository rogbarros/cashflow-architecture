# 01 — Mapeamento de Domínios e Capacidades

## 1. Contexto de negócio

Um **comerciante** (loja, MEI, pequeno varejo) precisa acompanhar o **fluxo de caixa
do dia**: tudo que entrou (crédito) e tudo que saiu (débito), e um **saldo diário
consolidado** ao final do período. O problema de negócio é a **visibilidade tardia**:
hoje o comerciante só sabe o saldo depois de fechar o caixa manualmente.

## 2. Capacidades de negócio (capability map)

| # | Capacidade | Descrição | Subdomínio (DDD) |
|---|---|---|---|
| C1 | **Registrar lançamento** | Receber um débito ou crédito com valor, data, descrição, tipo | Core — *Cash Flow* |
| C2 | **Consultar lançamentos** | Listar lançamentos do dia/período | Core — *Cash Flow* |
| C3 | **Publicar evento de lançamento** | Notificar o restante do sistema de que houve lançamento | Supporting — *Cash Flow* |
| C4 | **Consolidar saldo diário** | Agregar créditos − débitos por data | Core — *Consolidation* |
| C5 | **Consultar saldo consolidado** | Devolver o saldo de um dia/período | Core — *Consolidation* |
| C6 | **Reprocessar falhas** | Recuperar eventos não processados (DLQ) | Supporting — *Consolidation* |
| C7 | **Observar saúde da integração** | Métricas de lag, backlog, perda | Generic — *Platform* |

## 3. Contextos delimitados (Bounded Contexts)

```
┌─────────────────────────────┐        ┌─────────────────────────────┐
│   Bounded Context:           │        │   Bounded Context:           │
│   CASH FLOW (Lançamentos)    │        │   CONSOLIDATION (Saldo)      │
│                              │        │                              │
│   • Registrar lançamento     │ evento │   • Consumir lançamento      │
│   • Consultar lançamento     │  ────▶ │   • Agregar débito/crédito   │
│   • Publicar evento          │ (async)│   • Consultar saldo diário   │
│                              │        │   • Reprocessar (DLQ)        │
│   Linguagem: débito, crédito,│        │   Linguagem: saldo, agregado,│
│   lançamento, valor, data    │        │   período, consolidado       │
└─────────────────────────────┘        └─────────────────────────────┘
        Language of its own                    Language of its own
```

### Por que **dois** contextos e não um?

- **Razões de mudança distintas.** O *cash flow* muda quando o comerciante lança; o
  *consolidation* muda quando a **regra de agregação** muda. Acoplar força as duas a
  evoluírem juntas.
- **NFRs opostos.** O lançamento precisa ser **sempre aceito e rápido**; a consolidação
  tolera **latência** (processa em lote/streaming). São invariantes diferentes.
- **Risco isolado.** Se a agregação degrada, o registro de lançamento — a fonte da
  verdade — **não pode ser afetado**. Esse é o NFR central do desafio.

> **Estratégia de integração:** relação **Customer/Supplier** entre contextos —
> *Cash Flow* publica um **evento de domínio** (`CashFlowEntryRegistered`) e *Consolidation*
> é consumidor. Comunicação **unidirecional e assíncrona** (ver ADR-0002).

## 4. Linguagem ubíqua (glossário)

| Termo | Definição | Contexto |
|---|---|---|
| **Lançamento** | Um fato financeiro do dia: entrada (crédito) ou saída (débito) | Cash Flow |
| **Crédito** | Lançamento que **aumenta** o saldo | Cash Flow |
| **Débito** | Lançamento que **diminui** o saldo | Cash Flow |
| **Saldo diário** | Resultado de Σ créditos − Σ débitos em um dia | Consolidation |
| **Consolidado** | Visão agregada (por dia ou período) sobre os lançamentos | Consolidation |
| **Evento de lançamento** | Fato publicado quando um lançamento é registrado | Ambos |
| **Idempotência** | Reprocessar o mesmo evento sem duplicar o efeito | Ambos |

## 5. Fronteiras e responsabilidades

| Pergunta | Cash Flow | Consolidation |
|---|---|---|
| Quem **cria** o lançamento? | ✅ Sim | ❌ Não |
| Quem é **fonte da verdade** dos lançamentos? | ✅ Sim | ❌ (deriva) |
| Quem **agrega**? | ❌ Não | ✅ Sim |
| Quem pode **cair** sem afetar o outro? | — | ✅ Pode cair; Cash Flow segue |
| Quem **consome** evento? | ❌ (publica) | ✅ (consome) |

## 6. Modelo conceitual (domínio)

```
CashFlowEntry (lançamento)
├── id            (UUID)             — identidade
├── type          (CREDIT | DEBIT)   — natureza
├── amount        (decimal > 0)      — valor
├── currency      (BRL)              — moeda
├── entry_date    (date local)       — data do lançamento (fuso do comerciante)
├── description   (texto)            — descrição livre
├── merchant_id   (id)               — dono do caixa
└── created_at    (timestamp)        — momento do registro

DailyBalance (saldo diário)
├── merchant_id
├── date
├── total_credit  (Σ créditos do dia)
├── total_debit   (Σ débitos do dia)
└── balance       (total_credit − total_debit)
```

### Invariantes
1. `amount` **sempre positivo**; a natureza vem de `type` (evita valor negativo ambíguo).
2. Um lançamento **nunca é alterado** (imutável); correção é um **lançamento de estorno**.
3. `entry_date` é a data **de negócio** (não `created_at`) — o saldo diário usa `entry_date`.
4. `DailyBalance` é **derivado**: nunca é fonte da verdade, sempre reconstruível.

## 7. Ubiquitous language × integração

O evento é a **fronteira anti-corrupção (ACL)**: o *Consolidation* não conhece as tabelas
do *Cash Flow*, apenas o **contrato do evento**. Mudanças internas no Cash Flow que não
alterem o contrato do evento **não impactam** o Consolidation.
