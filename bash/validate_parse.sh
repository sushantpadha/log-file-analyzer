#!/bin/bash

# just in case
if [[ ! ($# -eq 2) ]]; then
    echo "Usage: <script.sh> <log_file_path> <csv_file_path>" >&2
    exit 1
fi

# args are LOG_FILE, CSV_FILE

# if file is CRLF terminated, we dont care :) convert to LF
sed -i.bck 's/\r$//' "$1"

# Assuming creation of log and csv files was done prior to calling script
# and relevant permissions are given

# ! Assumes script is always called from project root
# TODO: ensure no issues with quoting
awk -v OUTFILE="$2" -f "bash/validate_parse.awk" "$1"

err=$?

if [[ ! $err -eq 0 ]]; then
    exit $err
fi

# basic check for output file
if [[ ! -s "$2" ]]; then
    echo "Error: Failed to create or populate CSV file '$2'." >&2
    rm -f "$2"
    exit 1
fi