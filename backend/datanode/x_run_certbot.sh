#!/bin/bash

# Get the SERVER_HOST from environment or use the host's IP address
DOMAIN=${SERVER_HOST:-$HOST_IP}
EMAIL="your_email@example.com"

# Check if DOMAIN is an IP address
if [[ $DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Warning: Using an IP address ($DOMAIN) for SSL certificate. This is not recommended for production."
    echo "Please set a proper domain name in the SERVER_HOST environment variable."
    exit 1
fi

# Run certbot
docker-compose run --rm --entrypoint "\
  certbot --nginx \
  --email $EMAIL \
  --agree-tos \
  --no-eff-email \
  --force-renewal \
  -d $DOMAIN" nginx

# Reload nginx to apply the new configuration
docker-compose exec nginx nginx -s reload

echo "Certbot process completed. Check the output for any errors."