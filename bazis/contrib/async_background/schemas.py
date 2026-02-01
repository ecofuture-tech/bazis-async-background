from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Background task statuses."""

    CREATED = "created"  # The task is registered but has not yet been sent to Kafka
    PENDING = "pending"  # The message has been delivered to Kafka and is awaiting processing
    PROCESSING = "processing"  # The consumer has started processing
    COMPLETED = "completed"  # The task has completed successfully
    FAILED = "failed"  # An error occurred during execution


class KafkaTask[Payload: BaseModel](BaseModel):
    """Base schema for tasks processed by Kafka."""

    task_id: str = Field(..., description="Background task identifier")
    channel_name: str = Field(..., description="Channel name for status updates")
    payload: Payload

