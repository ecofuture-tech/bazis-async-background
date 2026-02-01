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
import random
from contextlib import asynccontextmanager

from django.conf import settings

from faststream import FastStream
from faststream.kafka import KafkaBroker


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
