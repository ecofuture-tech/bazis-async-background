import asyncio
import random
from contextlib import asynccontextmanager

from django.conf import settings

from faststream import FastStream
from faststream.kafka import KafkaBroker


_brokers_by_loop_id: dict[int, KafkaBroker] = {}
_consumer_broker: KafkaBroker | None = None


def _new_broker() -> KafkaBroker:
    return KafkaBroker(settings.KAFKA_BOOTSTRAP_SERVERS)


def get_broker_for_async() -> KafkaBroker:
    loop_id = id(asyncio.get_running_loop())
    broker = _brokers_by_loop_id.get(loop_id)
    if broker is None:
        broker = _new_broker()
        _brokers_by_loop_id[loop_id] = broker
    return broker


def get_broker_for_consumer() -> KafkaBroker:
    global _consumer_broker
    if _consumer_broker is None:
        _consumer_broker = _new_broker()
    return _consumer_broker


@asynccontextmanager
async def lifespan_handler(app: FastStream | None = None):
    stop_task = asyncio.create_task(
        asyncio.sleep(
            settings.KAFKA_CONSUMER_LIFETIME_SEC +
            random.randint(0, settings.KAFKA_CONSUMER_LIFETIME_JITTER_SEC)
        )
    )
    yield
    stop_task.cancel()


def build_app() -> FastStream:
    return FastStream(get_broker_for_consumer(), lifespan=lifespan_handler)
