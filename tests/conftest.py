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
