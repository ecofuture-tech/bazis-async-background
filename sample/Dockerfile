# 1. Base stage
FROM python:3.13-slim-bookworm AS base

ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_BAZIS_ASYNC_BACKGROUND=0.0.0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

RUN apt-get update \
    && apt-get upgrade --yes \
    && apt-get install -y --no-install-recommends \
        binutils \
        build-essential \
        gdal-bin \
        git \
        libgdal-dev \
        python3-dev \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf \
        /var/lib/apt/lists/* \
        /usr/share/man \
        /usr/share/doc \
        /usr/share/doc-base

RUN pip install --upgrade pip uv --no-cache-dir

ENV WORKDIR=/app
WORKDIR $WORKDIR

# 2. Runtime stage
FROM base AS runtime

COPY bazis/ ${WORKDIR}/bazis/
COPY pyproject.toml ${WORKDIR}/
COPY sample/pyproject.toml sample/uv.lock ${WORKDIR}/sample/

WORKDIR ${WORKDIR}/sample
RUN uv sync --frozen

COPY sample/ ${WORKDIR}/sample/
COPY tests/ ${WORKDIR}/tests/

# 3. Test stage
FROM runtime AS test
