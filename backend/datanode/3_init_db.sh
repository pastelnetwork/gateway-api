#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Check if both email and password are provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <superuser_email> <superuser_password>"
    exit 1
fi

SUPERUSER_EMAIL=$1
SUPERUSER_PASSWORD=$2

# Check if pastel_data_node container is running
if ! docker ps --format '{{.Names}}' | grep -q '^pastel_data_node$'; then
    echo "Error: pastel_data_node container is not running. Please ensure it's started with 2_start_all.sh first."
    exit 1
fi

# Execute the Python script inside the Docker container
echo "Initializing database with superuser..."
docker exec -w /app pastel_data_node bash -c '
    PYTHONPATH=/app env $(cat /scripts/.env_sensitive | xargs) poetry run python app/init_db_script.py --email "'$SUPERUSER_EMAIL'" --password "'$SUPERUSER_PASSWORD'"
'

echo "Database initialization complete."
