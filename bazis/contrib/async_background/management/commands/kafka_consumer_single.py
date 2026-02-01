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
import inspect
import logging
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from aiokafka.errors import KafkaConnectionError

from bazis.contrib.async_background.broker import build_app


logger = logging.getLogger(__name__)


def _get_consumer_logger(consumer_id: int) -> logging.Logger:
    consumer_logger = logging.getLogger(f"consumer_{consumer_id}")
    if not consumer_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - [consumer_id=%(consumer_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        consumer_logger.addHandler(handler)
        consumer_logger.setLevel(settings.KAFKA_LOG_LEVEL)
    return consumer_logger


def run_consumer(consumer_id: int) -> None:
    from bazis.core.app import app  # noqa: F401
    from bazis.core.router import router  # noqa: F401

    if not settings.KAFKA_TASKS:
        logger.warning("No Kafka tasks configured in settings.KAFKA_TASKS.")
        return

    for task_path in settings.KAFKA_TASKS:
        __import__(task_path)

    consumer_logger = _get_consumer_logger(consumer_id)
    consumer_logger.info("Starting consumer process", extra={"consumer_id": consumer_id})

    while True:
        try:
            broker_app = build_app()
            result = broker_app.run()
            if inspect.iscoroutine(result):
                asyncio.run(result)
            break
        except KafkaConnectionError as err:
            consumer_logger.warning(
                "Kafka not ready: %s. Retrying in 1s...",
                err,
                extra={"consumer_id": consumer_id},
            )
            time.sleep(1)
        except Exception as err:
            consumer_logger.exception(
                "Error while processing: %s",
                err,
                extra={"consumer_id": consumer_id},
            )
            sys.exit(1)
        finally:
            consumer_logger.info("Consumer process stopped", extra={"consumer_id": consumer_id})


class Command(BaseCommand):
    help = "Starts a single Kafka consumer (one process)."

    def handle(self, *args, **options) -> None:
        """Entry point of the Django command."""
        logger.info("Starting a single Kafka consumer...")
        run_consumer(consumer_id=1)
