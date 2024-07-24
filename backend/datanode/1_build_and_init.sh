#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Default value for network
NETWORK=${1:-mainnet}

if [ "$NETWORK" == "mainnet" ]; then
  PEERS="18.218.28.57,18.220.120.83,3.141.226.93,3.132.60.47,18.116.179.95"
elif [ "$NETWORK" == "testnet" ]; then
  PEERS="154.12.235.41,154.12.235.19,154.12.235.16"
elif [ "$NETWORK" == "devnet" ]; then
  PEERS="154.12.243.33,154.38.164.105,207.244.236.251"
else
  echo "Invalid network. Please use 'mainnet', 'testnet', or 'devnet'."
  exit 1
fi

# Remove existing pastel_data volume if it exists
echo "Removing existing pastel_data volume if it exists..."
docker volume rm pastel_data || true

# Create a named volume for Pastel data
docker volume create pastel_data

# Build the Docker image
echo "Building Docker image..."
docker build --build-arg NETWORK="$NETWORK" --build-arg PEERS="$PEERS" -t pastel_data_node:latest -f pastel_data_node.dockerfile .

# Run initialization
echo "Starting initialization..."
docker run --name init_container -e NETWORK="$NETWORK" -v pastel_data:/root/.pastel pastel_data_node:latest bash /scripts/init_pastel.sh

# Check if the container exited successfully
# shellcheck disable=SC2046
if [ $(docker inspect init_container --format='{{.State.ExitCode}}') -ne 0 ]; then
    echo "Initialization failed. Check the logs above for errors."
    docker rm init_container
    exit 1
fi

# Commit the changes to a new image
echo "Committing changes to new image..."
docker commit init_container pastel_data_node:initialized

# Remove the temporary container
docker rm init_container

echo "Build and initialization complete for $NETWORK network. A new image 'pastel_data_node:initialized' has been created."
echo "You can now start the application using 2_start_all.sh with the new image."