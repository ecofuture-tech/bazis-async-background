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

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError, NoError
from django.conf import settings
from faststream import FastStream
from faststream.kafka import KafkaBroker

logger = logging.getLogger(__name__)


_brokers_by_loop_id: dict[int, KafkaBroker] = {}
_consumer_broker: KafkaBroker | None = None


def _new_broker() -> KafkaBroker:
    return KafkaBroker(settings.KAFKA_BOOTSTRAP_SERVERS)


def get_broker_for_async() -> KafkaBroker:
    loop_id = id(asyncio.get_running_loop())
    broker = _brokers_by_loop_id.get(loop_id)
    if broker is None:
        broker = _new_broker()
        _brokers_by_loop_id[loop_id] = broker
    return broker


def get_broker_for_consumer() -> KafkaBroker:
    global _consumer_broker
    if _consumer_broker is None:
        _consumer_broker = _new_broker()
    return _consumer_broker


@asynccontextmanager
async def lifespan_handler(app: FastStream | None = None):
    stop_task = asyncio.create_task(
        asyncio.sleep(
            settings.KAFKA_CONSUMER_LIFETIME_SEC +
            random.randint(0, settings.KAFKA_CONSUMER_LIFETIME_JITTER_SEC)
        )
    )
    yield
    stop_task.cancel()


def build_app() -> FastStream:
    return FastStream(get_broker_for_consumer(), lifespan=lifespan_handler)


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
                    "Error creating Kafka topic '%s': code=%s message=%s"
                    % (topic_name, error_code, error_message)
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
