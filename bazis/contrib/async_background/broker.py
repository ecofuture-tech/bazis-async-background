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
import logging
import random
from contextlib import asynccontextmanager

from django.conf import settings

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import NoError, TopicAlreadyExistsError
from faststream import AckPolicy, FastStream
from faststream.kafka import KafkaBroker


logger = logging.getLogger(__name__)


_brokers_by_loop: dict[asyncio.AbstractEventLoop, KafkaBroker] = {}


def drop_closed_loops(registry: dict):
    """
    Removes the objects of closed event loops from a per-loop registry: the objects refer to
    their loop, so a weak registry would never release them.
    """
    for loop in [loop for loop in registry if loop.is_closed()]:
        del registry[loop]
_consumer_broker: KafkaBroker | None = None


def _new_broker() -> KafkaBroker:
    # the broker connects when it starts: the task modules can be imported without Kafka.
    # The publication is bounded by the request timeout of the producer: cancelling it from
    # outside would leave the message queued in the producer and delivered later
    return KafkaBroker(
        settings.KAFKA_BOOTSTRAP_SERVERS or 'localhost',
        request_timeout_ms=settings.KAFKA_PUBLISH_TIMEOUT_SEC * 1000,
    )


def get_broker_for_async() -> KafkaBroker:
    """
    Returns the (not started) publishing broker of the running event loop: a broker and
    its connections cannot be shared between event loops.
    """
    loop = asyncio.get_running_loop()
    broker = _brokers_by_loop.get(loop)
    if broker is None:
        drop_closed_loops(_brokers_by_loop)
        broker = _new_broker()
        _brokers_by_loop[loop] = broker
    return broker


def get_broker_for_consumer() -> KafkaBroker:
    """
    Returns the broker that the subscribers of the consumer process register on.
    """
    global _consumer_broker
    if _consumer_broker is None:
        _consumer_broker = _new_broker()
    return _consumer_broker


def subscriber_kwargs(**overrides) -> dict:
    """
    The arguments of `broker.subscriber(...)` from the KAFKA_* settings, for the installed
    FastStream (`auto_commit` was replaced by `ack_policy` in FastStream 0.6)::

        @get_broker_for_consumer().subscriber(settings.KAFKA_TOPIC_ASYNC_BG, **subscriber_kwargs())
        async def consumer(task: KafkaTask[MyPayload]): ...
    """
    kwargs: dict[str, object] = {
        'auto_offset_reset': settings.KAFKA_AUTO_OFFSET_RESET,
        'auto_commit_interval_ms': settings.KAFKA_AUTO_COMMIT_INTERVAL_MS,
        'consumer_timeout_ms': settings.KAFKA_CONSUMER_TIMEOUT_MS,
        'ack_policy': (
            AckPolicy.ACK_FIRST
            if settings.KAFKA_ENABLE_AUTO_COMMIT
            else AckPolicy(settings.KAFKA_ACK_POLICY)
        ),
    }
    if settings.KAFKA_GROUP_ID:
        kwargs['group_id'] = settings.KAFKA_GROUP_ID
    if settings.KAFKA_FETCH_MIN_BYTES is not None:
        kwargs['fetch_min_bytes'] = settings.KAFKA_FETCH_MIN_BYTES
    if settings.KAFKA_FETCH_MAX_WAIT_MS is not None:
        kwargs['fetch_max_wait_ms'] = settings.KAFKA_FETCH_MAX_WAIT_MS
    kwargs.update(overrides)
    return kwargs


def consumer_lifetime() -> float | None:
    """
    The lifetime of a consumer process in seconds (with a random jitter), or None.
    """
    if not settings.KAFKA_CONSUMER_LIFETIME_SEC:
        return None
    jitter = settings.KAFKA_CONSUMER_LIFETIME_JITTER_SEC or 0
    return settings.KAFKA_CONSUMER_LIFETIME_SEC + random.randint(0, jitter)


def lifetime_hooks(app: FastStream, lifetime: float):
    """
    Returns the hooks that start and cancel the timer which stops the application after
    its lifetime.
    """
    timer: dict[str, asyncio.Task] = {}

    async def stop_after_lifetime():
        await asyncio.sleep(lifetime)
        logger.info('Kafka consumer lifetime of %s s is over, stopping.', round(lifetime))
        app.exit()

    async def start_lifetime_timer():
        timer['task'] = asyncio.create_task(stop_after_lifetime())

    async def stop_lifetime_timer():
        if task := timer.get('task'):
            task.cancel()

    return start_lifetime_timer, stop_lifetime_timer


def build_app() -> FastStream:
    """
    The FastStream application of a consumer process. With KAFKA_CONSUMER_LIFETIME_SEC the
    application stops after its lifetime, and kafka_consumer_multiple starts a new process.
    """
    app = FastStream(get_broker_for_consumer())
    if lifetime := consumer_lifetime():
        start_timer, stop_timer = lifetime_hooks(app, lifetime)
        app.after_startup(start_timer)
        app.on_shutdown(stop_timer)
    return app


@asynccontextmanager
async def _get_admin_client():
    admin_client = AIOKafkaAdminClient(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        request_timeout_ms=settings.KAFKA_ADMIN_TIMEOUT_MS,
    )
    started = False
    try:
        await admin_client.start()
        started = True
        yield admin_client
    finally:
        if started:
            await admin_client.close()
        else:
            try:
                await admin_client.close()
            except Exception:
                logger.debug(
                    "Kafka admin client close failed after failed start.",
                    exc_info=True,
                )


async def ensure_topic_exists(
    topic_name: str,
    num_partitions: int | None = None,
    replication_factor: int | None = None,
) -> None:
    logger.info("Ensuring Kafka topic '%s' exists...", topic_name)

    resolved_num_partitions = num_partitions or settings.KAFKA_AUTO_TOPIC_NUM_PARTITIONS
    resolved_replication_factor = replication_factor or settings.KAFKA_AUTO_TOPIC_REPLICATION_FACTOR

    try:
        async with _get_admin_client() as admin_client:
            topics = await admin_client.list_topics()
            if topic_name in topics:
                logger.info("Kafka topic '%s' already exists.", topic_name)
                return

            new_topic = NewTopic(
                name=topic_name,
                num_partitions=resolved_num_partitions,
                replication_factor=resolved_replication_factor,
            )

            resp = await admin_client.create_topics([new_topic])

            for err in getattr(resp, "topic_errors", []):
                # err[0]/err[1]/err[2] topic/error_code/message
                error_code = err[1]
                if error_code == NoError.errno:
                    continue

                if error_code == TopicAlreadyExistsError.errno:
                    logger.info("Kafka topic '%s' already exists.", topic_name)
                    return

                error_message = err[2] if len(err) > 2 else None
                raise RuntimeError(
                    f"Error creating Kafka topic '{topic_name}': "
                    f"code={error_code} message={error_message}"
                )

        logger.info("Kafka topic '%s' created successfully.", topic_name)
    except TopicAlreadyExistsError:
        logger.info("Kafka topic '%s' already exists.", topic_name)
    except Exception:
        logger.exception("Error creating Kafka topic '%s'.", topic_name)
        raise


async def get_topics_by_prefix(
    prefix: str,
) -> list[str]:
    try:
        async with _get_admin_client() as admin_client:
            topics = await admin_client.list_topics()

        topics = [t for t in topics if t.startswith(prefix)]
        logger.info(
            "Found %d topics with prefix '%s': %s",
            len(topics),
            prefix,
            topics if topics else "none",
        )
        return topics
    except Exception:
        logger.exception("Kafka error while listing topics with prefix '%s'.", prefix)
        raise
