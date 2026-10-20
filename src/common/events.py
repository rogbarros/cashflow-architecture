"""Abstracao de transporte de eventos.

O dominio nao conhece o broker. Trocar RabbitMQ por SQS/Kafka nao deve
tocar a logica de negocio (ADR-0004). Aqui oferecemos duas implementacoes:

- FileTransport: fila durável em arquivo (JSONL) — roda SEM Docker.
- RabbitTransport: AMQP real via pika — usado no docker-compose.

Ambas entregam AT-LEAST-ONCE; o consumidor e idempotente (ADR-0005).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable

QUEUE_DIR = Path(os.environ.get("EVENT_QUEUE_DIR", "event_queue"))
QUEUE_FILE = QUEUE_DIR / "events.jsonl"
DLQ_FILE = QUEUE_DIR / "dlq.jsonl"


class FileTransport:
    """Fila durável em arquivo: append no produtor, leitura sequencial no consumidor.

    Simula um broker persistente para ambientes sem Docker. O contrato e o
    mesmo do RabbitTransport (publish / consume), provando o desacoplamento.
    """

    name = "file"

    def __init__(self) -> None:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def publish(self, event: dict) -> None:
        with self._lock:
            with QUEUE_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")

    def consume(self, handler: Callable[[dict], None],
                poll_interval: float = 0.5,
                stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        offset = 0
        while not stop.is_set():
            if not QUEUE_FILE.exists():
                time.sleep(poll_interval)
                continue
            with self._lock:
                lines = QUEUE_FILE.read_text(encoding="utf-8").splitlines()
            for line in lines[offset:]:
                if not line.strip():
                    continue
                try:
                    handler(json.loads(line))
                except Exception as exc:  # falha -> DLQ (nao some)
                    self._to_dlq(line, exc)
                offset += 1
            time.sleep(poll_interval)

    def depth(self) -> int:
        if not QUEUE_FILE.exists():
            return 0
        with self._lock:
            return sum(1 for l in QUEUE_FILE.read_text("utf-8").splitlines() if l.strip())

    def _to_dlq(self, raw: str, exc: Exception) -> None:
        with DLQ_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"raw": raw, "error": str(exc)}) + "\n")

    def dlq_depth(self) -> int:
        if not DLQ_FILE.exists():
            return 0
        return sum(1 for l in DLQ_FILE.read_text("utf-8").splitlines() if l.strip())


class RabbitTransport:
    """Transporte AMQP real (RabbitMQ). Usado no docker-compose."""

    name = "rabbit"

    def __init__(self) -> None:
        import pika  # import tardio: so existe quando RabbitMQ e usado

        url = os.environ.get("RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/%2F")
        params = pika.URLParameters(url)
        self._params = params
        self._queue = os.environ.get("EVENT_QUEUE", "cashflow.events")
        self._dlq = self._queue + ".dlq"

    def publish(self, event: dict) -> None:
        import pika

        conn = pika.BlockingConnection(self._params)
        try:
            ch = conn.channel()
            ch.queue_declare(queue=self._queue, durable=True)
            ch.basic_publish(
                exchange="",
                routing_key=self._queue,
                body=json.dumps(event).encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),  # persistente
            )
        finally:
            conn.close()

    def consume(self, handler: Callable[[dict], None],
                poll_interval: float = 0.0,
                stop: threading.Event | None = None) -> None:
        import pika

        conn = pika.BlockingConnection(self._params)
        ch = conn.channel()
        ch.queue_declare(queue=self._queue, durable=True)
        ch.queue_declare(queue=self._dlq, durable=True)
        ch.basic_qos(prefetch_count=10)

        def _on_message(channel, method, _props, body):
            try:
                handler(json.loads(body))
                channel.basic_ack(method.delivery_tag)
            except Exception as exc:  # falha -> DLQ (nao some)
                channel.basic_publish(
                    exchange="",
                    routing_key=self._dlq,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2, headers={"error": str(exc)}),
                )
                channel.basic_ack(method.delivery_tag)

        ch.basic_consume(queue=self._queue, on_message_callback=_on_message)
        try:
            ch.start_consuming()
        finally:
            conn.close()

    def depth(self) -> int:
        import pika

        conn = pika.BlockingConnection(self._params)
        try:
            ch = conn.channel()
            ch.queue_declare(queue=self._queue, durable=True)
            return ch.queue_declare(queue=self._queue, durable=True, passive=True).method.message_count
        finally:
            conn.close()

    def dlq_depth(self) -> int:
        return 0


def get_transport() -> FileTransport | RabbitTransport:
    """Seleciona o transporte por variavel de ambiente (TRANSPORT=file|rabbit)."""
    if os.environ.get("TRANSPORT", "file").lower() == "rabbit":
        return RabbitTransport()
    return FileTransport()
