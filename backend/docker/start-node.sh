#! /usr/bin/env sh
set -e

/pastelup-linux-amd64 start node

if [ -f ~/.pastel/debug.log ]; then
    TAIL_FILE=~/.pastel/debug.log
elif [ -f ~/.pastel/testnet3/debug.log ]; then
    TAIL_FILE=~/.pastel/testnet3/debug.log
else
    TAIL_FILE=/dev/null
fi

tail -F "$TAIL_FILE"
