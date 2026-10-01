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

from typing import Literal

from pydantic import Field, computed_field

from bazis.core.utils.schemas import BazisSettings


class Settings(BazisSettings):
    """Kafka configuration."""

    KAFKA_TASKS: list[str] = Field([], description="List of Kafka tasks to run.")

    KAFKA_LOG_LEVEL: str = Field(
        default="INFO", description="Logging level for Kafka (DEBUG, INFO, WARNING...)."
    )

    KAFKA_CONSUMER_LIFETIME_SEC: int | None = Field(
        default=None, description="Lifetime of the Kafka consumer (in seconds). For example, 7200."
    )  # TD: Try with rolling-update.

    KAFKA_CONSUMER_LIFETIME_JITTER_SEC: int | None = Field(
        default=None,
        description="Maximum random lifetime shift (jitter) in seconds. For example, 300.",
    )

    KAFKA_RESPONSE_HOLD_SEC: int = Field(
        default=86400, description="Time to hold the response for async requests (in seconds)."
    )

    KAFKA_BOOTSTRAP_SERVERS: str | None = Field(
        default=None, description="List of Kafka brokers separated by commas (for example, 'kafka1:9092,kafka2:9092')."
    )  # List of brokers polled to obtain the topic owner

    KAFKA_TOPIC_ASYNC_BG: str | None = Field(default=None, description="Kafka topic for async requests.")

    KAFKA_GROUP_ID: str | None = Field(default=None, description="Kafka consumer group for this service.")

    KAFKA_AUTO_OFFSET_RESET: str = Field(
        default="earliest",
        description="Behavior when there is no offset: earliest - from the beginning, latest - from the end.",
    )

    KAFKA_ENABLE_AUTO_COMMIT: bool = Field(
        default=False, description="Enable automatic committing of offsets (not recommended)."
    )
    # If you enable automatic commits, information about messages read via poll() will be automatically
    # committed to Kafka (moving the offset) at the interval auto.commit.interval.ms
    # This approach helps avoid frequent commits and reduce the load on Kafka, but it is not suitable for most of our
    # cases because:
    # 1) When the consumer crashes, information about the fact of processing messages since the last auto.commit.interval.ms
    # is lost, the offset for them does not have time to be moved by a commit, and after the consumer is restarted these messages will
    # be processed again.
    # 2) The commit that moves the offset for a message read via poll() may be sent to Kafka before the consumer
    # actually processes this message. This creates a risk that the consumer will not be able to process the message successfully,
    # and Kafka will have already advanced the offset for this message.

    KAFKA_ACK_POLICY: Literal['ack', 'reject_on_error', 'nack_on_error'] = Field(
        default='reject_on_error',
        description=(
            'When the consumer commits a message (FastStream AckPolicy) without auto commit: '
            'reject_on_error - after processing, also when it failed (a failing message is not '
            'redelivered forever); nack_on_error - only after a successful processing (a '
            'failing message is redelivered at once and blocks its partition); ack - after '
            'processing.'
        ),
    )

    KAFKA_AUTO_COMMIT_INTERVAL_MS: int = Field(
        default=10000, description="Interval for auto-committing the offset if enable.auto.commit is enabled."
    )  # If KAFKA_ENABLE_AUTO_COMMIT is enabled

    KAFKA_PUBLISH_TIMEOUT_SEC: int = Field(
        default=10, description="Timeout in seconds for producing a message to Kafka."
    )

    KAFKA_ADMIN_TIMEOUT_MS: int = Field(
        default=2000,
        description="Timeout for Kafka admin operations (in milliseconds).",
    )
    KAFKA_AUTO_TOPIC_NUM_PARTITIONS: int = Field(
        default=15,
        description="Default number of partitions for automatically created topics.",
    )
    KAFKA_AUTO_TOPIC_REPLICATION_FACTOR: int = Field(
        default=1,
        description="Default replication factor for automatically created topics.",
    )
    KAFKA_CONSUMER_TIMEOUT_MS: int = Field(
        default=2000,
        description="Timeout for Kafka consumer polling (in milliseconds).",
    )
    KAFKA_FETCH_MIN_BYTES: int | None = Field(
        default=None,
        description="Minimum bytes the broker should accumulate before replying to fetch requests.",
    )
    KAFKA_FETCH_MAX_WAIT_MS: int | None = Field(
        default=None,
        description="Maximum wait time in milliseconds for fetch requests when the minimum bytes are not reached.",
    )

    @computed_field
    @property
    def KAFKA_ENABLED(self) -> bool: # noqa: N802
        return all(
            [
                self.KAFKA_BOOTSTRAP_SERVERS,
                self.KAFKA_TOPIC_ASYNC_BG,
            ]
        )


settings = Settings()
