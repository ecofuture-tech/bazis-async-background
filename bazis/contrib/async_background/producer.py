# Copyright 2026 EcoFuture Technology Services LLC and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
import weakref
from uuid import uuid4

from django.conf import settings

from pydantic import BaseModel

from faststream.kafka import KafkaBroker

from bazis.contrib.async_background.broker import get_broker_for_async
from bazis.contrib.async_background.schemas import KafkaTask, TaskStatus
from bazis.contrib.async_background.utils import set_and_publish_status_async


logger = logging.getLogger(__name__)


class _LoopProducer:
    """
    The started publishing broker of an event loop. The start is guarded by an asyncio
    lock: a threading lock held across `await broker.start()` blocked the event loop when
    two requests published at the same time.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._broker: KafkaBroker | None = None

    async def get_broker(self) -> KafkaBroker:
        if self._broker is None:
            async with self._lock:
                if self._broker is None:
                    broker = get_broker_for_async()
                    await broker.start()
                    self._broker = broker
        return self._broker


_producers: 'weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _LoopProducer]' = (
    weakref.WeakKeyDictionary()
)


def _get_producer() -> _LoopProducer:
    loop = asyncio.get_running_loop()
    producer = _producers.get(loop)
    if producer is None:
        producer = _producers[loop] = _LoopProducer()
    return producer


async def publish_message(topic_name: str, message: dict, partition_marker: str | None = None):
    """
    Publishes a message to a Kafka topic within KAFKA_PUBLISH_TIMEOUT_SEC.
    """
    broker = await _get_producer().get_broker()
    await asyncio.wait_for(
        broker.publish(
            message,
            topic_name,
            key=partition_marker.encode('utf-8') if partition_marker else None,
        ),
        timeout=settings.KAFKA_PUBLISH_TIMEOUT_SEC,
    )


async def enqueue_task_async[Payload: BaseModel](
    *,
    topic_name: str,
    channel_name: str,
    payload: Payload,
    partition_marker: str | None = None,
) -> KafkaTask[Payload]:
    """
    Registers a task (status `created`), publishes it to Kafka (`pending`) and returns it.
    If publishing fails, the status is `failed` and the error is raised.
    """
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
        await publish_message(topic_name, message.model_dump(mode='json'), partition_marker)
    except Exception as err:
        logger.exception('Kafka publish failed for task %s.', task_id)
        await set_and_publish_status_async(
            task_id=task_id,
            channel_name=channel_name,
            status=TaskStatus.FAILED,
            response={'error': 'The task could not be queued'},
        )
        raise err
    else:
        await set_and_publish_status_async(
            task_id=task_id,
            channel_name=channel_name,
            status=TaskStatus.PENDING,
        )
    return message
