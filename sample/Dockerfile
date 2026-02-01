# 1. Base stage
FROM python:3.14-slim-bookworm AS base

ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_BAZIS_ASYNC_BACKGROUND=0.0.0     UV_SYSTEM_PYTHON=1     PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PYTHONIOENCODING=utf-8

RUN apt-get update     && apt-get upgrade --yes     && apt-get install -y --no-install-recommends         binutils         build-essential         gdal-bin         git         libgdal-dev         python3-dev     && apt-get autoremove -yqq --purge     && apt-get clean     && rm -rf         /var/lib/apt/lists/*         /usr/share/man         /usr/share/doc         /usr/share/doc-base

RUN pip install --upgrade pip uv --no-cache-dir

ENV WORKDIR=/app
WORKDIR $WORKDIR

# 2. Runtime stage
FROM base AS runtime

WORKDIR ${WORKDIR}/sample
COPY pyproject.toml ${WORKDIR}/
COPY bazis/ ${WORKDIR}/bazis/
COPY sample/pyproject.toml ${WORKDIR}/sample/
RUN uv sync

WORKDIR ${WORKDIR}
COPY ./ ${WORKDIR}

# 3. Test stage
FROM runtime AS test
