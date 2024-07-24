#!/bin/bash

# Default values
export FILE_STORAGE=${FILE_STORAGE:-/path/to/default/storage}

# Get the host IP address
HOST_IP=$(hostname -I | awk '{print $1}')
# Export the HOST_IP as an environment variable
export HOST_IP

# Start the application using docker-compose
docker-compose up -d