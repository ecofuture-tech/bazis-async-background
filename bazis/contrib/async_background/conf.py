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

    KAFKA_TOPIC_ASYNC_REQUEST: str | None = Field(default=None, description="Kafka topic for async requests.")

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

    KAFKA_AUTO_COMMIT_INTERVAL_MS: int = Field(
        default=10000, description="Interval for auto-committing the offset if enable.auto.commit is enabled."
    )  # If KAFKA_ENABLE_AUTO_COMMIT is enabled

    KAFKA_PUBLISH_TIMEOUT_SEC: int = Field(
        default=10, description="Timeout in seconds for producing a message to Kafka."
    )

    @computed_field
    @property
    def KAFKA_ENABLED(self) -> bool: # noqa: N802
        return all(
            [
                self.KAFKA_BOOTSTRAP_SERVERS,
                self.KAFKA_TOPIC_ASYNC_REQUEST,
            ]
        )


settings = Settings()
