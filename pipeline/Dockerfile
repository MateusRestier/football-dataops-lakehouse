FROM python:3.11-slim

WORKDIR /opt/dagster/app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python package (layer caching: deps before code)
# Context is the project root, so paths are relative to it
COPY pipeline/setup.py pipeline/setup.py
COPY pipeline/pipeline/ pipeline/pipeline/
RUN pip install --no-cache-dir -e pipeline/

# Copy Dagster config files into the image
COPY workspace.yaml workspace.yaml
RUN mkdir -p /opt/dagster/dagster_home
COPY dagster_home/dagster.yaml /opt/dagster/dagster_home/dagster.yaml

ENV DAGSTER_HOME=/opt/dagster/dagster_home
