"""Teste de carga leve para validar o RNF-02 (50 req/s no consolidado).

Nao depende de Docker: publica N eventos direto no transporte e mede a
vazao do worker de consolidacao. Serve como evidencia do dimensionamento
(documentado em docs/05-nfr-strategy.md).

Uso:
    python -m tests.load_test 5000        # 5000 eventos
"""
from __future__ import annotations

import sys
import time
import uuid
from datetime import date

from common.events import get_transport
from consolidation_service.app import apply_event, init_db


def make_event(i: int, merchant: str = "LOAD") -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "CashFlowEntryRegistered",
        "occurred_at": f"2026-10-20T00:00:{i % 60:02d}+00:00",
        "data": {
            "entry_id": str(uuid.uuid4()),
            "merchant_id": merchant,
            "type": "CREDIT" if i % 2 == 0 else "DEBIT",
            "amount": 10.0,
            "currency": "BRL",
            "entry_date": date.today().isoformat(),
        },
    }


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    init_db()
    transport = get_transport()

    print(f"Publicando {n} eventos...")
    t0 = time.perf_counter()
    for i in range(n):
        transport.publish(make_event(i))
    t_pub = time.perf_counter() - t0
    print(f"  publicacao: {t_pub:.2f}s  ({n / t_pub:,.0f} msg/s)")

    print("Processando...")
    t0 = time.perf_counter()
    for i in range(n):
        apply_event(make_event(i))  # idempotente: ids novos a cada chamada
    t_proc = time.perf_counter() - t0
    print(f"  processamento: {t_proc:.2f}s  ({n / t_proc:,.0f} msg/s)")
    print()
    if n / t_proc >= 50:
        print("OK: vazao >= 50 msg/s (RNF-02 atendido nesta maquina).")
    else:
        print("ATENCAO: vazao < 50 msg/s; escalar workers (ver docs/05).")


if __name__ == "__main__":
    main()
