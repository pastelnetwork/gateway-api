#! /usr/bin/env bash
set -e

celery -A app.main.celery flower --port=5555