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

from django.conf import settings

from fastapi import Request

from bazis.contrib.async_background.producer import enqueue_task_async
from bazis.contrib.async_background.utils import ChannelNameError, resolve_channel_name_async
from bazis.core.errors import JsonApi401Exception
from bazis.core.routing import BazisRouter

from .schemas import DemoPayload


router = BazisRouter(tags=["Demo"])


@router.post("/demo/enqueue/", status_code=202)
async def enqueue_demo(request: Request, payload: DemoPayload) -> dict:
    try:
        channel_name = await resolve_channel_name_async(request)
    except ChannelNameError as err:
        raise JsonApi401Exception from err

    message = await enqueue_task_async(
        topic_name=settings.KAFKA_TOPIC_ASYNC_REQUEST,
        channel_name=channel_name,
        payload=payload,
        partition_marker=channel_name,
    )
    return {"data": None, "meta": {"task_id": message.task_id}}
