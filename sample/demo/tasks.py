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

from django.conf import settings

from bazis.contrib.async_background.broker import get_broker_for_consumer, subscriber_kwargs
from bazis.contrib.async_background.schemas import KafkaTask, TaskStatus
from bazis.contrib.async_background.utils import set_and_publish_status_async

from .schemas import DemoPayload


logger = logging.getLogger(__name__)


@get_broker_for_consumer().subscriber(settings.KAFKA_TOPIC_ASYNC_BG, **subscriber_kwargs())
async def consumer_demo_tasks(task: KafkaTask[DemoPayload]):
    await set_and_publish_status_async(
        task_id=task.task_id,
        channel_name=task.channel_name,
        status=TaskStatus.PROCESSING,
    )

    response = {
        "task_id": task.task_id,
        "status": 200,
        "response": {"echo": task.payload.model_dump()},
    }

    await set_and_publish_status_async(
        task_id=task.task_id,
        channel_name=task.channel_name,
        status=TaskStatus.COMPLETED,
        response=response,
    )

    logger.info("Processed demo task_id=%s", task.task_id)
