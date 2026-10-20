"""Testes da PoC — cobrem os cenarios arquiteturais centrais.

1. Contrato do lancamento (RF-01) e validacoes.
2. Publicacao de evento no outbox (ADR-0003).
3. Consumo assincrono e materializacao do saldo (RF-04/RF-05).
4. Idempotencia por event_id (RF-08 / ADR-0005).
5. CENARIO-CHAVE: consolidado indisponivel NAO derruba lancamentos (RNF-01).
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """Isola bancos e fila por teste (nao poluir o diretorio)."""
    monkeypatch.setenv("CASHFLOW_DB", str(tmp_path / "cf.db"))
    monkeypatch.setenv("CONSOLIDATION_DB", str(tmp_path / "cons.db"))
    monkeypatch.setenv("EVENT_QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.setenv("TRANSPORT", "file")

    # reimporta modulos para pegar os novos paths
    import importlib

    import common.events as events
    import cashflow_service.app as cf
    import consolidation_service.app as cons

    importlib.reload(events)
    importlib.reload(cf)
    importlib.reload(cons)
    cf.init_db()
    cons.init_db()
    yield cf, cons, events


def test_register_entry_returns_201(isolated):
    cf, _cons, _events = isolated
    client = TestClient(cf.app)
    r = client.post(
        "/entries",
        json={
            "merchant_id": "M1",
            "type": "CREDIT",
            "amount": 100.0,
            "entry_date": "2026-10-20",
            "description": "venda",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"]
    assert body["type"] == "CREDIT"
    assert body["amount"] == 100.0


def test_amount_must_be_positive(isolated):
    cf, _cons, _events = isolated
    client = TestClient(cf.app)
    r = client.post(
        "/entries",
        json={"merchant_id": "M1", "type": "DEBIT", "amount": -5, "entry_date": "2026-10-20"},
    )
    assert r.status_code == 422


def test_invalid_type_rejected(isolated):
    cf, _cons, _events = isolated
    client = TestClient(cf.app)
    r = client.post(
        "/entries",
        json={"merchant_id": "M1", "type": "FOO", "amount": 10, "entry_date": "2026-10-20"},
    )
    assert r.status_code == 422


def test_entry_creates_outbox_event(isolated):
    cf, _cons, _events = isolated
    client = TestClient(cf.app)
    client.post(
        "/entries",
        json={"merchant_id": "M1", "type": "CREDIT", "amount": 50, "entry_date": "2026-10-20"},
    )
    with cf.conn() as c:
        rows = c.execute("SELECT event_id, status FROM outbox").fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "PENDING"


def test_consolidation_materializes_balance(isolated):
    cf, cons, _events = isolated
    cf_client = TestClient(cf.app)
    # dois lancamentos
    for t, amt in (("CREDIT", 100.0), ("DEBIT", 30.0)):
        cf_client.post(
            "/entries",
            json={"merchant_id": "M1", "type": t, "amount": amt, "entry_date": "2026-10-20"},
        )
    # simula o consumo (sem broker): le do outbox e aplica
    with cf.conn() as c:
        payloads = [json.loads(r["payload"]) for r in c.execute("SELECT payload FROM outbox")]
    for p in payloads:
        cons.apply_event(p)

    cons_client = TestClient(cons.app)
    r = cons_client.get("/balance", params={"merchant_id": "M1", "date": "2026-10-20"})
    assert r.status_code == 200
    b = r.json()
    assert b["total_credit"] == 100.0
    assert b["total_debit"] == 30.0
    assert b["balance"] == 70.0


def test_idempotency_same_event_not_duplicated(isolated):
    cf, cons, _events = isolated
    cf_client = TestClient(cf.app)
    cf_client.post(
        "/entries",
        json={"merchant_id": "M1", "type": "CREDIT", "amount": 40, "entry_date": "2026-10-20"},
    )
    with cf.conn() as c:
        p = json.loads(c.execute("SELECT payload FROM outbox").fetchone()["payload"])

    assert cons.apply_event(p) is True   # primeira vez: aplica
    assert cons.apply_event(p) is False  # segunda vez: ignora (idempotente)

    cons_client = TestClient(cons.app)
    b = cons_client.get("/balance", params={"merchant_id": "M1", "date": "2026-10-20"}).json()
    assert b["total_credit"] == 40.0  # NAO duplicou


def test_key_scenario_consolidation_down_does_not_break_cashflow(isolated):
    """RNF-01: com o consumo parado, POST /entries continua retornando 201."""
    cf, _cons, _events = isolated
    client = TestClient(cf.app)
    # nenhum worker consumindo -> simula consolidado fora
    for i in range(5):
        r = client.post(
            "/entries",
            json={
                "merchant_id": "M1",
                "type": "CREDIT",
                "amount": 10 + i,
                "entry_date": "2026-10-20",
            },
        )
        assert r.status_code == 201  # lancamento segue aceito
    # eventos ficaram no outbox (backlog), nenhum perdido
    with cf.conn() as c:
        pending = c.execute(
            "SELECT COUNT(*) FROM outbox WHERE status='PENDING'"
        ).fetchone()[0]
    assert pending == 5
