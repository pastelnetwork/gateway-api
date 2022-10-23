#! /usr/bin/env bash
set -e

#python /app/app/celeryworker_pre_start.py

celery -A app.main.celery worker -l debug -Q cascade,sense
