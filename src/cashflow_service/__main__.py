"""Relay do Outbox: le eventos PENDING e publica no transporte.

Roda como thread no cashflow-service. Separar o relay do caminho de escrita
garante que o POST /entries nunca espere o broker (ADR-0002/0003).
"""
from __future__ import annotations

import json
import os
import threading
import time

from common.events import get_transport
from cashflow_service.app import conn, init_db


def run_relay(stop: threading.Event, interval: float = 0.5) -> None:
    transport = get_transport()
    init_db()
    while not stop.is_set():
        with conn() as c:
            rows = c.execute(
                "SELECT event_id, payload FROM outbox WHERE status='PENDING' "
                "ORDER BY created_at LIMIT 100"
            ).fetchall()
        for row in rows:
            try:
                transport.publish(json.loads(row["payload"]))
                with conn() as c:
                    c.execute(
                        "UPDATE outbox SET status='SENT' WHERE event_id=?",
                        (row["event_id"],),
                    )
            except Exception as exc:  # pragma: no cover - infra
                print(f"[relay] falha ao publicar {row['event_id']}: {exc}")
        time.sleep(interval)


def main() -> None:
    import uvicorn

    stop = threading.Event()
    t = threading.Thread(target=run_relay, args=(stop,), daemon=True)
    t.start()
    try:
        uvicorn.run(
            "cashflow_service.app:app",
            host="0.0.0.0",
            port=int(os.environ.get("PORT", "8001")),
        )
    finally:
        stop.set()


if __name__ == "__main__":
    main()
