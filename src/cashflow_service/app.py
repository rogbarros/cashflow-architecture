"""Cash Flow Service — registra lancamentos e publica eventos.

Ponto arquitetural central (ADR-0002): o POST /entries NAO chama o
consolidation-service. Ele grava localmente, publica no outbox e confirma.
Se o consolidado estiver fora, o lancamento continua sendo aceito.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Iterator

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

DB_PATH = os.environ.get("CASHFLOW_DB", "cashflow.db")

app = FastAPI(
    title="Cash Flow Service",
    version="1.0.0",
    description="Registra lancamentos (credito/debito). Fonte da verdade.",
)


# --------------------------------------------------------------------------- #
# Modelo de dados (SQLite na PoC; PostgreSQL em producao — ver docs/03)
# --------------------------------------------------------------------------- #
def init_db() -> None:
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS cash_flow_entry (
                id           TEXT PRIMARY KEY,
                merchant_id  TEXT NOT NULL,
                type         TEXT NOT NULL CHECK (type IN ('CREDIT','DEBIT')),
                amount       REAL NOT NULL CHECK (amount > 0),
                currency     TEXT NOT NULL DEFAULT 'BRL',
                entry_date   TEXT NOT NULL,
                description  TEXT,
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_entry_merchant_date
                ON cash_flow_entry (merchant_id, entry_date);

            -- Transactional Outbox (ADR-0003)
            CREATE TABLE IF NOT EXISTS outbox (
                event_id   TEXT PRIMARY KEY,
                payload    TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL
            );
            """
        )


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


# --------------------------------------------------------------------------- #
# Contratos
# --------------------------------------------------------------------------- #
class EntryIn(BaseModel):
    merchant_id: str = Field(..., min_length=1)
    type: str
    amount: float
    currency: str = "BRL"
    entry_date: date
    description: str | None = None

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        v = v.upper()
        if v not in ("CREDIT", "DEBIT"):
            raise ValueError("type deve ser CREDIT ou DEBIT")
        return v

    @field_validator("amount")
    @classmethod
    def _amount_ok(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount deve ser > 0 (a natureza vem de type)")
        return v


class EntryOut(BaseModel):
    id: str
    merchant_id: str
    type: str
    amount: float
    currency: str
    entry_date: str
    description: str | None
    created_at: str


# --------------------------------------------------------------------------- #
# Caso de uso: registrar lancamento (transacao local + outbox)
# --------------------------------------------------------------------------- #
def register_entry(payload: EntryIn) -> tuple[dict, dict]:
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": entry_id,
        "merchant_id": payload.merchant_id,
        "type": payload.type,
        "amount": payload.amount,
        "currency": payload.currency,
        "entry_date": payload.entry_date.isoformat(),
        "description": payload.description,
        "created_at": now,
    }
    # Evento de dominio (contrato — fronteira anti-corrupcao)
    event = {
        "event_id": entry_id,  # determinístico: 1 evento por lançamento
        "event_type": "CashFlowEntryRegistered",
        "occurred_at": now,
        "data": {
            "entry_id": entry_id,
            "merchant_id": payload.merchant_id,
            "type": payload.type,
            "amount": payload.amount,
            "currency": payload.currency,
            "entry_date": payload.entry_date.isoformat(),
        },
    }
    with conn() as c:
        c.execute(
            "INSERT INTO cash_flow_entry VALUES (:id,:merchant_id,:type,:amount,"
            ":currency,:entry_date,:description,:created_at)",
            entry,
        )
        c.execute(
            "INSERT INTO outbox (event_id, payload, status, created_at) "
            "VALUES (?,?, 'PENDING', ?)",
            (event["event_id"], json.dumps(event), now),
        )
    return entry, event


# --------------------------------------------------------------------------- #
# Rotas
# --------------------------------------------------------------------------- #
@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict:
    with conn() as c:
        c.execute("SELECT 1")
    return {"status": "ready", "db": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    with conn() as c:
        pending = c.execute(
            "SELECT COUNT(*) FROM outbox WHERE status='PENDING'"
        ).fetchone()[0]
        total = c.execute("SELECT COUNT(*) FROM cash_flow_entry").fetchone()[0]
    body = (
        f"# HELP outbox_pending Eventos gravados e ainda nao publicados\n"
        f"outbox_pending {pending}\n"
        f"# HELP entries_total Lancamentos registrados\n"
        f"entries_total {total}\n"
    )
    return Response(content=body, media_type="text/plain")


@app.post("/entries", response_model=EntryOut, status_code=201)
def create_entry(payload: EntryIn) -> EntryOut:
    try:
        entry, _event = register_entry(payload)
    except sqlite3.Error as exc:  # pragma: no cover - erro de infra
        raise HTTPException(status_code=500, detail=str(exc))
    return EntryOut(**entry)


@app.get("/entries", response_model=list[EntryOut])
def list_entries(
    merchant_id: str = Query(...),
    date_: date | None = Query(None, alias="date"),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
) -> list[EntryOut]:
    q = "SELECT * FROM cash_flow_entry WHERE merchant_id = ?"
    args: list = [merchant_id]
    if date_:
        q += " AND entry_date = ?"
        args.append(date_.isoformat())
    if from_:
        q += " AND entry_date >= ?"
        args.append(from_.isoformat())
    if to:
        q += " AND entry_date <= ?"
        args.append(to.isoformat())
    q += " ORDER BY entry_date, created_at"
    with conn() as c:
        rows = c.execute(q, args).fetchall()
    return [EntryOut(**dict(r)) for r in rows]
