#! /usr/bin/env bash
set -e

celery -A app.main.celery beat -l debug
