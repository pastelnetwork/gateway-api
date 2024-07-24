FROM ubuntu:latest

ARG NETWORK=mainnet
ARG PEERS=""

# Install dependencies
RUN apt update && apt install -y \
    wget curl python3-pip python3-poetry pkg-config vim\
    && apt clean

# Install latest IPFS
RUN wget https://dist.ipfs.tech/kubo/v0.29.0/kubo_v0.29.0_linux-amd64.tar.gz && \
    tar -xvzf kubo_v0.29.0_linux-amd64.tar.gz && \
    cd kubo && \
    bash install.sh && \
    cd .. && \
    rm -rf kubo kubo_v0.29.0_linux-amd64.tar.gz
RUN ipfs init

# Install pastelup
RUN wget https://download.pastel.network/latest-release/pastelup/pastelup-linux-amd64 &&  \
    chmod +x pastelup-linux-amd64 && mv pastelup-linux-amd64 /usr/local/bin/pastelup

# Install Pastel node and download snapshot based on network
RUN pastelup install walletnode -n $NETWORK -f -p $PEERS && \
    wget https://download.pastel.network/snapshots/$NETWORK/snapshot-latest-$NETWORK-txind.tar.gz && \
    tar -xvzf snapshot-latest-$NETWORK-txind.tar.gz -C ~/.pastel && \
    rm snapshot-latest-$NETWORK-txind.tar.gz;

# Add txindex=1 to pastel.conf
RUN echo 'txindex=1' >> ~/.pastel/pastel.conf

# Create a directory for scripts
RUN mkdir /scripts

# Create entrypoint script
RUN echo '#!/bin/bash\n\
export PASTEL_RPC_USER=$(grep -oP "(?<=rpcuser=).*" ~/.pastel/pastel.conf)\n\
export PASTEL_RPC_PWD=$(grep -oP "(?<=rpcpassword=).*" ~/.pastel/pastel.conf)\n\
export NETWORK='$NETWORK'\n\
case "$NETWORK" in\n\
  mainnet)\n\
    export PASTEL_RPC_PORT=9932\n\
    export BURN_ADDRESS=PtpasteLBurnAddressXXXXXXXXXXbJ5ndd\n\
    ;;\n\
  testnet)\n\
    export PASTEL_RPC_PORT=19932\n\
    export BURN_ADDRESS=tPpasteLBurnAddressXXXXXXXXXXX3wy7u\n\
    ;;\n\
  devnet)\n\
    export PASTEL_RPC_PORT=29932\n\
    export BURN_ADDRESS=44oUgmZSL997veFEQDq569wv5tsT6KXf9QY7\n\
    ;;\n\
  *)\n\
    echo "Unknown network: $NETWORK"\n\
    exit 1\n\
    ;;\n\
esac\n\
exec "$@"' > /scripts/entrypoint.sh &&  \
    chmod +x /scripts/entrypoint.sh

WORKDIR /app

# Copy scripts
COPY init_pastel.sh /scripts/init_pastel.sh
COPY run_app.sh /scripts/run_app.sh
RUN chmod +x /scripts/init_pastel.sh /scripts/run_app.sh

# Use ENTRYPOINT to run the entrypoint script
ENTRYPOINT ["/scripts/entrypoint.sh"]

# Default CMD is bash, allowing us to override easily
CMD ["/bin/bash"]