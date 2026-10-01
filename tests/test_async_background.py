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

import pytest
from bazis_test_utils.utils import get_api_client
from faststream import AckPolicy

from bazis.contrib.async_background import broker as broker_module
from bazis.contrib.async_background import producer as producer_module
from bazis.contrib.async_background.schemas import TaskStatus
from bazis.contrib.async_background.utils import (
    redis,
    set_and_publish_status,
    task_key,
)
from bazis.contrib.ws.utils import get_anonymous_channel


TOKEN = 'anonymous-token-0123456789'


def _store(task_id: str, channel_name: str, status=TaskStatus.COMPLETED, response=None):
    set_and_publish_status(task_id, channel_name, status, response)


def _get(app, task_id: str, token: str = TOKEN, **params):
    return get_api_client(app).get(
        f'/api/v1/async_background_response/{task_id}/',
        params=params,
        headers={'Authorization': f'Bearer {token}'},
    )


def test_result_of_own_task(sample_app):
    _store('task-1', get_anonymous_channel(TOKEN), response={'value': 1})

    response = _get(sample_app, 'task-1')
    assert response.status_code == 200
    assert response.json() == {'value': 1}

    response = _get(sample_app, 'task-1', full_response='true')
    assert response.json()['status'] == 'completed'


def test_result_not_ready(sample_app):
    _store('task-2', get_anonymous_channel(TOKEN), status=TaskStatus.PENDING)
    assert _get(sample_app, 'task-2').json() == {'status': 'not ready'}


def test_result_of_foreign_task(sample_app):
    _store('task-3', get_anonymous_channel('other-anonymous-token-0123'))
    assert _get(sample_app, 'task-3').status_code == 403


def test_result_access_requires_token(sample_app):
    _store('task-4', get_anonymous_channel(TOKEN))
    response = get_api_client(sample_app).get('/api/v1/async_background_response/task-4/')
    assert response.status_code == 401
    # an anonymous token must be a valid anonymous token, not a channel name
    assert _get(sample_app, 'task-4', token='user_ws::1').status_code == 401


def test_result_unknown_task(sample_app):
    assert _get(sample_app, 'missing-task').status_code == 404


def test_task_id_cannot_address_other_keys(sample_app):
    """
    The statuses live under their own prefix: a task id cannot read other keys of the cache.
    """
    redis.set('secret-key', json.dumps({'channel_name': get_anonymous_channel(TOKEN), 'response': 1}))
    assert _get(sample_app, 'secret-key').status_code == 404
    assert redis.get(task_key('secret-key')) is None


def test_status_is_published_to_the_channel():
    channel = get_anonymous_channel(TOKEN)
    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)
    try:
        _store('task-5', channel, status=TaskStatus.PROCESSING)
        for _ in range(50):
            if message := pubsub.get_message(timeout=0.1):
                break
        assert json.loads(message['data']) == {
            'status': 'processing',
            'task_id': 'task-5',
            'action': 'async_bg',
        }
    finally:
        pubsub.close()


def test_subscriber_kwargs(settings):
    settings.KAFKA_GROUP_ID = 'group'
    settings.KAFKA_ENABLE_AUTO_COMMIT = False
    settings.KAFKA_ACK_POLICY = 'nack_on_error'
    kwargs = broker_module.subscriber_kwargs(max_records=5)
    assert kwargs['ack_policy'] == AckPolicy.NACK_ON_ERROR

    settings.KAFKA_ACK_POLICY = 'reject_on_error'
    assert broker_module.subscriber_kwargs()['ack_policy'] == AckPolicy.ACK
    assert kwargs['group_id'] == 'group'
    assert kwargs['max_records'] == 5
    assert 'auto_commit' not in kwargs

    settings.KAFKA_ENABLE_AUTO_COMMIT = True
    assert broker_module.subscriber_kwargs()['ack_policy'] == AckPolicy.ACK_FIRST


def test_consumer_lifetime(settings):
    settings.KAFKA_CONSUMER_LIFETIME_SEC = None
    settings.KAFKA_CONSUMER_LIFETIME_JITTER_SEC = None
    # 2.2 failed to start a consumer without a lifetime: None + randint(0, None)
    broker_module.build_app()
    assert broker_module.consumer_lifetime() is None

    settings.KAFKA_CONSUMER_LIFETIME_SEC = 10
    assert broker_module.consumer_lifetime() == 10
    settings.KAFKA_CONSUMER_LIFETIME_JITTER_SEC = 5
    assert 10 <= broker_module.consumer_lifetime() <= 15


def test_consumer_stops_after_lifetime():
    class FakeApp:
        exits = 0

        def exit(self):
            FakeApp.exits += 1

    start_timer, stop_timer = broker_module.lifetime_hooks(FakeApp(), 0.2)

    async def run(wait):
        await start_timer()
        await asyncio.sleep(wait)
        await stop_timer()

    asyncio.run(run(0.4))
    assert FakeApp.exits == 1
    # stopped before the lifetime is over: the timer is cancelled
    asyncio.run(run(0.05))
    assert FakeApp.exits == 1


def test_concurrent_first_publishes(monkeypatch, settings):
    """
    Two requests publishing at the same time on a new event loop: 2.2 held a threading
    lock across the start of the broker and blocked the event loop.
    """
    settings.KAFKA_PUBLISH_TIMEOUT_SEC = 5
    published = []

    class FakeBroker:
        starts = 0

        async def start(self):
            FakeBroker.starts += 1
            await asyncio.sleep(0.1)

        async def publish(self, message, topic, key=None):
            published.append((topic, key))

    monkeypatch.setattr(broker_module, '_new_broker', FakeBroker)

    async def main():
        await asyncio.wait_for(
            asyncio.gather(
                producer_module.publish_message('topic', {'a': 1}, 'key-1'),
                producer_module.publish_message('topic', {'a': 2}),
            ),
            timeout=5,
        )

    asyncio.run(main())
    assert FakeBroker.starts == 1
    assert sorted(published, key=str) == [('topic', None), ('topic', b'key-1')]


def test_enqueue_failure_marks_the_task_failed(monkeypatch):
    async def failing_publish(*args, **kwargs):
        raise ConnectionError('Kafka is down')

    monkeypatch.setattr(producer_module, 'publish_message', failing_publish)

    from demo.schemas import DemoPayload

    async def main():
        return await producer_module.enqueue_task_async(
            topic_name='topic',
            channel_name=get_anonymous_channel(TOKEN),
            payload=DemoPayload(message='hello'),
        )

    with pytest.raises(ConnectionError):
        asyncio.run(main())

    keys = [k for k in redis.scan_iter(f'{task_key("")}*')]
    statuses = {json.loads(redis.get(k))['status'] for k in keys}
    assert 'failed' in statuses


@pytest.fixture(autouse=True)
def _clean_redis():
    for key in redis.scan_iter(f'{task_key("")}*'):
        redis.delete(key)
    redis.delete('secret-key')
    yield


def test_brokers_of_closed_loops_are_dropped(monkeypatch):
    """
    The broker of an event loop refers to it: it is released when another loop needs one.
    """

    class FakeBroker:
        async def start(self): ...

    monkeypatch.setattr(broker_module, '_new_broker', FakeBroker)
    broker_module._brokers_by_loop.clear()

    for _ in range(3):
        asyncio.run(broker_module.get_started_broker_for_async())
    assert len(broker_module._brokers_by_loop) == 1
