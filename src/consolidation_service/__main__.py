"""Worker de consolidacao: consome eventos do transporte e aplica o agregado.

Roda como thread no consolidation-service (o processo tambem serve a API de
consulta). Em producao, worker e API podem ser escalados independentemente
(competing consumers — ADR-0004).
"""
from __future__ import annotations

import os
import threading

from common.events import get_transport
from consolidation_service.app import apply_event, init_db


def run_worker(stop: threading.Event) -> None:
    transport = get_transport()
    init_db()
    transport.consume(apply_event, stop=stop)


def main() -> None:
    import uvicorn

    stop = threading.Event()
    t = threading.Thread(target=run_worker, args=(stop,), daemon=True)
    t.start()
    try:
        uvicorn.run(
            "consolidation_service.app:app",
            host="0.0.0.0",
            port=int(os.environ.get("PORT", "8002")),
        )
    finally:
        stop.set()


if __name__ == "__main__":
    main()
