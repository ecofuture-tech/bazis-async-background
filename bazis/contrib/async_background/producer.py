import asyncio
import logging
import threading
from uuid import uuid4

from pydantic import BaseModel

from bazis.contrib.async_background.broker import get_broker_for_async
from bazis.contrib.async_background.schemas import KafkaTask, TaskStatus
from bazis.contrib.async_background.utils import set_and_publish_status_async


logger = logging.getLogger(__name__)


async def enqueue_task_async[Payload: BaseModel](
    *,
    topic_name: str,
    channel_name: str,
    payload: Payload,
    partition_marker: str | None = None,
) -> KafkaTask[Payload]:
    task_id = str(uuid4())
    message = KafkaTask[Payload](
        task_id=task_id,
        channel_name=channel_name,
        payload=payload,
    )

    await set_and_publish_status_async(
        task_id=task_id,
        channel_name=channel_name,
        status=TaskStatus.CREATED,
    )

    try:
        producer = _get_kafka_producer(topic_name)
        await producer.send_one_message(
            message=message.model_dump(),
            partition_marker=partition_marker,
        )
    except Exception as err:
        await set_and_publish_status_async(
            task_id=task_id,
            channel_name=channel_name,
            status=TaskStatus.FAILED,
            response={"error": str(err)},
        )
        raise
    else:
        await set_and_publish_status_async(
            task_id=task_id,
            channel_name=channel_name,
            status=TaskStatus.PENDING,
        )
    return message


class _KafkaProducer:
    """FastStream Kafka producer with reusable connection lifecycle."""

    def __init__(self, topic_name: str) -> None:
        self.topic_name = topic_name
        self._start_lock = threading.Lock()
        self._started = False
        self._loop_id: int | None = None
        self._broker = None

    async def ensure_started(self) -> None:
        current_loop_id = id(asyncio.get_running_loop())
        if self._started and self._loop_id == current_loop_id:
            return
        with self._start_lock:
            current_loop_id = id(asyncio.get_running_loop())
            if self._started and self._loop_id == current_loop_id:
                return
            if self._started and self._loop_id != current_loop_id:
                self._started = False
                self._loop_id = None
                self._broker = None
            if self._broker is None:
                self._broker = get_broker_for_async()
            await self._broker.start()
            self._started = True
            self._loop_id = current_loop_id

    async def send_one_message(
        self,
        message: dict,
        partition_marker: str | None = None,
    ) -> None:
        """Sends a single message to Kafka."""
        await self.ensure_started()
        try:
            await self._broker.publish(
                message,
                self.topic_name,
                key=partition_marker.encode("utf-8") if partition_marker else None,
            )
        except Exception:
            logger.exception("Kafka publish failed.")
            raise


_producer_cache: dict[tuple[str | None, int], _KafkaProducer] = {}


def _get_kafka_producer(topic_name: str) -> _KafkaProducer:
    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = None
    cache_key = (topic_name, loop_id if loop_id is not None else threading.get_ident())
    producer = _producer_cache.get(cache_key)
    if producer is None:
        producer = _KafkaProducer(topic_name)
        _producer_cache[cache_key] = producer
    return producer
