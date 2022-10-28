#!/bin/sh
repo="$IPFS_PATH"

if [ ! -f "$repo/config" ]; then
  ipfs init
  sed -i -e 's/127.0.0.1/0.0.0.0/' /data/ipfs/config
fi

ipfs daemon
