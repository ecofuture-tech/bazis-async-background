# bazis-async-background — guide for AI agents

Background tasks over Kafka (FastStream) for Bazis. An endpoint queues a task with
`enqueue_task_async` and returns its id; consumer processes run the task; the statuses are
stored in Redis and pushed to the WebSocket channel of the client (bazis-ws); the client
reads the result at `GET <router prefix>/async_background_response/{task_id}/`
(`/api/v1/...` with `BazisRouter(prefix='/api/v1')`).

## Setup

```bash
BS_INSTALLED_APPS='["bazis.contrib.async_background", ...]'
BS_KAFKA_BOOTSTRAP_SERVERS=kafka1:9092,kafka2:9092
BS_KAFKA_TOPIC_ASYNC_BG=myproject_async_background
BS_KAFKA_GROUP_ID=myproject
BS_KAFKA_TASKS='["myapp.tasks"]'        # modules the consumer imports
```

- Services: Kafka, and Redis as `BS_CACHES__DEFAULT__LOCATION` (statuses and pub/sub).
- If `BS_BAZIS_APPS` (or `BS_BAZIS_CONFIG_APPS`) is set, list
  `bazis.contrib.async_background` there, or its `KAFKA_*` settings do not exist.
- Register the result route: `router.register('bazis.contrib.async_background.router')`.
- Run consumers with the same settings as the API, from the directory of `manage.py`:
  `python manage.py kafka_consumer_single` (one process, e.g. per pod) or
  `python manage.py kafka_consumer_multiple --consumers-count=N` (default 15;
  `--restart-delay-sec` default 1.0, `--max-restarts` default unlimited). Without
  `KAFKA_BOOTSTRAP_SERVERS` and `KAFKA_TOPIC_ASYNC_BG` the consumer exits with an error.
  With `KAFKA_CONSUMER_LIFETIME_SEC` (+ `_JITTER_SEC`) a consumer exits after its lifetime;
  `kafka_consumer_multiple` starts a new one.

## Queue a task

```python
from django.conf import settings
from fastapi import Request
from bazis.contrib.async_background.producer import enqueue_task_async
from bazis.contrib.async_background.utils import ChannelNameError, resolve_channel_name_async
from bazis.core.errors import JsonApi401Exception

@router.post('/report/', status_code=202)
async def report(request: Request, payload: ReportPayload) -> dict:   # pydantic model
    try:
        channel_name = await resolve_channel_name_async(request)
    except ChannelNameError as err:
        raise JsonApi401Exception from err
    task = await enqueue_task_async(topic_name=settings.KAFKA_TOPIC_ASYNC_BG,
                                    channel_name=channel_name, payload=payload)
    return {'data': None, 'meta': {'task_id': task.task_id}}
```

`resolve_channel_name_async` reads `Authorization: Bearer <token>`: a session JWT gives the
user channel, any other token the anonymous channel of bazis-ws. Tasks with the same
`partition_marker` (the Kafka key) go to the same partition.

## Run a task (a module listed in `KAFKA_TASKS`)

```python
from django.conf import settings
from bazis.contrib.async_background.broker import get_broker_for_consumer, subscriber_kwargs
from bazis.contrib.async_background.schemas import KafkaTask, TaskStatus
from bazis.contrib.async_background.utils import set_and_publish_status_async

@get_broker_for_consumer().subscriber(settings.KAFKA_TOPIC_ASYNC_BG, **subscriber_kwargs())
async def run_report(task: KafkaTask[ReportPayload]):
    await set_and_publish_status_async(task_id=task.task_id, channel_name=task.channel_name,
                                       status=TaskStatus.PROCESSING)
    ...
    await set_and_publish_status_async(task_id=task.task_id, channel_name=task.channel_name,
                                       status=TaskStatus.COMPLETED, response={...})
```

## Results

- Statuses: `pending` (set before publishing), `processing`, `completed`, `failed`.
  Stored under `async_bg:task:<task_id>` for `KAFKA_RESPONSE_HOLD_SEC` (default 86400).
- The WS channel receives `{"status", "task_id", "action": "async_bg"}`, not the result.
- `GET /async_background_response/{task_id}/` needs the same token as the request that
  queued the task: no or invalid token 401, another channel 403, unknown task 404. It returns
  `response`, or `{"status": "not ready"}`; `?full_response=true` returns the stored status.

## Rules

- Set `KAFKA_GROUP_ID`: without a consumer group offsets are not committed and every
  consumer receives every task.
- Get the channel only from `resolve_channel_name_async`: it owns the results.
- A task sets its final status itself: on an exception, set `TaskStatus.FAILED` with a
  generic error, or the task stays `processing`. Do not store exception texts.
- Always pass `**subscriber_kwargs()` to `subscriber(...)`. With the default
  `KAFKA_ACK_POLICY=ack` a failed message is not redelivered; `nack_on_error` redelivers it
  and blocks its partition. `KAFKA_ENABLE_AUTO_COMMIT=true` can lose messages.
