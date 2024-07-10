FROM python:3.9-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install latest IPFS
RUN wget https://dist.ipfs.tech/kubo/v0.29.0/kubo_v0.29.0_linux-amd64.tar.gz && \
    tar -xvzf kubo_v0.29.0_linux-amd64.tar.gz && \
    cd kubo && \
    bash install.sh && \
    cd .. && \
    rm -rf kubo kubo_v0.29.0_linux-amd64.tar.gz

WORKDIR /app

# Install Python dependencies
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi

COPY . /app

# Start IPFS
RUN ipfs init
CMD ipfs daemon --routing=dhtclient & \
    poetry run gunicorn -k "uvicorn.workers.UvicornWorker" -c gunicorn_conf.py app.main:app & \
    poetry run celery -A app.main.celery worker -Q cascade,sense,nft,collection -n worker1@%h --loglevel=info & \
    poetry run celery -A app.main.celery worker -Q registration_helpers -n worker2@%h --loglevel=info & \
    poetry run celery -A app.main.celery beat -l info

