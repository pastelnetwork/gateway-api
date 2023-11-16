#! /usr/bin/env bash

# Let the DB start
python ./app/backend_pre_start.py

# Uncomment this line to run migrations
#alembic upgrade head

# Uncomment this line to create initial data - only do on the first start, when no DB is defined yet!!!
#python ./app/initial_data.py
