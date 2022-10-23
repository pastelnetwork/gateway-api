#! /usr/bin/env sh
set -e

/pastelup-linux-amd64 start walletnode --development-mode

if [ -f ~/.pastel/walletnode.log ]; then
    TAIL_FILE=~/.pastel/walletnode.log
else
    TAIL_FILE=/dev/null
fi

tail -F "$TAIL_FILE"
