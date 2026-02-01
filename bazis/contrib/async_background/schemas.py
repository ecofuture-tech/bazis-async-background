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

