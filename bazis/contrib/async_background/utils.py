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

import json
import logging

from django.conf import settings

from fastapi import Request

from redis import Redis

from bazis.contrib.ws.utils import (
    UserError,
    get_anonymous_channel,
    get_redis_async,
    get_user_from_token_async,
    is_user_token,
)

from .schemas import TaskStatus


logger = logging.getLogger(__name__)

redis = Redis.from_url(settings.CACHES['default']['LOCATION'])

#: the statuses of the tasks are stored under their own prefix: a bare task id from the URL
#: addressed any key of the cache database
TASK_KEY_PREFIX = 'async_bg:task:'


class StatusStorageError(Exception):
    """Error when setting or publishing status in Redis."""


class ChannelNameError(Exception):
    """Error when resolving channel name."""


def task_key(task_id: str) -> str:
    return f'{TASK_KEY_PREFIX}{task_id}'


def _status_data(channel_name: str, status: TaskStatus, response: dict | None) -> str:
    return json.dumps(
        {'status': status.value, 'channel_name': channel_name, 'response': response},
        ensure_ascii=False,
    )


def _status_message(task_id: str, status: TaskStatus) -> str:
    return json.dumps(
        {'status': status.value, 'task_id': task_id, 'action': 'async_bg'}, ensure_ascii=False
    )


def set_and_publish_status(
    task_id: str, channel_name: str, status: TaskStatus, response: dict | None = None
) -> None:
    """
    Saves the task status in Redis and publishes a minimal status to the WS channel.
    """
    try:
        redis.set(
            task_key(task_id),
            _status_data(channel_name, status, response),
            ex=settings.KAFKA_RESPONSE_HOLD_SEC,
        )
    except Exception as err:
        logger.exception('Failed to set task %s in Redis', task_id)
        raise StatusStorageError(f'Redis set failed: {err}') from err

    try:
        redis.publish(channel_name, _status_message(task_id, status))
    except Exception as err:
        logger.exception('Failed to publish to channel for task %s', task_id)
        raise StatusStorageError(f'Redis publish failed: {err}') from err


async def set_and_publish_status_async(
    task_id: str, channel_name: str, status: TaskStatus, response: dict | None = None
) -> None:
    """
    The asynchronous version of `set_and_publish_status` (an asyncio Redis client, so that
    the statuses of concurrent tasks are not serialized through one thread).
    """
    client = get_redis_async()
    try:
        await client.set(
            task_key(task_id),
            _status_data(channel_name, status, response),
            ex=settings.KAFKA_RESPONSE_HOLD_SEC,
        )
    except Exception as err:
        logger.exception('Failed to set task %s in Redis', task_id)
        raise StatusStorageError(f'Redis set failed: {err}') from err

    try:
        await client.publish(channel_name, _status_message(task_id, status))
    except Exception as err:
        logger.exception('Failed to publish to channel for task %s', task_id)
        raise StatusStorageError(f'Redis publish failed: {err}') from err

    logger.debug('Task %s: status %s published', task_id, status.value)


async def get_task_data_async(task_id: str) -> dict | None:
    """
    Returns the stored status of the task or None.
    """
    raw = await get_redis_async().get(task_key(task_id))
    if not raw:
        return None
    return json.loads(raw)


def _get_token_from_request(request: Request) -> str | None:
    authorization = request.headers.get('authorization')
    if not authorization or not authorization.lower().startswith('bearer '):
        return None
    return authorization.split(' ', 1)[1].strip() or None


async def resolve_channel_name_async(request: Request) -> str:
    """
    The WS channel of the client that sent the request: the channel of the user of a
    session JWT, or the channel of an anonymous token (see bazis-ws). The channel also
    identifies the owner of the task results.
    """
    token = _get_token_from_request(request)
    if not token:
        raise ChannelNameError('No valid token found in request for channel name resolution.')

    try:
        if is_user_token(token):
            user = await get_user_from_token_async(token)
            return user.user_channel
        return get_anonymous_channel(token)
    except UserError as exc:
        raise ChannelNameError(f'Failed to resolve the channel: {exc.message}') from exc
