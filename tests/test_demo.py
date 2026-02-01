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

import pytest
from bazis_test_utils.utils import get_api_client


@pytest.mark.run_with_consumer
@pytest.mark.django_db(transaction=True)
def test_demo_enqueue_and_result(sample_app, process_async_response):
    channel_name = "test-channel"
    payload = {"message": "hello"}

    response = get_api_client(sample_app).post(
        "/api/v1/demo/enqueue/",
        data=json.dumps(payload),
        headers={
            "Authorization": f"Bearer {channel_name}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202
    task_id = response.json()["meta"]["task_id"]

    result = process_async_response(task_id)
    assert result["status"] == "completed"
    assert result["response"]["response"]["echo"] == payload

    response = get_api_client(sample_app).get(
        f"/api/v1/async_background_response/{task_id}/",
        headers={"Authorization": f"Bearer {channel_name}"},
    )
    assert response.status_code == 200
    assert response.json()["response"]["echo"] == payload
