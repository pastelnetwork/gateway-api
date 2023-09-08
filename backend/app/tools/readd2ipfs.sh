#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 /path/to/directory"
  exit 1
fi

# Get the total number of files
total_files=$(find "$1" -type f | wc -l)
processed_files=0
  echo "There are $total_files files to process"

for file in "$1"/*; do
  if [ -f "$file" ]; then
    ipfs add "$file"
    ((processed_files++))
    echo -ne "Processed: $processed_files/$total_files, File: $(basename "$file")\r"
  fi
done

echo # To print a newline after the loop ends
