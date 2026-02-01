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
import os
import time

import pytest

from bazis.contrib.async_background.utils import redis


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_stack_only():
    if os.environ.get("PYTEST_IN_DOCKER") != "1":
        pytest.fail("Run tests only via docker compose (PYTEST_IN_DOCKER=1).")
    time.sleep(2)
    yield


@pytest.fixture
def process_async_response():
    def _run(task_id: str, timeout: int = 45) -> dict:
        for _ in range(timeout):
            if redis_data := redis.get(task_id):
                data_dict = json.loads(redis_data.decode("utf-8"))
                if data_dict.get("status") == "completed":
                    return data_dict
            time.sleep(1)
        pytest.fail(f"Timeout waiting for async_background_response for task_id={task_id}")

    return _run


@pytest.fixture(scope="function")
def sample_app():
    from sample.main import app
    return app
