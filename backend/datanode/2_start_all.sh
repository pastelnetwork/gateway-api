#!/bin/bash

# Default values
export FILE_STORAGE=${FILE_STORAGE:-/path/to/default/storage}

# Start the application using docker-compose
docker-compose up -d