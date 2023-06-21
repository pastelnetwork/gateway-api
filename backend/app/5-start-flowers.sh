#! /usr/bin/env bash

set -e

poetry run celery -A app.main.celery flower --port=5555