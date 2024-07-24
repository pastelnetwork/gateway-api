#!/bin/bash

# Check if initialization has already been done
if [ -f "/scripts/.init_complete" ]; then
    echo "Initialization already completed for $NETWORK network. Skipping."
    exit 0
fi

# Start pasteld daemon
~/pastel/pasteld -datadir=/root/.pastel -daemon

# Function to check sync status
check_sync_status() {
    local sync_status
    sync_status=$(~/pastel/pastel-cli mnsync status)
    echo $sync_status | grep -q '"IsSynced": true'
}

# Wait for synchronization
echo "Waiting for Pastel node to synchronize on $NETWORK network..."
counter=0
while ! check_sync_status; do
    block_height=$(~/pastel/pastel-cli getblockcount)
    asset_name=$(~/pastel/pastel-cli mnsync status | grep AssetName | awk -F'"' '{print $4}')
    echo "Still syncing... (Block Height: $block_height; AssetName: $asset_name)"

    if [ "$asset_name" = "Initial" ]; then
        ((counter++))
        if [ $counter -ge 10 ]; then
            echo "AssetName still 'Initial' after 10 attempts. Resetting mnsync..."
            ~/pastel/pastel-cli mnsync reset
            counter=0
        fi
    else
        counter=0
    fi

    sleep 60
done
echo "Synchronization complete for $NETWORK network!"

# Generate new values
MAIN_GATEWAY_ADDRESS=$(~/pastel/pastel-cli getnewaddress)
PASTEL_ID_PWD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)

# Create new Pastel ID
~/pastel/pastel-cli pastelid newkey $PASTEL_ID_PWD
PASTEL_ID=$(ls ~/.pastel/pastelkeys/)

# Print the sensitive information once
echo "=============== SENSITIVE INFORMATION ==============="
echo "NETWORK=$NETWORK"
echo "MAIN_GATEWAY_ADDRESS=$MAIN_GATEWAY_ADDRESS"
echo "PASTEL_ID_PWD=$PASTEL_ID_PWD"
echo "PASTEL_ID=$PASTEL_ID"
echo "PASTEL_RPC_USER=$PASTEL_RPC_USER"
echo "PASTEL_RPC_PWD=PASTEL_RPC_PWD"
echo "====================================================="
echo "Please save this information securely."

# Save sensitive information to a file inside the container
echo "NETWORK=$NETWORK" > /scripts/.env_sensitive
echo "MAIN_GATEWAY_ADDRESS=$MAIN_GATEWAY_ADDRESS" >> /scripts/.env_sensitive
echo "PASTEL_ID_PWD=$PASTEL_ID_PWD" >> /scripts/.env_sensitive
echo "PASTEL_ID=$PASTEL_ID" >> /scripts/.env_sensitive
echo "PASTEL_RPC_USER=$PASTEL_RPC_USER" >> /scripts/.env_sensitive
echo "PASTEL_RPC_PWD=$PASTEL_RPC_PWD" >> /scripts/.env_sensitive
echo "PASTEL_RPC_PORT=$PASTEL_RPC_PORT" >> /scripts/.env_sensitive
echo "BURN_ADDRESS=$BURN_ADDRESS" >> /scripts/.env_sensitive


# Mark initialization as complete
touch /scripts/.init_complete

# Stop the pasteld daemon
~/pastel/pastel-cli stop

echo "Initialization complete for $NETWORK network. You can now use docker-compose to start the application."