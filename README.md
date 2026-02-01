# Bazis Async Background

[![PyPI version](https://img.shields.io/pypi/v/bazis-async-background.svg)](https://pypi.org/project/bazis-async-background/)
[![Python Versions](https://img.shields.io/pypi/pyversions/bazis-async-background.svg)](https://pypi.org/project/bazis-async-background/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Core background task framework for Bazis. It provides Kafka broker helpers, task schemas, status storage in Redis, and a base API to retrieve task results.

## Quick Start

```bash
# Install the package
uv add bazis-async-background

# Configure environment variables / settings
INSTALLED_APPS='["bazis.contrib.async_background", ...]'
BAZIS_CONFIG_APPS='["bazis.contrib.async_background", ...]'

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS=localhost:9093
KAFKA_TOPIC_ASYNC_REQUEST=my_app_background_tasks
KAFKA_GROUP_ID=my_app_background
KAFKA_TASKS='["my_app.background.tasks"]'

# Run consumer in Kubernetes
python manage.py kafka_consumer_single

# Run multiple consumers locally
python manage.py kafka_consumer_multiple --consumers-count=5
```

## Table of Contents

- [Description](#description)
- [Requirements](#requirements)
- [Installation](#installation)
- [Architecture](#architecture)
- [Configuration](#configuration)
  - [Environment Variables / Settings](#environment-variables--settings)
  - [Route Registration](#route-registration)
- [Usage](#usage)
  - [Running Consumers](#running-consumers)
- [Examples](#examples)
- [License](#license)
- [Links](#links)

## Description

**Bazis Async Background** is a core package for running background tasks in the Bazis framework. It includes:

- **Kafka Producer** — sending tasks to Kafka queue
- **Kafka Consumer** — processing tasks from the queue
- **Redis storage** — storing task execution results
- **API endpoint** — retrieving results by task_id

## Requirements

- **Python**: 3.12+
- **bazis**: latest version
- **PostgreSQL**: 12+
- **Redis**: For storing results and caching
- **Kafka**: For task queue

## Installation

### Using uv (recommended)

```bash
uv add bazis-async-background
```

### Using pip

```bash
pip install bazis-async-background
```

## Running Tests

Run from the project root:

```bash
docker compose -f sample/docker-compose.test.yml up --build --exit-code-from bazis-async-background-pytest --attach bazis-async-background-pytest --attach bazis-async-background-consumer-test
```

This waits for the pytest container to finish and streams logs only from the Python containers, so test completion and output are easy to follow.

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ Background task request
       ▼
┌─────────────────────┐
│   API Endpoint      │
│ (Async Background)  │
└──────┬──────────────┘
       │ 1. Return task_id (202)
       │ 2. Send to Kafka
       ▼
┌─────────────────────┐
│   Kafka Topic       │
│ (async_background)  │
└──────┬──────────────┘
       │
       │ Consumer polls
       ▼
┌─────────────────────┐
│  Kafka Consumer     │
│  (Background Worker)│
└──────┬──────────────┘
       │ 3. Process task
       │ 4. Save result to Redis
       ▼
┌─────────────────────┐
│      Redis          │
│   (Results Store)   │
└──────┬──────────────┘
       │
       │ 5. GET /async_background_response/{task_id}/
       ▼
┌─────────────────────┐
│   API Endpoint      │
│   (Get Result)      │
└─────────────────────┘
```

## Configuration

### Environment Variables / Settings

Add to your `.env` or `settings.py`:

```bash
# Required settings
INSTALLED_APPS='["bazis.contrib.async_background", ...]'
BAZIS_CONFIG_APPS='["bazis.contrib.async_background", ...]'
KAFKA_TASKS='["my_app.background.tasks"]'

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS=localhost:9093
KAFKA_TOPIC_ASYNC_REQUEST=my_app_background_tasks
KAFKA_GROUP_ID=my_app_background

# Optional settings
KAFKA_CONSUMER_LIFETIME_SEC=900           # Consumer lifetime (15 minutes)
KAFKA_CONSUMER_LIFETIME_JITTER_SEC=180    # Random deviation (3 minutes)
KAFKA_AUTO_OFFSET_RESET=latest
KAFKA_ENABLE_AUTO_COMMIT=true
KAFKA_AUTO_COMMIT_INTERVAL_MS=5000
KAFKA_LOG_LEVEL=INFO
```

**Parameters**:

- `KAFKA_TASKS` — dotted module paths imported by the consumer to register tasks
- `KAFKA_BOOTSTRAP_SERVERS` — Kafka broker address
- `KAFKA_TOPIC_ASYNC_REQUEST` — topic for async tasks
- `KAFKA_GROUP_ID` — consumer group
- `KAFKA_CONSUMER_LIFETIME_SEC` — consumer working time before restart
- `KAFKA_CONSUMER_LIFETIME_JITTER_SEC` — random deviation to avoid simultaneous restart
- `KAFKA_AUTO_OFFSET_RESET` — Kafka auto offset reset policy
- `KAFKA_ENABLE_AUTO_COMMIT` — Kafka auto-commit toggle
- `KAFKA_AUTO_COMMIT_INTERVAL_MS` — auto-commit interval in ms
- `KAFKA_LOG_LEVEL` — log level for consumers

### Route Registration

Add the route for getting results to your `router.py`:

```python
from bazis.core.routing import BazisRouter

router = BazisRouter(prefix='/api/v1')

# Register background task results route
router.register('bazis.contrib.async_background.router')
```

This adds the endpoint: `GET /api/v1/async_background_response/{task_id}/`

## Usage

### Running Consumers

#### For Kubernetes (one consumer per pod)

```bash
python manage.py kafka_consumer_single
```

Runs one consumer that processes tasks from Kafka. Suitable for horizontal scaling in Kubernetes.

#### For Local Development (multiple consumers)

```bash
python manage.py kafka_consumer_multiple --consumers-count=5
```

Runs 5 consumers in separate processes. Suitable for local development or deployment without orchestration.

**Parameters**:

- `--consumers-count` — number of consumers to run (default: 1)

## Examples

### Minimal Task Registration

```python
from bazis.contrib.async_background.broker import get_broker_for_consumer
from bazis.contrib.async_background.schemas import KafkaTask, TaskStatus
from bazis.contrib.async_background.utils import set_and_publish_status_async
from pydantic import BaseModel


class DemoPayload(BaseModel):
    message: str


@get_broker_for_consumer().subscriber("my_app_background_tasks")
async def consumer_demo(task: KafkaTask[DemoPayload]):
    await set_and_publish_status_async(
        task_id=task.task_id,
        channel_name=task.channel_name,
        status=TaskStatus.COMPLETED,
        response={"echo": task.payload.model_dump()},
    )
```

## License

Apache License 2.0

See [LICENSE](LICENSE) file for details.

## Links

- [Bazis Documentation](https://github.com/ecofuture-tech/bazis) — main repository
- [Bazis Async Background Repository](https://github.com/ecofuture-tech/bazis-async-background) — package repository
- [Issue Tracker](https://github.com/ecofuture-tech/bazis-async-background/issues) — report bugs or request features
- [Apache Kafka](https://kafka.apache.org/) — Kafka documentation
