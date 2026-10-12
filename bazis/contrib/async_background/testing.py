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

"""
Helpers of the tests of background tasks (pytest; bazis-async-request uses them too):

- the tests marked `run_with_consumer` need Kafka and a running consumer: without Kafka
  settings they are skipped, once the hook is imported into the conftest::

      from bazis.contrib.async_background.testing import pytest_collection_modifyitems  # noqa: F401

- `wait_for_task(task_id)` waits until the consumer has completed a task and returns its
  stored status, `wait_for_tasks()` until no task is pending or processing;
- `redis_client()` reads the stored statuses (`task_key(task_id)`), `delete_tasks()`
  deletes them.
"""

import json
import time
from functools import cache

from django.conf import settings

import pytest
from redis import Redis

from .utils import TASK_KEY_PREFIX, task_key


@cache
def redis_client() -> Redis:
    """
    A synchronous client of the Redis database of the statuses (the cache).
    """
    return Redis.from_url(settings.CACHES['default']['LOCATION'])


def pytest_collection_modifyitems(config, items):
    """
    Skips the tests marked `run_with_consumer` without Kafka settings.
    """
    if settings.KAFKA_ENABLED:
        return
    skip = pytest.mark.skip(reason='Kafka is not configured (BS_KAFKA_BOOTSTRAP_SERVERS)')
    for item in items:
        if 'run_with_consumer' in item.keywords:
            item.add_marker(skip)


def task_data(task_id: str) -> dict | None:
    """
    The stored status of a task, or None.
    """
    raw = redis_client().get(task_key(task_id))
    return json.loads(raw) if raw else None


def wait_for_task(task_id: str, timeout: float = 45) -> dict:
    """
    The stored status of a task once it is completed; fails the test after `timeout`
    seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (data := task_data(task_id)) and data['status'] == 'completed':
            return data
        time.sleep(0.5)
    pytest.fail(f'The task {task_id} was not completed in {timeout} seconds')


def stored_tasks() -> list[bytes]:
    """
    The keys of the stored statuses.
    """
    return list(redis_client().scan_iter(f'{TASK_KEY_PREFIX}*'))


def wait_for_tasks(timeout: float = 30) -> None:
    """
    Waits until no stored task is pending or processing (at most `timeout` seconds): a
    consumer that shares the test database must be done before a test ends.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = {
            json.loads(value)['status']
            for key in stored_tasks()
            if (value := redis_client().get(key))
        }
        if not statuses - {'completed', 'failed'}:
            return
        time.sleep(0.5)


def delete_tasks() -> None:
    """
    Deletes the stored statuses.
    """
    if keys := stored_tasks():
        redis_client().delete(*keys)
