# bazis-async-background

Background tasks over Kafka for Bazis (FastStream): `enqueue_task_async` stores the status of a task in
Redis and publishes it to a Kafka topic; consumer processes (`kafka_consumer_single` /
`kafka_consumer_multiple`) run the subscribers registered in the `KAFKA_TASKS` modules
(`subscriber_kwargs()` builds their arguments from the settings) and publish the statuses to
the WebSocket channel of the client (bazis-ws). `GET /async_background_response/{task_id}/`
returns the result to the owner of the channel.

The channel of a request is resolved by `resolve_channel_name_async` with the functions of
bazis-ws: an anonymous token must never address a user channel.

The package code is in `bazis/contrib/async_background`, the sample project used by the tests is in `sample/`,
the tests are in `tests/`.

## Running the tests

The tests need PostgreSQL with PostGIS and Redis and Kafka (see `.github/workflows/tests.yml`).
Run them from the `sample` directory:

```bash
cd sample
BS_DEBUG=true \
BS_SECRET_KEY=local-secret-key-that-is-long-enough-0123456789 \
BS_DATABASES__DEFAULT__HOST=localhost BS_DATABASES__DEFAULT__PORT=5432 \
BS_DATABASES__DEFAULT__NAME=bazis BS_DATABASES__DEFAULT__USER=postgres \
BS_DATABASES__DEFAULT__PASSWORD=postgres \
BS_CACHES__DEFAULT__LOCATION=redis://localhost:6379/1 \
BS_MEDIA_ROOT=/tmp/bazis/media BS_STATIC_ROOT=/tmp/bazis/static BS_WEBAPP_ROOT=/tmp/bazis/webapp \
BS_KAFKA_BOOTSTRAP_SERVERS=localhost:9092 BS_KAFKA_TOPIC_ASYNC_BG=sample_local_async_background \
BS_KAFKA_GROUP_ID=sample_local \
python manage.py migrate -v0
python -m pytest ../tests -o addopts="--reuse-db" -p no:cacheprovider
```

The tests use the database itself (`TEST.NAME` is the database name, the consumer shares it),
so migrate it first and run pytest with `--reuse-db`.

The tests marked `run_with_consumer` also need a running consumer (start it first, from `sample`, with
the same variables): `python manage.py kafka_consumer_single &`. Without Kafka settings they
are skipped. A local Kafka without Docker: download the Kafka binaries and start a single
KRaft node (`bin/kafka-storage.sh format ...`, `bin/kafka-server-start.sh
config/kraft/server.properties`).

Lint: `ruff check bazis tests sample`. CI also runs `python manage.py makemigrations --check
--dry-run` in `sample`: commit the migrations of model changes, including the sample apps.

## Releasing

A release is the tag `vX.Y.Z` on `main`: the Build and Publish workflow builds the package
(the version comes from the tag through setuptools-scm) and publishes it to PyPI
(pre-releases `-alphaN`/`-betaN`/`-rcN` go to Test PyPI) and creates the GitHub release.

Claude Code sessions cannot push tags. Release through the **Release** workflow instead:

1. Make sure the changes are merged into `main` and the Tests workflow is green on the
   `main` head commit (the Release workflow checks this and refuses otherwise).
2. Add the release notes as `docs/releases/X.Y.Z.md` in the change being released.
3. Start the workflow `release.yml` on `ref: main` with the input `version: X.Y.Z`
   (GitHub API: `POST /repos/ecofuture-tech/bazis-async-background/actions/workflows/release.yml/dispatches`;
   with the GitHub MCP tools: `actions_run_trigger`, method `run_workflow`).
4. The Release run creates the annotated tag and starts Build and Publish on it. Check
   that both runs succeed and that the version appears on https://pypi.org/project/bazis-async-background/.

Release the Bazis packages in dependency order: a package is tested in CI against the
versions of its Bazis dependencies published on PyPI. Pick the version by semver:
breaking changes (settings renamed or required, dependency removed, behavior changed)
bump the minor version while the project is below 3.0.
