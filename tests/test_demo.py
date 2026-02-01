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
