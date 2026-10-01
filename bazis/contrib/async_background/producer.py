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

import logging
from uuid import uuid4

from pydantic import BaseModel

from bazis.contrib.async_background.broker import get_started_broker_for_async
from bazis.contrib.async_background.schemas import KafkaTask, TaskStatus
from bazis.contrib.async_background.utils import set_and_publish_status_async


logger = logging.getLogger(__name__)


async def publish_message(topic_name: str, message: dict, partition_marker: str | None = None):
    """
    Publishes a message to a Kafka topic (the producer gives up after
    KAFKA_PUBLISH_TIMEOUT_SEC).
    """
    broker = await get_started_broker_for_async()
    await broker.publish(
        message,
        topic_name,
        key=partition_marker.encode('utf-8') if partition_marker else None,
    )


async def enqueue_task_async[Payload: BaseModel](
    *,
    topic_name: str,
    channel_name: str,
    payload: Payload,
    partition_marker: str | None = None,
) -> KafkaTask[Payload]:
    """
    Registers a task (status `pending`), publishes it to Kafka and returns it.
    If publishing fails, the status is `failed` and the error is raised.
    """
    task_id = str(uuid4())
    message = KafkaTask[Payload](
        task_id=task_id,
        channel_name=channel_name,
        payload=payload,
    )

    # the status is pending before the publication: a consumer may process the task and
    # store its result before the publication returns, which a later status would overwrite
    await set_and_publish_status_async(
        task_id=task_id,
        channel_name=channel_name,
        status=TaskStatus.PENDING,
    )

    try:
        await publish_message(topic_name, message.model_dump(mode='json'), partition_marker)
    except Exception:
        # after a timeout the message may still have been delivered: a consumer can then
        # process the task and replace this status
        logger.exception('Kafka publish failed for task %s.', task_id)
        await set_and_publish_status_async(
            task_id=task_id,
            channel_name=channel_name,
            status=TaskStatus.FAILED,
            response={'error': 'The task could not be queued'},
        )
        raise
    return message
