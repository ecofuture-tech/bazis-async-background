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
import json
import logging

from django.conf import settings

from fastapi import Request

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from bazis.contrib.ws.utils import UserError, get_user_from_token_async

from .schemas import TaskStatus


logger = logging.getLogger(__name__)

redis = Redis.from_url(settings.CACHES['default']['LOCATION'])
_redis_async_by_loop: dict[int, AsyncRedis] = {}


def get_redis_async() -> AsyncRedis:
    loop_id = id(asyncio.get_running_loop())
    client = _redis_async_by_loop.get(loop_id)
    if client is None:
        client = AsyncRedis.from_url(settings.CACHES['default']['LOCATION'])
        _redis_async_by_loop[loop_id] = client
    return client


class StatusStorageError(Exception):
    """Error when setting or publishing status in Redis."""


class ChannelNameError(Exception):
    """Error when resolving channel name."""


def set_and_publish_status(
    task_id: str, channel_name: str, status: TaskStatus, response: dict | None = None
) -> None:
    """Saves the task status in Redis and publishes a minimal status to the WS channel."""
    try:
        # Save the full status in Redis (for subsequent retrieval of the result by task_id)
        redis.set(
            task_id,
            json.dumps(
                {
                    "status": status.value,
                    "channel_name": channel_name,
                    "response": response,
                },
                ensure_ascii=False,
            ),
            ex=settings.KAFKA_RESPONSE_HOLD_SEC,
        )
    except Exception as err:
        logger.exception("Failed to set task %s in Redis", task_id)
        raise StatusStorageError(f"Redis set failed: {err}") from err

    try:
        # Prepare a lightweight payload for publication via WebSocket
        redis.publish(
            channel_name,
            json.dumps(
                {
                    "status": status.value,
                    "task_id": task_id,
                    "action": "async_bg",
                },
                ensure_ascii=False,
            ),
        )

        logger.info(
            "Published WS message for task %s with status %s to channel %s",
            task_id,
            status.value,
            channel_name,
        )
    except Exception as err:
        logger.exception("Failed to publish to channel for task %s", task_id)
        raise StatusStorageError(f"Redis publish failed: {err}") from err


async def set_and_publish_status_async(
    task_id: str, channel_name: str, status: TaskStatus, response: dict | None = None
) -> None:
    from asgiref.sync import sync_to_async

    await sync_to_async(set_and_publish_status)(
        task_id,
        channel_name,
        status,
        response,
    )


def _get_token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ")[1].strip()


async def resolve_channel_name_async(request: Request) -> str:
    token = _get_token_from_request(request)

    if token and token.count('.') == 2:
        try:
            user = await get_user_from_token_async(token)
        except UserError as exc:
            raise ChannelNameError(
                f"Failed to get user from token: {exc.message}"
            ) from exc
        return user.user_channel
    elif token:
        return token
    else:
        raise ChannelNameError(
            "No valid token found in request for channel name resolution."
        )
