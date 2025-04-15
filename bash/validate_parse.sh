#!/bin/bash

# just in case
if [[ ! ($# -eq 2) ]]; then
    echo "Usage: <script.sh> <log_file_path> <csv_file_path>"
    exit 1
fi

# args are LOG_FILE, CSV_FILE

# if file is CRLF terminated, we dont care :) convert to LF
sed -i.bck 's/\r$//' "$1"

# ! Assumes script is always called from project root
awk -v OUTFILE="$2" -f "bash/validate_parse.awk" "$1"
