import logging

from django.conf import settings

from bazis.contrib.async_background.broker import get_broker_for_consumer
from bazis.contrib.async_background.schemas import KafkaTask, TaskStatus
from bazis.contrib.async_background.utils import set_and_publish_status_async

from .schemas import DemoPayload


logger = logging.getLogger(__name__)


_subscriber_kwargs: dict[str, object] = {
    "auto_offset_reset": settings.KAFKA_AUTO_OFFSET_RESET,
    "auto_commit": settings.KAFKA_ENABLE_AUTO_COMMIT,
    "auto_commit_interval_ms": settings.KAFKA_AUTO_COMMIT_INTERVAL_MS,
}
if settings.KAFKA_GROUP_ID:
    _subscriber_kwargs["group_id"] = settings.KAFKA_GROUP_ID


@get_broker_for_consumer().subscriber(settings.KAFKA_TOPIC_ASYNC_REQUEST, **_subscriber_kwargs)
async def consumer_demo_tasks(task: KafkaTask[DemoPayload]):
    await set_and_publish_status_async(
        task_id=task.task_id,
        channel_name=task.channel_name,
        status=TaskStatus.PROCESSING,
    )

    response = {
        "task_id": task.task_id,
        "status": 200,
        "response": {"echo": task.payload.model_dump()},
    }

    await set_and_publish_status_async(
        task_id=task.task_id,
        channel_name=task.channel_name,
        status=TaskStatus.COMPLETED,
        response=response,
    )

    logger.info("Processed demo task_id=%s", task.task_id)
