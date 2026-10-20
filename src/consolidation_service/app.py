"""Consolidation Service — consome eventos e materializa o saldo diario.

Ponto arquitetural (ADR-0005): o consumidor e IDEMPOTENTE por event_id.
Receber o mesmo evento duas vezes nao duplica o agregado.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from fastapi import FastAPI, Query
from pydantic import BaseModel

DB_PATH = os.environ.get("CONSOLIDATION_DB", "consolidation.db")

app = FastAPI(
    title="Consolidation Service",
    version="1.0.0",
    description="Materializa o saldo diario a partir dos eventos de lancamento.",
)


def init_db() -> None:
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_balance (
                merchant_id  TEXT NOT NULL,
                date         TEXT NOT NULL,
                total_credit REAL NOT NULL DEFAULT 0,
                total_debit  REAL NOT NULL DEFAULT 0,
                balance      REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (merchant_id, date)
            );
            -- Controle de idempotencia (ADR-0005)
            CREATE TABLE IF NOT EXISTS processed_event (
                event_id     TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
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


class BalanceOut(BaseModel):
    merchant_id: str
    date: str
    total_credit: float
    total_debit: float
    balance: float


# --------------------------------------------------------------------------- #
# Consumo do evento (idempotente por event_id)
# --------------------------------------------------------------------------- #
def apply_event(event: dict) -> bool:
    """Aplica um evento de lancamento ao agregado. Retorna False se ja processado.

    A checagem de idempotencia e o upsert acontecem na MESMA transacao,
    para que reprocessamento concorrente seja seguro.
    """
    from datetime import datetime, timezone

    event_id = event["event_id"]
    data = event["data"]
    merchant_id = data["merchant_id"]
    day = data["entry_date"]
    amount = float(data["amount"])
    kind = data["type"]
    now = datetime.now(timezone.utc).isoformat()

    with conn() as c:
        row = c.execute(
            "SELECT 1 FROM processed_event WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row:  # ja processado -> ignora (efetivamente exactly-once)
            return False

        c.execute(
            "INSERT INTO daily_balance (merchant_id, date) VALUES (?, ?) "
            "ON CONFLICT(merchant_id, date) DO NOTHING",
            (merchant_id, day),
        )
        if kind == "CREDIT":
            c.execute(
                "UPDATE daily_balance SET total_credit = total_credit + ? "
                "WHERE merchant_id = ? AND date = ?",
                (amount, merchant_id, day),
            )
        else:
            c.execute(
                "UPDATE daily_balance SET total_debit = total_debit + ? "
                "WHERE merchant_id = ? AND date = ?",
                (amount, merchant_id, day),
            )
        c.execute(
            "UPDATE daily_balance SET balance = total_credit - total_debit "
            "WHERE merchant_id = ? AND date = ?",
            (merchant_id, day),
        )
        c.execute(
            "INSERT INTO processed_event (event_id, processed_at) VALUES (?, ?)",
            (event_id, now),
        )
    return True


def rebuild_balance(merchant_id: str, day: str, entries: list[dict]) -> None:
    """Rebuild do agregado a partir dos lancamentos (integridade — ADR-0007)."""
    credit = sum(e["amount"] for e in entries if e["type"] == "CREDIT")
    debit = sum(e["amount"] for e in entries if e["type"] == "DEBIT")
    with conn() as c:
        c.execute(
            "INSERT INTO daily_balance (merchant_id, date, total_credit, total_debit, balance) "
            "VALUES (?,?,?,?,?) ON CONFLICT(merchant_id, date) DO UPDATE SET "
            "total_credit=excluded.total_credit, total_debit=excluded.total_debit, "
            "balance=excluded.balance",
            (merchant_id, day, credit, debit, credit - debit),
        )


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
def metrics():
    from fastapi import Response

    with conn() as c:
        processed = c.execute("SELECT COUNT(*) FROM processed_event").fetchone()[0]
        days = c.execute("SELECT COUNT(*) FROM daily_balance").fetchone()[0]
    body = (
        f"events_processed_total {processed}\n"
        f"consolidated_days {days}\n"
    )
    return Response(content=body, media_type="text/plain")


@app.get("/balance", response_model=BalanceOut)
def get_balance(
    merchant_id: str = Query(...),
    date: str = Query(..., description="YYYY-MM-DD"),
) -> BalanceOut:
    with conn() as c:
        row = c.execute(
            "SELECT * FROM daily_balance WHERE merchant_id = ? AND date = ?",
            (merchant_id, date),
        ).fetchone()
    if not row:
        return BalanceOut(
            merchant_id=merchant_id, date=date,
            total_credit=0.0, total_debit=0.0, balance=0.0,
        )
    return BalanceOut(**dict(row))


@app.get("/balance/range", response_model=list[BalanceOut])
def get_balance_range(
    merchant_id: str = Query(...),
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
) -> list[BalanceOut]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM daily_balance WHERE merchant_id = ? AND date BETWEEN ? AND ? "
            "ORDER BY date",
            (merchant_id, from_, to),
        ).fetchall()
    return [BalanceOut(**dict(r)) for r in rows]
