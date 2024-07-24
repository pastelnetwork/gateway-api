#!/bin/bash

# Source the sensitive environment variables
if [ -f "/scripts/.env_sensitive" ]; then
    source /scripts/.env_sensitive
fi

# Start pasteld daemon
~/pastel/pasteld -daemon

# Start your application here
cd /app
poetry config virtualenvs.create true
poetry run pip install setuptools wheel
poetry run pip install secp256k1==0.14.0 --no-use-pep517
poetry install --no-interaction --no-ansi --no-root

poetry run alembic upgrade head

ipfs daemon --routing=dhtclient &
env $(cat /scripts/.env_sensitive | xargs) poetry run gunicorn -k 'uvicorn.workers.UvicornWorker' -c gunicorn_conf.py app.main:app &
env $(cat /scripts/.env_sensitive | xargs) poetry run celery -A app.main.celery worker -Q cascade,sense,nft,collection -n worker1@%h --loglevel=info &
env $(cat /scripts/.env_sensitive | xargs) poetry run celery -A app.main.celery worker -Q registration_helpers -n worker2@%h --loglevel=info &
env $(cat /scripts/.env_sensitive | xargs) poetry run celery -A app.main.celery beat -l info &

# Keep the container running
tail -f /dev/null