FROM python:3.11-slim

WORKDIR /opt/dagster/app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python package (layer caching: deps before code)
COPY setup.py setup.py
COPY pipeline/ pipeline/
RUN pip install --no-cache-dir -e .

# Workspace and dagster home are bind-mounted at runtime
