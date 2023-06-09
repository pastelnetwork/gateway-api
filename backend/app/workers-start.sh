#! /usr/bin/env bash
set -e

poetry run celery -A app.main.celery worker -l debug -Q cascade,sense,nft