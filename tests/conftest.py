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
import time

from django.conf import settings

import pytest

from bazis.contrib.async_background.utils import redis, task_key


def pytest_collection_modifyitems(config, items):
    """
    The tests marked `kafka` need a Kafka broker and a running consumer
    (`python manage.py kafka_consumer_single` in `sample`, see CLAUDE.md).
    """
    if settings.KAFKA_ENABLED:
        return
    skip = pytest.mark.skip(reason='Kafka is not configured (BS_KAFKA_BOOTSTRAP_SERVERS)')
    for item in items:
        if 'kafka' in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def process_async_response():
    def _run(task_id: str, timeout: int = 45) -> dict:
        for _ in range(timeout):
            if redis_data := redis.get(task_key(task_id)):
                data_dict = json.loads(redis_data)
                if data_dict.get('status') == 'completed':
                    return data_dict
            time.sleep(1)
        pytest.fail(f'Timeout waiting for async_background_response for task_id={task_id}')

    return _run


@pytest.fixture(scope='function')
def sample_app():
    from sample.main import app

    return app
